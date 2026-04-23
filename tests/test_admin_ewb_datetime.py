"""Bug A: _to_datetime coerces SQLite-raw-SQL string timestamps to datetime.

Raw SQL (`text()`) bypasses SQLAlchemy's type conversion, so DATETIME
columns return strings. Templates call .strftime() which crashes on strings.
"""
from datetime import datetime

from routes.admin_ewb import _to_datetime


def test_passthrough_datetime():
    dt = datetime(2026, 4, 23, 12, 34, 56)
    assert _to_datetime(dt) is dt


def test_none_stays_none():
    assert _to_datetime(None) is None


def test_iso_with_space_and_microseconds():
    out = _to_datetime('2026-04-23 12:34:56.789012')
    assert isinstance(out, datetime)
    assert out.year == 2026 and out.month == 4 and out.day == 23
    assert out.hour == 12 and out.minute == 34


def test_iso_with_space_no_microseconds():
    out = _to_datetime('2026-04-23 12:34:56')
    assert isinstance(out, datetime)
    assert (out.year, out.month, out.day) == (2026, 4, 23)


def test_iso_with_t_separator():
    out = _to_datetime('2026-04-23T12:34:56')
    assert isinstance(out, datetime)
    assert out.hour == 12


def test_iso_short_form():
    out = _to_datetime('2026-04-23 12:34')
    assert isinstance(out, datetime)
    assert out.minute == 34


def test_unparseable_string_returns_none():
    assert _to_datetime('not a date') is None


def test_non_string_non_datetime_returns_none():
    assert _to_datetime(12345) is None
    assert _to_datetime([]) is None


def test_output_supports_strftime():
    """Regression guard: coerced output must support .strftime() — the template calls it."""
    out = _to_datetime('2026-04-23 12:34:56')
    assert out.strftime('%Y-%m-%d %H:%M') == '2026-04-23 12:34'
