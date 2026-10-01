from datetime import date

from watcher.dates import extract_dates, filter_dates, parse_json, refresh_timestamps, shape, shape_matches


def test_extracts_iso_and_dotnet_dates_from_nested_json():
    data = {"ScheduleDays": [{"Date": "2026-11-04T00:00:00"}, {"Date": "2026-11-06"}], "x": "/Date(1798761600000)/"}
    assert extract_dates(data) == [date(2026, 11, 4), date(2026, 11, 6), date(2027, 1, 1)]


def test_ignores_non_dates_and_invalid_dates():
    assert extract_dates({"a": "hello", "b": 2026, "c": "2026-13-40", "d": None}) == []


def test_parse_json_handles_html_and_double_encoded_json():
    assert parse_json("<html>Login</html>") is None
    assert parse_json('"{\\"a\\": [1]}"') == {"a": [1]}


def test_filter_window_is_inclusive():
    ds = [date(2026, 10, 1), date(2026, 10, 5), date(2026, 12, 31), date(2027, 1, 1)]
    assert filter_dates(ds, date(2026, 10, 5), date(2026, 12, 31)) == [date(2026, 10, 5), date(2026, 12, 31)]


def test_refresh_timestamps_replaces_cache_busters_only():
    url = "https://x/custom-actions/?route=/api/v1/days&cacheString=1727740800123&postId=123"
    assert refresh_timestamps(url, 1800000000000) == url.replace("1727740800123", "1800000000000")
    assert refresh_timestamps('{"t":1727740800123,"id":42}', 1800000000000) == '{"t":1800000000000,"id":42}'
    assert refresh_timestamps(None, 1) is None


def test_shape_detects_error_payloads():
    learned = shape({"ScheduleDays": [], "Status": 1})
    assert shape_matches(learned, shape({"ScheduleDays": [], "Status": 1, "Extra": 0}))
    assert not shape_matches(learned, shape({"error": "unauthorized"}))
    assert shape_matches(shape([1]), shape([]))
    assert not shape_matches(shape([1]), shape({"a": 1}))
