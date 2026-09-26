"""Resolve polling options while preserving explicitly configured legacy values."""

from datetime import timedelta

from homeassistant.const import CONF_SCAN_INTERVAL

from .const import DEFAULT_INTERVALS


def merge_entry_data(entry) -> dict:
    """Merge options, retaining a cleared interval as an explicit default choice."""
    data = dict(entry.data)
    for key, value in entry.options.items():
        if value in ("", None):
            if key in DEFAULT_INTERVALS:
                data[key] = None
            else:
                data.pop(key, None)
        else:
            data[key] = value
    return data


def get_scan_interval(data: dict, key: str) -> int | float:
    """Prefer a service option, then legacy scan_interval, then our default.

    A service option explicitly set to None restores that service's default,
    even when an old scan_interval remains in the imported entry data.
    """
    value = data.get(key, data.get(CONF_SCAN_INTERVAL))
    if value is None:
        return DEFAULT_INTERVALS[key]
    if isinstance(value, timedelta):
        return value.total_seconds()
    return value
