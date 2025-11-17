from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch

from django.test import SimpleTestCase, TestCase

from api.services.cache import FileCache
from api.services.client import TeamSLClient
from api.services.service import TeamSLService


class TeamSLServiceVerbandTests(SimpleTestCase):
    """Tests for association (Verband) functionality in TeamSLService."""

    def test_get_associations_uses_cache_after_first_fetch(self):
        """Service should cache the Verband list after the first fetch."""

        class DummyClient:
            def __init__(self):
                self.call_count = 0

            def fetch_associations(self):
                self.call_count += 1
                return {
                    "status": 0,
                    "data": {
                        "verbaende": [
                            {"id": 7, "label": "Niedersachsen", "hits": 205},
                        ]
                    },
                }

        with TemporaryDirectory() as directory:
            cache = FileCache(Path(directory))
            client = DummyClient()
            service = TeamSLService(cache=cache, client=client)

            first = service.get_associations()
            second = service.get_associations()

            self.assertEqual(first, second)
            self.assertEqual(client.call_count, 1)

    def test_get_associations_bypasses_cache_when_requested(self):
        """Service should bypass the cache when explicitly requested."""

        class DummyClient:
            def __init__(self):
                self.call_count = 0

            def fetch_associations(self):
                self.call_count += 1
                return {
                    "status": 0,
                    "data": {
                        "verbaende": [
                            {"id": self.call_count, "label": f"Verband {self.call_count}", "hits": 10},
                        ]
                    },
                }

        with TemporaryDirectory() as directory:
            cache = FileCache(Path(directory))
            client = DummyClient()
            service = TeamSLService(cache=cache, client=client)

            first = service.get_associations(use_cache=False)
            second = service.get_associations(use_cache=False)

            self.assertNotEqual(first, second)
            self.assertEqual(client.call_count, 2)

    def test_normalize_associations_handles_missing_fields(self):
        """Normalization should handle missing or malformed fields gracefully."""
        raw_data = {
            "status": 0,
            "data": {
                "verbaende": [
                    {"label": "Bundesligen", "hits": "42"},
                    {"id": None, "hits": None},
                ]
            },
        }

        result = TeamSLService._normalize_associations(raw_data)

        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["id"], "unknown")
        self.assertEqual(result[0]["label"], "Bundesligen")
        self.assertEqual(result[0]["hits"], 42)
        self.assertEqual(result[1]["label"], "Unknown Verband")
        self.assertEqual(result[1]["hits"], 0)


class TeamSLClientVerbandTests(SimpleTestCase):
    """Tests for Verband functionality in TeamSLClient."""

    @patch("api.services.client.httpx.Client")
    def test_fetch_associations_posts_json_payload(self, mock_client_class):
        """Client should POST an empty JSON body to fetch Verbände."""
        mock_response = Mock()
        mock_response.json.return_value = {"status": 0, "data": {"verbaende": []}}
        mock_response.raise_for_status = Mock()

        mock_client_instance = Mock()
        mock_client_instance.post.return_value = mock_response
        mock_client_class.return_value = mock_client_instance

        client = TeamSLClient(base_url="https://www.basketball-bund.net")
        result = client.fetch_associations()

        mock_client_instance.post.assert_called_once_with("/rest/wam/data", json={})
        self.assertEqual(result["status"], 0)

    @patch("api.services.client.httpx.Client")
    def test_fetch_associations_raises_on_non_zero_status(self, mock_client_class):
        """Client should raise ValueError when upstream reports an error."""
        mock_response = Mock()
        mock_response.json.return_value = {"status": 1, "message": "Something went wrong"}
        mock_response.raise_for_status = Mock()

        mock_client_instance = Mock()
        mock_client_instance.post.return_value = mock_response
        mock_client_class.return_value = mock_client_instance

        client = TeamSLClient(base_url="https://www.basketball-bund.net")

        with self.assertRaises(ValueError) as context:
            client.fetch_associations()

        self.assertIn("API error", str(context.exception))
        self.assertIn("Something went wrong", str(context.exception))

    @patch("api.services.client.httpx.Client")
    def test_fetch_associations_handles_string_status(self, mock_client_class):
        """Client should handle status returned as string instead of int."""
        mock_response = Mock()
        mock_response.json.return_value = {"status": "0", "data": {"verbaende": []}}
        mock_response.raise_for_status = Mock()

        mock_client_instance = Mock()
        mock_client_instance.post.return_value = mock_response
        mock_client_class.return_value = mock_client_instance

        client = TeamSLClient(base_url="https://www.basketball-bund.net")
        result = client.fetch_associations()

        # Should not raise an error even though status is a string "0"
        self.assertEqual(result["status"], "0")
        self.assertIn("data", result)


class VerbandEndpointTests(TestCase):
    """Tests for the Verband API endpoint."""

    def test_verbaende_endpoint_returns_data(self):
        """Endpoint should return normalized Verbände."""
        with patch("api.api.service") as mock_service:
            mock_service.get_associations.return_value = [
                {"id": "7", "label": "Niedersachsen", "hits": 205},
            ]

            response = self.client.get("/verbaende")

            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertEqual(len(data["verbaende"]), 1)
            self.assertEqual(data["verbaende"][0]["id"], "7")
            self.assertEqual(data["verbaende"][0]["label"], "Niedersachsen")
            self.assertEqual(data["verbaende"][0]["hits"], 205)

    def test_verbaende_endpoint_respects_use_cache_parameter(self):
        """Endpoint should forward the use_cache flag to the service layer."""
        with patch("api.api.service") as mock_service:
            mock_service.get_associations.return_value = []

            response = self.client.get("/verbaende?use_cache=false")

            self.assertEqual(response.status_code, 200)
            mock_service.get_associations.assert_called_once_with(use_cache=False)


