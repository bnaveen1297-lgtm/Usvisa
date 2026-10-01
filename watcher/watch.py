"""The watch loop: check, compare, alert. No browser code here so it can be tested directly."""

import random
import time
from datetime import datetime, timedelta

from .dates import filter_dates, fmt

RETRY_MINUTES = 3
PROBLEM_ALERT_AFTER = 2  # consecutive failed rounds before we bother you
PROBLEM_REMINDER = timedelta(hours=1)


class Watcher:
    def __init__(self, cfg, captures, notify, checker, now=datetime.now, rng=random.random):
        self.cfg = cfg
        self.captures = captures
        self.notify = notify
        self.checker = checker
        self.now = now
        self.rng = rng
        self.healthy = True
        self.failures = 0
        self.last_problem_alert = None
        self.alerted = {c.name: set() for c in captures}
        self.latest = {}
        self.last_ok = None
        self.last_heartbeat = now()

    def window(self):
        return f"{fmt(self.cfg.earliest_acceptable_date)} to {fmt(self.cfg.latest_acceptable_date)}"

    def start_message(self):
        names = "\n".join(f"  - {c.name}" for c in self.captures)
        return (
            "👀 Visa slot watcher started\n"
            f"Watching:\n{names}\n"
            f"Alerting for dates {self.window()}\n"
            f"Checking about every {self.cfg.check_interval_minutes:g} minutes."
        )

    def cycle(self):
        now = self.now()
        if hasattr(self.checker, "start_round"):
            self.checker.start_round()

        results = {c.name: self.checker(c, self.healthy) for c in self.captures}
        problems = {name: r.detail for name, r in results.items() if not r.ok}

        if problems:
            self.failures += 1
            self.healthy = False
            due = self.last_problem_alert is None or now - self.last_problem_alert >= PROBLEM_REMINDER
            if self.failures >= PROBLEM_ALERT_AFTER and due:
                lines = "\n".join(f"  - {name}: {detail}" for name, detail in problems.items())
                self.notify(
                    "⚠️ Visa watcher can't check slots\n"
                    f"{lines}\n"
                    "If you've been logged out, log in again in the watcher's browser window. "
                    f"It retries every {RETRY_MINUTES} minutes and will tell you when it's back."
                )
                self.last_problem_alert = now
        else:
            if self.last_problem_alert is not None:
                self.notify("✅ Visa watcher is back to checking slots.")
            self.healthy = True
            self.failures = 0
            self.last_problem_alert = None
            self.last_ok = now

        for name, result in results.items():
            if not result.ok:
                print(f"[{now:%H:%M}] {name}: problem: {result.detail}")
                continue
            dates = sorted(result.dates)
            self.latest[name] = dates
            wanted = filter_dates(dates, self.cfg.earliest_acceptable_date, self.cfg.latest_acceptable_date)
            new = sorted(set(wanted) - self.alerted[name])
            # Remember only what's open now, so a date that disappears and comes back alerts again.
            self.alerted[name] = set(wanted)
            earliest = fmt(dates[0]) if dates else "none open"
            print(f"[{now:%H:%M}] {name}: earliest {earliest}; {len(wanted)} in your window; {len(new)} new")
            if new:
                self.notify(self.slot_message(name, wanted, new))

        if now - self.last_heartbeat >= timedelta(hours=self.cfg.heartbeat_hours):
            self.notify(self.heartbeat_message())
            self.last_heartbeat = now

    def slot_message(self, name, wanted, new):
        shown = ", ".join(d.strftime("%d %b") for d in new[:8])
        more = f" (+{len(new) - 8} more)" if len(new) > 8 else ""
        return (
            f"🗓️ Earlier visa slot: {name}\n"
            f"Earliest in your window: {fmt(wanted[0])}\n"
            f"New dates: {shown}{more}\n"
            f"Book it now: {self.cfg.portal_url}\n"
            "Slots go fast. Log in and book it yourself."
        )

    def heartbeat_message(self):
        lines = []
        for c in self.captures:
            dates = self.latest.get(c.name)
            if dates is None:
                lines.append(f"  - {c.name}: not checked yet")
            else:
                lines.append(f"  - {c.name}: earliest open {fmt(dates[0]) if dates else 'none'}")
        last = f"{self.last_ok:%d %b %H:%M}" if self.last_ok else "never"
        status = "OK" if self.healthy else "having trouble, see earlier message"
        return "💤 Visa watcher still running (" + status + f")\nLast good check: {last}\n" + "\n".join(lines)

    def next_delay_seconds(self):
        if not self.healthy:
            return RETRY_MINUTES * 60
        jitter = (self.rng() * 2 - 1) * self.cfg.jitter_minutes
        return max(1.0, self.cfg.check_interval_minutes + jitter) * 60

    def run(self, sleep=time.sleep):
        self.notify(self.start_message())
        while True:
            self.cycle()
            delay = self.next_delay_seconds()
            print(f"  next check in {delay / 60:.1f} min")
            sleep(delay)
