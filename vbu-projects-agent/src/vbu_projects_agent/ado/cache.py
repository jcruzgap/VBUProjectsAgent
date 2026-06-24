"""In-memory ADO response cache with TTL."""
from __future__ import annotations

import hashlib
import json
import time
from typing import Optional


class AdoCache:
    def __init__(self, ttl_seconds: int = 900) -> None:
        self.ttl = ttl_seconds
        self._store: dict[str, tuple[float, list]] = {}

    def _key(self, project_id: str, wiql: str, field_map_hash: str,
             api_version: str) -> str:
        raw = f"{project_id}|{wiql}|{field_map_hash}|{api_version}"
        return hashlib.sha256(raw.encode()).hexdigest()

    def get(self, project_id: str, wiql: str, field_map_hash: str,
            api_version: str) -> Optional[list]:
        key = self._key(project_id, wiql, field_map_hash, api_version)
        if key not in self._store:
            return None
        ts, items = self._store[key]
        if time.time() - ts > self.ttl:
            del self._store[key]
            return None
        return items

    def set(self, project_id: str, wiql: str, field_map_hash: str,
            api_version: str, items: list) -> None:
        key = self._key(project_id, wiql, field_map_hash, api_version)
        self._store[key] = (time.time(), items)

    def invalidate(self, project_id: str | None = None) -> None:
        if project_id is None:
            self._store.clear()
        else:
            to_remove = [k for k in self._store]
            # Can't key-filter without project_id in key — clear all for safety
            self._store.clear()


_global_cache: AdoCache | None = None


def get_cache(ttl_seconds: int = 900) -> AdoCache:
    global _global_cache
    if _global_cache is None:
        _global_cache = AdoCache(ttl_seconds)
    return _global_cache
