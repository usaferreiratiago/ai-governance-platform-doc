import time
from typing import Any, Dict, Optional

class SimpleTTLCache:
    def __init__(self, ttl_seconds: int = 300):
        self.ttl_seconds = ttl_seconds
        self._store: Dict[str, Dict[str, Any]] = {}

    def get(self, key: str) -> Optional[Any]:
        item = self._store.get(key)

        if not item:
            return None

        if time.time() > item['expires_at']:
            del self._store[key]
            return None

        return item['value']

    def set(self, key: str, value: Any):
        self._store[key] = {
            'value': value,
            'expires_at': time.time() + self.ttl_seconds,
        }

    def clear(self):
        self._store.clear()

# Shared cache instance
cache = SimpleTTLCache(ttl_seconds=300)