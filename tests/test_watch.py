from datetime import date, datetime, timedelta

from watcher.browser import CheckResult
from watcher.config import Capture, Config
from watcher.watch import RETRY_MINUTES, Watcher


class Clock:
    def __init__(self):
        self.t = datetime(2026, 10, 1, 9, 0)

    def __call__(self):
        return self.t

    def advance(self, **kw):
        self.t += timedelta(**kw)


def make(results):
    """results: list of CheckResult (one per cycle) or a callable."""
    cfg = Config(earliest_acceptable_date=date(2026, 10, 5), latest_acceptable_date=date(2026, 12, 31), heartbeat_hours=24)
    cap = Capture(name="Chennai interview", method="POST", url="u", body=None, headers={}, page_url="p")
    sent, clock, queue = [], Clock(), list(results)
    w = Watcher(cfg, [cap], sent.append, lambda c, healthy: queue.pop(0), now=clock, rng=lambda: 0.5)
    return w, sent, clock


def ok(*ds):
    return CheckResult(True, dates=[date.fromisoformat(d) for d in ds])


def test_alerts_once_per_new_date_in_window_and_realerts_if_it_returns():
    w, sent, _ = make([
        ok("2027-03-01"),                 # outside window: silent
        ok("2026-11-04", "2027-03-01"),   # new date in window: alert
        ok("2026-11-04"),                 # same: silent
        ok("2026-11-04", "2026-11-02"),   # one more: alert for it only
        ok("2027-03-01"),                 # gone
        ok("2026-11-04"),                 # back again: alert
    ])
    for _ in range(6):
        w.cycle()
    assert len(sent) == 3
    assert "04 Nov" in sent[0] and "Earliest in your window: Wed 04 Nov 2026" in sent[0]
    assert "New dates: 02 Nov" in sent[1] and "Earliest in your window: Mon 02 Nov 2026" in sent[1]
    assert "04 Nov" in sent[2]


def test_problem_alert_after_two_failures_then_hourly_then_recovery():
    bad = CheckResult(False, detail="got a web page instead of data (probably logged out)")
    w, sent, clock = make([bad, bad, bad, bad, ok()])
    w.cycle()
    assert sent == [] and not w.healthy
    assert w.next_delay_seconds() == RETRY_MINUTES * 60
    clock.advance(minutes=3); w.cycle()
    assert len(sent) == 1 and "log in again" in sent[0]
    clock.advance(minutes=3); w.cycle()
    assert len(sent) == 1  # no spam
    clock.advance(hours=1); w.cycle()
    assert len(sent) == 2  # hourly reminder
    clock.advance(minutes=3); w.cycle()
    assert "back to checking" in sent[-1] and w.healthy


def test_single_blip_recovers_silently():
    w, sent, _ = make([CheckResult(False, detail="HTTP 500"), ok()])
    w.cycle(); w.cycle()
    assert sent == [] and w.healthy


def test_heartbeat_and_jittered_interval():
    w, sent, clock = make([ok("2027-02-01"), ok("2027-02-01")])
    w.cycle()
    clock.advance(hours=24, minutes=1); w.cycle()
    assert len(sent) == 1 and "still running" in sent[0] and "Mon 01 Feb 2027" in sent[0]
    assert w.next_delay_seconds() == 15 * 60  # rng 0.5 -> zero jitter
    w.rng = lambda: 1.0
    assert w.next_delay_seconds() == 19 * 60
