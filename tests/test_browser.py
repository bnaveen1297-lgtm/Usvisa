"""Runs the real browser code against a small fake portal on localhost."""

import json
import os
import threading
from datetime import date
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

sync_api = pytest.importorskip("playwright.sync_api")

from watcher.browser import BrowserChecker, make_response_listener  # noqa: E402
from watcher.config import Capture  # noqa: E402

DAYS = {"ScheduleDays": [{"ID": "a", "Date": "2026-11-04T00:00:00"}, {"ID": "b", "Date": "2026-11-06T00:00:00"}]}
SCHEDULE_PAGE = """<html><body>Schedule
<script>
fetch('/custom-actions/?route=/api/v1/schedule-group/get-family-consular-schedule-days&cacheString=' + Date.now(),
      {method: 'POST', headers: {'Content-Type': 'application/x-www-form-urlencoded', 'X-Requested-With': 'XMLHttpRequest'},
       body: 'parameters=' + encodeURIComponent(JSON.stringify({postId: '17'}))});
fetch('/api/profile', {method: 'GET'});
</script></body></html>"""


class Portal(BaseHTTPRequestHandler):
    seen_bodies = []

    def log_message(self, *a):
        pass

    def _logged_in(self):
        return "session=1" in (self.headers.get("Cookie") or "")

    def _send(self, code, body, ctype="text/html", extra=()):
        data = body.encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        for k, v in extra:
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path.startswith("/login?ok=1"):
            return self._send(302, "", extra=[("Set-Cookie", "session=1; Path=/"), ("Location", "/schedule")])
        if self.path.startswith("/login"):
            return self._send(200, "<html><form>Sign in</form></html>")
        if not self._logged_in():
            return self._send(302, "", extra=[("Location", "/login")])
        if self.path.startswith("/schedule"):
            return self._send(200, SCHEDULE_PAGE)
        if self.path.startswith("/api/profile"):
            return self._send(200, json.dumps({"dob": "1990-01-01"}), "application/json")
        self._send(404, "nope")

    def do_POST(self):
        body = self.rfile.read(int(self.headers.get("Content-Length", 0))).decode()
        Portal.seen_bodies.append((self.path, body, self.headers.get("X-Requested-With")))
        if not self._logged_in():
            return self._send(302, "", extra=[("Location", "/login")])
        self._send(200, json.dumps(DAYS), "application/json")


@pytest.fixture(scope="module")
def portal():
    server = ThreadingHTTPServer(("127.0.0.1", 0), Portal)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown()


@pytest.fixture(scope="module")
def browser():
    with sync_api.sync_playwright() as p:
        exe = os.environ.get("CHROMIUM_EXECUTABLE")
        b = p.chromium.launch(**({"executable_path": exe} if exe else {}))
        yield b
        b.close()


def test_learn_listener_then_checker_round_trip(portal, browser):
    context = browser.new_context()
    page = context.new_page()
    found, logs = [], []
    context.on("response", make_response_listener(portal + "/", date(2026, 10, 1), found, logs.append))

    page.goto(portal + "/login?ok=1")  # "user logs in" and lands on the schedule page
    page.wait_for_timeout(500)

    # Only the calendar request is captured; the profile's birth date is in the past.
    assert len(found) == 1, logs
    capture, future = found[0]
    assert future == [date(2026, 11, 4), date(2026, 11, 6)]
    assert capture.method == "POST" and capture.page_url.endswith("/schedule")
    assert capture.headers.get("x-requested-with") == "XMLHttpRequest"
    assert "(get-family-consular-schedule-days)" in logs[0]
    capture.name = "Chennai"

    checker = BrowserChecker(page, now_ms=lambda: 1800000000000)
    checker.start_round()
    result = checker(capture, healthy=True)
    assert result.ok and result.dates == future
    path, body, xrw = Portal.seen_bodies[-1]
    assert "cacheString=1800000000000" in path and "postId" in body and xrw == "XMLHttpRequest"

    # Session expires: the checker reports it, and doesn't navigate away from the login page.
    context.clear_cookies()
    page.goto(portal + "/login")
    checker.start_round()
    result = checker(capture, healthy=False)
    assert not result.ok and "logged out" in result.detail
    assert page.url.endswith("/login")

    # User logs back in from wherever; the next check recovers.
    page.goto(portal + "/login?ok=1")
    checker.start_round()
    assert checker(capture, healthy=False).ok
    context.close()


def test_network_failure_is_a_failed_check_not_a_crash(browser):
    page = browser.new_page()

    dead = "http://127.0.0.1:9/"  # nothing listens on port 9
    capture = Capture(name="x", method="GET", url=dead + "api", body=None, headers={}, page_url=dead + "schedule")
    checker = BrowserChecker(page, navigate_timeout_ms=5000)
    checker.start_round()
    result = checker(capture, healthy=True)
    assert not result.ok and "couldn't load the portal page" in result.detail

    page.close()
    checker.start_round()
    with pytest.raises(Exception, match="(?i)closed"):
        checker(capture, healthy=True)
