"""File-based cache with TTL. SHA-256 hashed keys."""

import json
import time
import hashlib
from pathlib import Path
from typing import Optional


class FileCache:
    """Local filesystem cache. Thread-safe for single-process use."""

    def __init__(self, cache_dir: str = "cache", default_ttl: int = 3600):
        self._dir = Path(cache_dir)
        self._dir.mkdir(parents=True, exist_ok=True)
        self._default_ttl = default_ttl

    def _key_path(self, key: str) -> Path:
        hashed = hashlib.sha256(key.encode()).hexdigest()[:16]
        return self._dir / f"{hashed}.json"

    def get(self, key: str) -> Optional[dict]:
        path = self._key_path(key)
        if not path.exists():
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                entry = json.load(f)
            age = time.time() - entry["created_at"]
            if age > entry.get("ttl", self._default_ttl):
                path.unlink(missing_ok=True)
                return None
            return entry.get("value")
        except (json.JSONDecodeError, KeyError, OSError):
            return None

    def set(self, key: str, value: object, ttl: int = 3600) -> None:
        entry = {
            "key": key,
            "value": value,
            "created_at": time.time(),
            "ttl": ttl,
        }
        try:
            with open(self._key_path(key), "w", encoding="utf-8") as f:
                json.dump(entry, f, ensure_ascii=False)
        except OSError:
            pass  # Cache write failure is non-fatal
