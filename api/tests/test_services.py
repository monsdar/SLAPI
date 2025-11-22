import os
import time
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.test import SimpleTestCase, override_settings

from api.services.cache import FileCache
from api.services.service import TeamSLService


class FileCacheTests(SimpleTestCase):
    def test_write_read_and_delete(self):
        with TemporaryDirectory() as directory:
            cache = FileCache(Path(directory))
            cache.write("sample-key", {"value": 42})

            self.assertEqual(cache.read("sample-key"), {"value": 42})

            cache.delete("sample-key")
            self.assertIsNone(cache.read("sample-key"))

    @override_settings(CACHE_RETENTION_TIME_MIN=1)
    def test_cache_expires_after_retention_time(self):
        """Test that cache entries expire after the configured retention time."""
        with TemporaryDirectory() as directory:
            cache = FileCache(Path(directory))
            cache.write("expire-key", {"value": 100})
            
            # Immediately reading should return the value
            self.assertEqual(cache.read("expire-key"), {"value": 100})
            
            # Mock time to simulate cache expiration (61 seconds = 1 minute + 1 second)
            with patch('time.time', return_value=time.time() + 61):
                result = cache.read("expire-key")
                self.assertIsNone(result)
            
            # Verify the cache file was deleted
            self.assertIsNone(cache.read("expire-key"))

    @override_settings(CACHE_RETENTION_TIME_MIN=2)
    def test_cache_not_expires_within_retention_time(self):
        """Test that cache entries don't expire within the retention time."""
        with TemporaryDirectory() as directory:
            cache = FileCache(Path(directory))
            cache.write("valid-key", {"value": 200})
            
            # Mock time to simulate 1 minute passing (less than 2 minute retention)
            with patch('time.time', return_value=time.time() + 60):
                result = cache.read("valid-key")
                self.assertEqual(result, {"value": 200})

    @override_settings(CACHE_RETENTION_TIME_MIN=1)
    def test_old_cache_files_expire_based_on_mtime(self):
        """Test that old cache files expire based on filesystem modification time."""
        with TemporaryDirectory() as directory:
            cache = FileCache(Path(directory))
            # Create an old cache file
            path = cache._path_for("old-file-key")
            with path.open("w", encoding="utf-8") as f:
                import json
                json.dump({"value": 300}, f)
            
            # Modify the file's mtime to be 2 minutes old
            old_time = time.time() - 120  # 2 minutes ago
            os.utime(path, (old_time, old_time))
            
            # Reading should return None and delete the file (expired)
            result = cache.read("old-file-key")
            self.assertIsNone(result)
            self.assertFalse(path.exists())


class TeamSLServiceTests(SimpleTestCase):
    def test_get_leagues_uses_cache_after_first_fetch(self):
        class DummyClient:
            def __init__(self):
                self.call_count = 0

            def fetch_leagues(self):
                self.call_count += 1
                return [{"id": "l1", "name": "League 1"}]

        with TemporaryDirectory() as directory:
            cache = FileCache(Path(directory))
            client = DummyClient()
            service = TeamSLService(cache=cache, client=client)

            first = service.get_leagues()
            second = service.get_leagues()

            self.assertEqual(first, second)
            self.assertEqual(client.call_count, 1)

    def test_get_leagues_bypasses_cache_when_requested(self):
        class DummyClient:
            def __init__(self):
                self.call_count = 0

            def fetch_leagues(self):
                self.call_count += 1
                return [{"id": f"l{self.call_count}", "name": "League"}]

        with TemporaryDirectory() as directory:
            cache = FileCache(Path(directory))
            client = DummyClient()
            service = TeamSLService(cache=cache, client=client)

            first = service.get_leagues(use_cache=False)
            second = service.get_leagues(use_cache=False)

            self.assertNotEqual(first, second)
            self.assertEqual(client.call_count, 2)

