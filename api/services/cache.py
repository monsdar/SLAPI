from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from typing import Any

from django.conf import settings


class FileCache:
    """
    Minimal JSON file cache used to persist upstream responses.
    Cached entries expire after CACHE_RETENTION_TIME_MIN minutes.
    """

    def __init__(self, directory: Path | str | None = None) -> None:
        self.directory = Path(directory or settings.SLAPI_CACHE_DIRECTORY)
        self.directory.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self.retention_time_seconds = settings.CACHE_RETENTION_TIME_MIN * 60

    def _path_for(self, key: str) -> Path:
        safe_key = key.replace("/", "_")
        return self.directory / f"{safe_key}.json"

    def read(self, key: str) -> Any | None:
        path = self._path_for(key)
        if not path.exists():
            return None
        
        # Check if cache has expired using file modification time
        file_mtime = path.stat().st_mtime
        current_time = time.time()
        if current_time - file_mtime > self.retention_time_seconds:
            # Cache expired, delete and return None
            self.delete(key)
            return None
        
        with self._lock:
            with path.open("r", encoding="utf-8") as handle:
                return json.load(handle)

    def write(self, key: str, value: Any) -> None:
        path = self._path_for(key)
        with self._lock:
            with path.open("w", encoding="utf-8") as handle:
                json.dump(value, handle, ensure_ascii=False, indent=2)

    def delete(self, key: str) -> None:
        path = self._path_for(key)
        if path.exists():
            path.unlink()

