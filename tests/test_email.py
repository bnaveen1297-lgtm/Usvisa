import smtplib

import pytest

from watcher.__main__ import alert_channels, fan_out
from watcher.config import Config, ConfigError, require_alerts
from watcher.email_alerts import Email


class FakeSMTP:
    sent = []
    fail_login = False

    def __init__(self, host, port, timeout=None, context=None):
        self.host, self.port, self.tls = host, port, context is not None

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def starttls(self, context=None):
        self.tls = True

    def login(self, user, password):
        if FakeSMTP.fail_login:
            raise smtplib.SMTPAuthenticationError(535, b"bad credentials")
        self.user = user

    def send_message(self, msg):
        assert self.tls, "must never send without TLS"
        FakeSMTP.sent.append((self.port, msg))


@pytest.fixture
def smtp(monkeypatch):
    FakeSMTP.sent, FakeSMTP.fail_login = [], False
    monkeypatch.setattr(smtplib, "SMTP", FakeSMTP)
    monkeypatch.setattr(smtplib, "SMTP_SSL", FakeSMTP)
    return FakeSMTP


def test_first_line_is_subject_rest_is_body(smtp):
    e = Email("smtp.gmail.com", 587, "me@gmail.com", "pw", "you@example.com")
    assert e.send("🗓️ Earlier visa slot: Chennai\nEarliest: Wed 04 Nov 2026\nBook it now")
    port, msg = smtp.sent[0]
    assert port == 587
    assert msg["Subject"] == "🗓️ Earlier visa slot: Chennai"
    assert (msg["From"], msg["To"]) == ("me@gmail.com", "you@example.com")
    assert msg.get_content().strip() == "Earliest: Wed 04 Nov 2026\nBook it now"


def test_ssl_port_and_failures_dont_raise(smtp):
    Email("smtp.example.com", 465, "a", "b", "c").send("hi")
    assert smtp.sent[0][0] == 465
    smtp.fail_login = True
    assert Email("smtp.gmail.com", 587, "a", "b", "c").send("hi") is False


def test_channels_and_fan_out(smtp, monkeypatch):
    cfg = Config(email_username="me@gmail.com", email_password="pw", email_to="me@gmail.com")
    assert [n for n, _ in alert_channels(cfg)] == ["email to me@gmail.com"]

    cfg.telegram_bot_token, cfg.telegram_chat_id = "t", "1"
    got = []
    monkeypatch.setattr("watcher.telegram.Telegram.send", lambda self, text: got.append(text) or True)
    channels = alert_channels(cfg)
    assert [n for n, _ in channels] == ["Telegram", "email to me@gmail.com"]
    fan_out(channels)("hello\nworld")
    assert got == ["hello\nworld"] and len(smtp.sent) == 1


def test_needs_at_least_one_channel():
    with pytest.raises(ConfigError, match="setup-email"):
        require_alerts(Config())
    require_alerts(Config(email_username="a", email_password="b", email_to="a"))
