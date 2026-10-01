"""Everything that touches the real browser: learning the portal's requests and replaying them."""

import os
import threading
import time
from dataclasses import dataclass, field
from datetime import date
from urllib.parse import urlparse

from .config import Capture
from .dates import extract_dates, fmt, parse_json, refresh_timestamps, shape, shape_matches

# Headers the browser sets itself (or that must not be replayed verbatim).
_SKIP_HEADERS = {"cookie", "content-length", "host", "connection", "accept-encoding", "origin", "referer", "user-agent"}

FETCH_JS = """async ({url, method, headers, body}) => {
  try {
    const r = await fetch(url, {method, headers, body: body ?? undefined, credentials: 'include'});
    return {ok: true, status: r.status, url: r.url, text: await r.text()};
  } catch (e) {
    return {ok: false, error: String(e)};
  }
}"""


@dataclass
class CheckResult:
    ok: bool
    dates: list = field(default_factory=list)
    detail: str = ""


def launch(playwright, cfg, headless=False):
    """Open a browser that keeps its own profile, so your login survives restarts."""
    kwargs = {"headless": headless, "no_viewport": True}
    if cfg.browser_channel:
        kwargs["channel"] = cfg.browser_channel
    if os.environ.get("CHROMIUM_EXECUTABLE"):
        kwargs["executable_path"] = os.environ["CHROMIUM_EXECUTABLE"]
    cfg.profile_dir.mkdir(parents=True, exist_ok=True)
    return playwright.chromium.launch_persistent_context(str(cfg.profile_dir), **kwargs)


def _site(url):
    host = urlparse(url).hostname or ""
    return ".".join(host.split(".")[-2:])


def _same_path(a, b):
    return urlparse(a).path.rstrip("/") == urlparse(b).path.rstrip("/")


def _dedupe_key(method, url, body):
    return (method, refresh_timestamps(url, 0), refresh_timestamps(body or "", 0))


def make_response_listener(portal_url, today, found, log=print):
    """Build a page 'response' handler that records portal requests whose JSON contains future dates.

    `found` receives (Capture, future_dates) tuples; the Capture's name is filled in later.
    """
    seen = set()
    site = _site(portal_url)

    def on_response(response):
        request = response.request
        if request.resource_type not in ("xhr", "fetch") or _site(request.url) != site:
            return
        try:
            data = parse_json(response.text())
        except Exception:
            return
        if data is None:
            return
        future = [d for d in extract_dates(data) if d >= today]
        if not future:
            return
        key = _dedupe_key(request.method, request.url, request.post_data)
        if key in seen:
            return
        seen.add(key)
        try:
            page_url = request.frame.url
        except Exception:
            page_url = portal_url
        headers = {k: v for k, v in request.headers.items() if k.lower() not in _SKIP_HEADERS and not k.startswith(("sec-", ":"))}
        capture = Capture(
            name="",
            method=request.method,
            url=request.url,
            body=request.post_data,
            headers=headers,
            page_url=page_url,
            shape=shape(data),
        )
        found.append((capture, future))
        log(f"  Captured #{len(found)}: {describe(capture)} -> {len(future)} date(s), earliest {fmt(future[0])}")

    return on_response


def describe(capture):
    """Short human label for a request, e.g. 'POST /custom-actions/ (get-family-consular-schedule-days)'."""
    parsed = urlparse(capture.url)
    route = [p.split("=", 1)[1] for p in parsed.query.split("&") if p.startswith("route=")]
    hint = f" ({route[0].rstrip('/').split('/')[-1]})" if route else ""
    return f"{capture.method} {parsed.path}{hint}"


def learn(playwright, cfg, ask=input, log=print):
    """Let the user log in and open each calendar; return the captured requests, named."""
    context = launch(playwright, cfg)
    try:
        page = context.pages[0] if context.pages else context.new_page()
        found = []
        context.on("response", make_response_listener(cfg.portal_url, date.today(), found, log))
        page.goto(cfg.portal_url)

        log(
            "\nA browser window has opened.\n"
            "  1. Log in to your account in that window (solve the CAPTCHA yourself).\n"
            "  2. Go to Schedule / Reschedule Appointment.\n"
            "  3. Pick each location you'd accept so its calendar of available dates loads\n"
            "     (both the OFC/biometrics and the consular interview, if you need both).\n"
            "  4. Each calendar that loads appears here as 'Captured'.\n"
            "  5. When you're done, come back here and press Enter.\n"
        )
        done = threading.Event()
        threading.Thread(target=lambda: (ask(""), done.set()), daemon=True).start()
        while not done.is_set():
            # Playwright only delivers events while we're inside one of its calls.
            if context.pages:
                context.pages[0].wait_for_timeout(300)
            else:
                time.sleep(0.3)

        captures = []
        for i, (capture, future) in enumerate(found, 1):
            preview = ", ".join(d.strftime("%d %b %Y") for d in future[:4])
            log(f"\n#{i}: {describe(capture)}\n    dates: {preview}{' ...' if len(future) > 4 else ''}")
            name = ask("    Name it (e.g. 'Chennai interview'), or press Enter to skip: ").strip()
            if name:
                capture.name = name
                captures.append(capture)
        return captures
    finally:
        context.close()


class BrowserChecker:
    """Replays captured requests from inside the logged-in page, like the portal itself does."""

    def __init__(self, page, now_ms=lambda: int(time.time() * 1000), navigate_timeout_ms=60_000):
        self.page = page
        self.now_ms = now_ms
        self.navigate_timeout_ms = navigate_timeout_ms
        self._visited_this_round = set()

    def start_round(self):
        self._visited_this_round.clear()

    def __call__(self, capture, healthy):
        # Reload the page the request came from, which also keeps the session alive. If we're
        # unhealthy and the window is on another page (likely the login page), leave it alone so
        # we never yank the page out from under someone who is typing their password.
        if capture.page_url not in self._visited_this_round and (healthy or _same_path(self.page.url, capture.page_url)):
            self._visited_this_round.add(capture.page_url)
            try:
                self.page.goto(capture.page_url, wait_until="networkidle", timeout=self.navigate_timeout_ms)
            except Exception as e:
                if "Timeout" not in type(e).__name__:
                    return self._browser_problem(e, "couldn't load the portal page")

        now = self.now_ms()
        try:
            result = self.page.evaluate(
                FETCH_JS,
                {
                    "url": refresh_timestamps(capture.url, now),
                    "method": capture.method,
                    "headers": capture.headers,
                    "body": refresh_timestamps(capture.body, now),
                },
            )
        except Exception as e:
            # e.g. the portal redirected to its login page mid-check.
            return self._browser_problem(e, "the page changed while checking")
        if not result["ok"]:
            return CheckResult(False, detail=f"request failed ({result['error']})")
        if result["status"] != 200:
            return CheckResult(False, detail=f"portal answered HTTP {result['status']}")
        data = parse_json(result["text"])
        if data is None:
            return CheckResult(False, detail="got a web page instead of data (probably logged out)")
        if capture.shape is not None and not shape_matches(capture.shape, shape(data)):
            return CheckResult(False, detail="portal sent an unexpected reply (probably logged out)")
        return CheckResult(True, dates=extract_dates(data))

    @staticmethod
    def _browser_problem(error, what):
        """A network blip is a failed check; a closed browser window is fatal."""
        message = str(error)
        if "closed" in message.lower():
            raise error
        first = message.splitlines()[0] if message else type(error).__name__
        return CheckResult(False, detail=f"{what} ({first[:120]})")
