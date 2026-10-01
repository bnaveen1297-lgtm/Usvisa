"""Pull appointment dates out of whatever JSON the portal returns."""

import json
import re
from datetime import date, datetime, timezone

_ISO = re.compile(r"^(\d{4})-(\d{2})-(\d{2})")
_DOTNET = re.compile(r"^/Date\((-?\d+)")
_TIMESTAMP_PARAM = re.compile(r"(?<=[=:])(1\d{12})(?=\D|$)")


def parse_json(text):
    """Return parsed JSON, or None if the text isn't JSON (e.g. a login page).

    Some ASP.NET endpoints return JSON wrapped in a JSON string, so unwrap once.
    """
    try:
        data = json.loads(text)
    except (TypeError, ValueError):
        return None
    if isinstance(data, str) and data.strip()[:1] in ("{", "["):
        try:
            data = json.loads(data)
        except ValueError:
            pass
    return data


def _parse_one(value):
    m = _ISO.match(value)
    if m:
        try:
            return date(int(m[1]), int(m[2]), int(m[3]))
        except ValueError:
            return None
    m = _DOTNET.match(value)
    if m:
        return datetime.fromtimestamp(int(m[1]) / 1000, tz=timezone.utc).date()
    return None


def extract_dates(data):
    """Every distinct date found in string values anywhere in the JSON, sorted."""
    found = set()
    stack = [data]
    while stack:
        item = stack.pop()
        if isinstance(item, dict):
            stack.extend(item.values())
        elif isinstance(item, list):
            stack.extend(item)
        elif isinstance(item, str):
            d = _parse_one(item)
            if d:
                found.add(d)
    return sorted(found)


def filter_dates(dates, earliest, latest):
    return [d for d in dates if (earliest is None or d >= earliest) and (latest is None or d <= latest)]


def shape(data):
    """A rough fingerprint of a response, used to notice error payloads."""
    if isinstance(data, dict):
        return sorted(data.keys())
    return type(data).__name__


def shape_matches(learned, current):
    if isinstance(learned, list):
        return isinstance(current, list) and set(learned) <= set(current)
    return learned == current


def refresh_timestamps(text, now_ms):
    """Swap cache-busting millisecond timestamps (e.g. cacheString=1727...) for a fresh one."""
    if not text:
        return text
    return _TIMESTAMP_PARAM.sub(str(now_ms), text)


def fmt(d):
    return d.strftime("%a %d %b %Y")
