"""Loads config.toml, .env and the captured portal requests."""

import json
import os
import tomllib
from dataclasses import asdict, dataclass, field
from datetime import date, timedelta
from pathlib import Path

MIN_INTERVAL_MINUTES = 5


class ConfigError(Exception):
    pass


@dataclass
class Capture:
    """One portal request that returns available dates (e.g. one consulate's calendar)."""

    name: str
    method: str
    url: str
    body: str | None
    headers: dict
    page_url: str
    shape: object = None


@dataclass
class Config:
    portal_url: str = "https://www.usvisascheduling.com/"
    earliest_acceptable_date: date | None = None
    latest_acceptable_date: date | None = None
    check_interval_minutes: float = 15
    jitter_minutes: float = 4
    heartbeat_hours: float = 24
    browser_channel: str = ""
    profile_dir: Path = Path("browser-profile")
    captures_file: Path = Path("captured_requests.json")
    telegram_bot_token: str = field(default="", repr=False)
    telegram_chat_id: str = ""
    email_smtp_host: str = "smtp.gmail.com"
    email_smtp_port: int = 587
    email_username: str = ""
    email_password: str = field(default="", repr=False)
    email_to: str = ""


def _load_dotenv(path):
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def _as_date(raw, key):
    if raw in (None, ""):
        return None
    if isinstance(raw, date):
        return raw
    try:
        return date.fromisoformat(str(raw))
    except ValueError:
        raise ConfigError(f"{key} must look like 2026-12-31, got {raw!r}") from None


def load_config(base=Path(".")):
    base = Path(base)
    _load_dotenv(base / ".env")
    path = base / "config.toml"
    if not path.exists():
        raise ConfigError("config.toml not found. Copy config.example.toml to config.toml and edit it.")
    with path.open("rb") as f:
        raw = tomllib.load(f)

    cfg = Config(
        portal_url=raw.get("portal_url", Config.portal_url),
        earliest_acceptable_date=_as_date(raw.get("earliest_acceptable_date"), "earliest_acceptable_date"),
        latest_acceptable_date=_as_date(raw.get("latest_acceptable_date"), "latest_acceptable_date"),
        check_interval_minutes=float(raw.get("check_interval_minutes", Config.check_interval_minutes)),
        jitter_minutes=float(raw.get("jitter_minutes", Config.jitter_minutes)),
        heartbeat_hours=float(raw.get("heartbeat_hours", Config.heartbeat_hours)),
        browser_channel=raw.get("browser_channel", ""),
        profile_dir=base / raw.get("profile_dir", "browser-profile"),
        captures_file=base / raw.get("captures_file", "captured_requests.json"),
        telegram_bot_token=os.environ.get("TELEGRAM_BOT_TOKEN", ""),
        telegram_chat_id=os.environ.get("TELEGRAM_CHAT_ID", ""),
        email_smtp_host=os.environ.get("EMAIL_SMTP_HOST") or Config.email_smtp_host,
        email_smtp_port=int(os.environ.get("EMAIL_SMTP_PORT") or Config.email_smtp_port),
        email_username=os.environ.get("EMAIL_USERNAME", ""),
        email_password=os.environ.get("EMAIL_PASSWORD", "").replace(" ", ""),
        email_to=os.environ.get("EMAIL_TO", "") or os.environ.get("EMAIL_USERNAME", ""),
    )
    if cfg.earliest_acceptable_date is None:
        cfg.earliest_acceptable_date = date.today() + timedelta(days=2)
    if cfg.latest_acceptable_date is None:
        raise ConfigError("Set latest_acceptable_date in config.toml (only slots on or before it trigger an alert).")
    if cfg.latest_acceptable_date < cfg.earliest_acceptable_date:
        raise ConfigError("latest_acceptable_date is before earliest_acceptable_date.")
    if cfg.check_interval_minutes < MIN_INTERVAL_MINUTES:
        raise ConfigError(
            f"check_interval_minutes must be at least {MIN_INTERVAL_MINUTES}; checking more often risks an account lock."
        )
    cfg.jitter_minutes = max(0.0, min(cfg.jitter_minutes, cfg.check_interval_minutes - MIN_INTERVAL_MINUTES / 2))
    return cfg


def telegram_configured(cfg):
    return bool(cfg.telegram_bot_token and cfg.telegram_chat_id)


def email_configured(cfg):
    return bool(cfg.email_username and cfg.email_password and cfg.email_to)


def require_alerts(cfg):
    if not telegram_configured(cfg) and not email_configured(cfg):
        raise ConfigError(
            "No alerts are set up yet. Run: python -m watcher setup-telegram  and/or  python -m watcher setup-email"
        )


def load_captures(path):
    path = Path(path)
    if not path.exists():
        raise ConfigError(f"{path} not found. Run: python -m watcher learn")
    try:
        captures = [Capture(**c) for c in json.loads(path.read_text())]
    except (ValueError, TypeError):
        raise ConfigError(f"{path} is damaged. Run: python -m watcher learn") from None
    if not captures:
        raise ConfigError(f"{path} has no requests in it. Run: python -m watcher learn")
    return captures


def save_captures(path, captures):
    Path(path).write_text(json.dumps([asdict(c) for c in captures], indent=2))
