from datetime import date, timedelta

import pytest

from watcher.__main__ import _write_env
from watcher.config import ConfigError, load_captures, load_config


def write(tmp_path, text):
    (tmp_path / "config.toml").write_text(text)


def test_defaults_and_dotenv(tmp_path, monkeypatch):
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    for var in ("TELEGRAM_CHAT_ID", "EMAIL_USERNAME", "EMAIL_PASSWORD", "EMAIL_TO", "EMAIL_SMTP_HOST", "EMAIL_SMTP_PORT"):
        monkeypatch.delenv(var, raising=False)
    write(tmp_path, 'latest_acceptable_date = "2099-01-31"\n')
    (tmp_path / ".env").write_text("TELEGRAM_BOT_TOKEN=abc\nTELEGRAM_CHAT_ID='42'\nEMAIL_USERNAME=me@gmail.com\nEMAIL_PASSWORD=abcd efgh ijkl mnop\n")
    cfg = load_config(tmp_path)
    assert cfg.earliest_acceptable_date == date.today() + timedelta(days=2)
    assert cfg.latest_acceptable_date == date(2099, 1, 31)
    assert (cfg.telegram_bot_token, cfg.telegram_chat_id) == ("abc", "42")
    assert cfg.profile_dir == tmp_path / "browser-profile"
    # Gmail shows app passwords with spaces; EMAIL_TO defaults to yourself.
    assert (cfg.email_password, cfg.email_to, cfg.email_smtp_port) == ("abcdefghijklmnop", "me@gmail.com", 587)


@pytest.mark.parametrize("text, msg", [
    ("", "latest_acceptable_date"),
    ('latest_acceptable_date = "31/01/2027"', "must look like"),
    ('latest_acceptable_date = "2099-01-31"\ncheck_interval_minutes = 1', "at least 5"),
    ('earliest_acceptable_date = "2099-02-01"\nlatest_acceptable_date = "2099-01-31"', "before"),
])
def test_rejects_bad_config(tmp_path, text, msg):
    write(tmp_path, text)
    with pytest.raises(ConfigError, match=msg):
        load_config(tmp_path)


def test_jitter_is_clamped(tmp_path):
    write(tmp_path, 'latest_acceptable_date = "2099-01-31"\ncheck_interval_minutes = 6\njitter_minutes = 10\n')
    assert load_config(tmp_path).jitter_minutes == 3.5


def test_write_env_updates_in_place(tmp_path):
    env = tmp_path / ".env"
    env.write_text("# mine\nTELEGRAM_CHAT_ID=1\nOTHER=x\n")
    _write_env(env, {"TELEGRAM_BOT_TOKEN": "t", "TELEGRAM_CHAT_ID": "2"})
    assert env.read_text() == "# mine\nTELEGRAM_CHAT_ID=2\nOTHER=x\nTELEGRAM_BOT_TOKEN=t\n"


def test_damaged_or_empty_captures_file(tmp_path):
    f = tmp_path / "captured_requests.json"
    for text in ("not json", '[{"wrong": 1}]', "[]"):
        f.write_text(text)
        with pytest.raises(ConfigError, match="learn"):
            load_captures(f)
