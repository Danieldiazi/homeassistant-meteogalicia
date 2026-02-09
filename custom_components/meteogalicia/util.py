"""Utility helpers for MeteoGalicia integration."""
from __future__ import annotations

import logging

_LOGGER = logging.getLogger(__name__)


async def safe_close_coordinators(coordinators):
    """Close coordinators safely, logging any issues."""
    if not coordinators:
        _LOGGER.debug("No coordinators to close")
        return
    _LOGGER.debug("Closing %d coordinator(s)", len(coordinators))
    for coordinator in list(coordinators):
        if not hasattr(coordinator, "async_close"):
            _LOGGER.debug(
                "Skipping coordinator without async_close: %s",
                type(coordinator).__name__,
            )
            continue
        label = type(coordinator).__name__
        name = getattr(coordinator, "name", None)
        if name:
            label = f"{label}({name})"
        _LOGGER.debug("Closing coordinator: %s", label)
        try:
            await coordinator.async_close()
            _LOGGER.debug("Closed coordinator: %s", label)
        except Exception as err:  # pylint: disable=broad-except
            _LOGGER.warning(
                "Error closing coordinator: %s (%s)", label, err, exc_info=True
            )
    coordinators.clear()
    _LOGGER.debug("Coordinator list cleared")
