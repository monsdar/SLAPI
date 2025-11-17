from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch

from django.test import TestCase, SimpleTestCase, override_settings

from api.services.cache import FileCache
from api.services.client import TeamSLClient
from api.services.service import TeamSLService


class TeamSLServiceStandingsTests(SimpleTestCase):
    """Tests for standings functionality in TeamSLService."""

    def test_get_standings_uses_cache_after_first_fetch(self):
        """Test that standings are cached after first fetch."""
        class DummyClient:
            def __init__(self):
                self.call_count = 0

            def fetch_standings(self, league_id):
                self.call_count += 1
                return {
                    "status": 0,
                    "data": {
                        "tabelle": {
                            "entries": [
                                {
                                    "s": 5,
                                    "n": 2,
                                    "koerbe": 500,
                                    "gegenKoerbe": 450,
                                    "korbdiff": 50,
                                    "anzGewinnpunkte": 10,
                                    "anzVerlustpunkte": 4,
                                    "team": {
                                        "teamname": "Test Team",
                                        "clubId": 123,
                                        "seasonTeamId": 456,
                                    }
                                }
                            ]
                        }
                    }
                }

        with TemporaryDirectory() as directory:
            cache = FileCache(Path(directory))
            client = DummyClient()
            service = TeamSLService(cache=cache, client=client)

            first = service.get_standings("12345")
            second = service.get_standings("12345")

            self.assertEqual(first["league_id"], second["league_id"])
            self.assertEqual(len(first["standings"]), len(second["standings"]))
            self.assertEqual(client.call_count, 1)

    def test_get_standings_bypasses_cache_when_requested(self):
        """Test that cache can be bypassed when requested."""
        class DummyClient:
            def __init__(self):
                self.call_count = 0

            def fetch_standings(self, league_id):
                self.call_count += 1
                return {
                    "status": 0,
                    "data": {
                        "tabelle": {
                            "entries": [
                                {
                                    "s": self.call_count,
                                    "n": 0,
                                    "team": {"teamname": f"Team {self.call_count}"}
                                }
                            ]
                        }
                    }
                }

        with TemporaryDirectory() as directory:
            cache = FileCache(Path(directory))
            client = DummyClient()
            service = TeamSLService(cache=cache, client=client)

            first = service.get_standings("12345", use_cache=False)
            second = service.get_standings("12345", use_cache=False)

            self.assertNotEqual(first["standings"][0]["wins"], second["standings"][0]["wins"])
            self.assertEqual(client.call_count, 2)

    def test_normalize_standings_extracts_all_fields(self):
        """Test that normalization extracts all expected fields from API response."""
        raw_data = {
            "status": 0,
            "data": {
                "tabelle": {
                    "entries": [
                        {
                            "s": 8,
                            "n": 2,
                            "koerbe": 750,
                            "gegenKoerbe": 680,
                            "korbdiff": 70,
                            "anzGewinnpunkte": 16,
                            "anzVerlustpunkte": 4,
                            "team": {
                                "teamname": "Team Alpha",
                                "teamnameSmall": "Alpha",
                                "clubId": 100,
                                "teamPermanentId": 200,
                                "seasonTeamId": 300,
                            }
                        },
                        {
                            "s": 5,
                            "n": 5,
                            "koerbe": 600,
                            "gegenKoerbe": 600,
                            "korbdiff": 0,
                            "anzGewinnpunkte": 10,
                            "anzVerlustpunkte": 10,
                            "team": {
                                "teamname": "Team Beta",
                                "clubId": 101,
                                "seasonTeamId": 301,
                            }
                        }
                    ]
                }
            }
        }

        result = TeamSLService._normalize_standings(raw_data, "12345")

        self.assertEqual(result["league_id"], "12345")
        self.assertEqual(len(result["standings"]), 2)

        # Check first team
        first = result["standings"][0]
        self.assertEqual(first["position"], 1)
        self.assertEqual(first["wins"], 8)
        self.assertEqual(first["losses"], 2)
        self.assertEqual(first["points_for"], 750)
        self.assertEqual(first["points_against"], 680)
        self.assertEqual(first["point_difference"], 70)
        self.assertEqual(first["win_points"], 16)
        self.assertEqual(first["loss_points"], 4)
        self.assertEqual(first["team"]["name"], "Team Alpha")
        self.assertEqual(first["team"]["club_id"], 100)
        self.assertEqual(first["team"]["team_permanent_id"], 200)
        self.assertEqual(first["team"]["season_team_id"], 300)

        # Check second team
        second = result["standings"][1]
        self.assertEqual(second["position"], 2)
        self.assertEqual(second["wins"], 5)
        self.assertEqual(second["losses"], 5)
        self.assertEqual(second["point_difference"], 0)

    def test_normalize_standings_handles_missing_fields(self):
        """Test that normalization handles missing optional fields gracefully."""
        raw_data = {
            "status": 0,
            "data": {
                "tabelle": {
                    "entries": [
                        {
                            "s": 3,
                            "n": 1,
                            "team": {
                                "teamname": "Team Gamma"
                            }
                        }
                    ]
                }
            }
        }

        result = TeamSLService._normalize_standings(raw_data, "99999")

        self.assertEqual(len(result["standings"]), 1)
        standing = result["standings"][0]
        self.assertEqual(standing["wins"], 3)
        self.assertEqual(standing["losses"], 1)
        self.assertIsNone(standing["points_for"])
        self.assertIsNone(standing["points_against"])
        self.assertIsNone(standing["point_difference"])
        self.assertEqual(standing["team"]["name"], "Team Gamma")

    def test_normalize_standings_handles_empty_entries(self):
        """Test that normalization handles empty standings gracefully."""
        raw_data = {
            "status": 0,
            "data": {
                "tabelle": {
                    "entries": []
                }
            }
        }

        result = TeamSLService._normalize_standings(raw_data, "12345")

        self.assertEqual(result["league_id"], "12345")
        self.assertEqual(len(result["standings"]), 0)


class TeamSLClientStandingsTests(SimpleTestCase):
    """Tests for standings functionality in TeamSLClient."""

    @patch('api.services.client.httpx.Client')
    def test_fetch_standings_makes_correct_request(self, mock_client_class):
        """Test that fetch_standings makes the correct HTTP request."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "status": 0,
            "data": {"tabelle": {"entries": []}}
        }
        mock_response.raise_for_status = Mock()

        mock_client_instance = Mock()
        mock_client_instance.get.return_value = mock_response
        mock_client_class.return_value = mock_client_instance

        client = TeamSLClient(base_url="https://www.basketball-bund.net")
        result = client.fetch_standings("48714")

        mock_client_instance.get.assert_called_once_with("/rest/competition/actual/id/48714")
        self.assertEqual(result["status"], 0)

    @patch('api.services.client.httpx.Client')
    def test_fetch_standings_raises_on_non_zero_status(self, mock_client_class):
        """Test that fetch_standings raises ValueError on API error."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "status": 1,
            "message": "League not found"
        }
        mock_response.raise_for_status = Mock()

        mock_client_instance = Mock()
        mock_client_instance.get.return_value = mock_response
        mock_client_class.return_value = mock_client_instance

        client = TeamSLClient(base_url="https://www.basketball-bund.net")

        with self.assertRaises(ValueError) as context:
            client.fetch_standings("99999")

        self.assertIn("API error", str(context.exception))
        self.assertIn("League not found", str(context.exception))

    @patch('api.services.client.httpx.Client')
    def test_fetch_standings_handles_string_status(self, mock_client_class):
        """Test that fetch_standings handles status returned as string instead of int."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "status": "0",
            "data": {"tabelle": {"entries": []}}
        }
        mock_response.raise_for_status = Mock()

        mock_client_instance = Mock()
        mock_client_instance.get.return_value = mock_response
        mock_client_class.return_value = mock_client_instance

        client = TeamSLClient(base_url="https://www.basketball-bund.net")
        result = client.fetch_standings("48714")

        # Should not raise an error even though status is a string "0"
        self.assertEqual(result["status"], "0")
        self.assertIn("data", result)

    def test_fetch_standings_extracts_base_url_correctly(self):
        """Test that base URL is extracted correctly from configured URL."""
        client = TeamSLClient(base_url="https://www.basketball-bund.net/static/#/ligaauswahl")
        self.assertEqual(client.base_url, "https://www.basketball-bund.net")


@override_settings(SLAPI_API_TOKEN=None)
class StandingsEndpointTests(TestCase):
    """Tests for the standings API endpoint."""

    def test_standings_endpoint_returns_standings(self):
        """Test that the standings endpoint returns properly formatted data."""
        # Mock the service to return test data
        with patch('api.api.service') as mock_service:
            mock_service.get_standings.return_value = {
                "league_id": "12345",
                "standings": [
                    {
                        "position": 1,
                        "team": {
                            "id": "1",
                            "name": "Team A",
                            "club_id": 100,
                        },
                        "wins": 5,
                        "losses": 2,
                        "points_for": 500,
                        "points_against": 450,
                        "point_difference": 50,
                        "win_points": 10,
                        "loss_points": 4,
                    }
                ]
            }

            response = self.client.get("/leagues/12345/standings")

            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertEqual(data["league_id"], "12345")
            self.assertEqual(len(data["standings"]), 1)
            self.assertEqual(data["standings"][0]["position"], 1)
            self.assertEqual(data["standings"][0]["wins"], 5)
            self.assertEqual(data["standings"][0]["losses"], 2)
            self.assertEqual(data["standings"][0]["team"]["name"], "Team A")

    def test_standings_endpoint_respects_use_cache_parameter(self):
        """Test that the use_cache parameter is passed to the service."""
        with patch('api.api.service') as mock_service:
            mock_service.get_standings.return_value = {
                "league_id": "12345",
                "standings": []
            }

            response = self.client.get("/leagues/12345/standings?use_cache=false")

            self.assertEqual(response.status_code, 200)
            mock_service.get_standings.assert_called_once_with("12345", use_cache=False)

