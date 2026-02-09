import pytest

from custom_components.meteogalicia.util import safe_close_coordinators


class DummyCoordinator:
    def __init__(self):
        self.closed = False
        self.name = "dummy"

    async def async_close(self):
        self.closed = True


class ExplodingCoordinator:
    async def async_close(self):
        raise RuntimeError("boom")


@pytest.mark.asyncio
async def test_safe_close_coordinators_closes_and_clears():
    c1 = DummyCoordinator()
    c2 = DummyCoordinator()
    coordinators = [c1, c2]

    await safe_close_coordinators(coordinators)

    assert c1.closed is True
    assert c2.closed is True
    assert coordinators == []


@pytest.mark.asyncio
async def test_safe_close_coordinators_continues_on_error():
    c1 = DummyCoordinator()
    c2 = ExplodingCoordinator()
    coordinators = [c1, c2]

    await safe_close_coordinators(coordinators)

    assert c1.closed is True
    assert coordinators == []
