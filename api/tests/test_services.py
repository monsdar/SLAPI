from pathlib import Path
from tempfile import TemporaryDirectory

from django.test import SimpleTestCase

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

