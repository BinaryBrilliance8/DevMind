"""Small TTL cache used only as a reproducible integration-test repository."""

from collections.abc import Callable
from time import monotonic


class TTLCache:
    def __init__(self, clock: Callable[[], float] = monotonic):
        self.clock = clock
        self.entries: dict[str, tuple[float, object]] = {}

    def put(self, key: str, value: object, ttl: float) -> None:
        if ttl < 0:
            raise ValueError("TTL cannot be negative")
        self.entries[key] = (self.clock() + ttl, value)

    def get(self, key: str) -> object | None:
        if key not in self.entries:
            return None
        expiry, value = self.entries[key]
        if self.clock() > expiry:
            del self.entries[key]
            return None
        return value
