from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch

from django.test import TestCase, SimpleTestCase

from api.services.cache import FileCache
from api.services.client import TeamSLClient
from api.services.service import TeamSLService


class TeamSLServiceMatchesTests(SimpleTestCase):
    """Tests for matches functionality in TeamSLService."""

    def test_get_matches_uses_cache_after_first_fetch(self):
        """Test that matches are cached after first fetch."""
        class DummyClient:
            def __init__(self):
                self.call_count = 0

            def fetch_matches(self, league_id):
                self.call_count += 1
                return {
                    "status": 0,
                    "data": {
                        "matches": [
                            {
                                "matchId": 12345,
                                "matchDay": 1,
                                "matchNo": 1,
                                "kickoffDate": "2025-09-13",
                                "kickoffTime": "09:00",
                                "homeTeam": {
                                    "teamname": "Home Team",
                                    "clubId": 100,
                                    "seasonTeamId": 200,
                                },
                                "guestTeam": {
                                    "teamname": "Away Team",
                                    "clubId": 101,
                                    "seasonTeamId": 201,
                                },
                                "result": "76:64",
                                "ergebnisbestaetigt": True,
                                "abgesagt": False,
                            }
                        ]
                    }
                }

        with TemporaryDirectory() as directory:
            cache = FileCache(Path(directory))
            client = DummyClient()
            service = TeamSLService(cache=cache, client=client)

            first = service.get_matches("12345")
            second = service.get_matches("12345")

            self.assertEqual(first["league_id"], second["league_id"])
            self.assertEqual(len(first["matches"]), len(second["matches"]))
            self.assertEqual(client.call_count, 1)

    def test_get_matches_bypasses_cache_when_requested(self):
        """Test that cache can be bypassed when requested."""
        class DummyClient:
            def __init__(self):
                self.call_count = 0

            def fetch_matches(self, league_id):
                self.call_count += 1
                return {
                    "status": 0,
                    "data": {
                        "matches": [
                            {
                                "matchId": self.call_count,
                                "matchDay": 1,
                                "matchNo": 1,
                                "kickoffDate": "2025-09-13",
                                "kickoffTime": "09:00",
                                "homeTeam": {"teamname": f"Team {self.call_count}"},
                                "guestTeam": {"teamname": "Away Team"},
                            }
                        ]
                    }
                }

        with TemporaryDirectory() as directory:
            cache = FileCache(Path(directory))
            client = DummyClient()
            service = TeamSLService(cache=cache, client=client)

            first = service.get_matches("12345", use_cache=False)
            second = service.get_matches("12345", use_cache=False)

            self.assertNotEqual(first["matches"][0]["match_id"], second["matches"][0]["match_id"])
            self.assertEqual(client.call_count, 2)

    def test_normalize_matches_extracts_all_fields(self):
        """Test that normalization extracts all expected fields from API response."""
        raw_data = {
            "status": 0,
            "data": {
                "matches": [
                    {
                        "matchId": 2688136,
                        "matchDay": 1,
                        "matchNo": 8303,
                        "kickoffDate": "2025-09-13",
                        "kickoffTime": "09:00",
                        "homeTeam": {
                            "teamname": "TuS Huchting",
                            "teamnameSmall": "Huchting",
                            "clubId": 153,
                            "teamPermanentId": 1000,
                            "seasonTeamId": 2000,
                        },
                        "guestTeam": {
                            "teamname": "TV Delmenhorst",
                            "clubId": 1342,
                            "seasonTeamId": 2001,
                        },
                        "result": "76:64",
                        "ergebnisbestaetigt": True,
                        "abgesagt": False,
                    },
                    {
                        "matchId": 2688137,
                        "matchDay": 1,
                        "matchNo": 8304,
                        "kickoffDate": "2025-09-20",
                        "kickoffTime": "18:00",
                        "homeTeam": {
                            "teamname": "Team A",
                            "clubId": 200,
                        },
                        "guestTeam": {
                            "teamname": "Team B",
                            "clubId": 201,
                        },
                        "result": None,
                        "ergebnisbestaetigt": False,
                        "abgesagt": False,
                    }
                ]
            }
        }

        result = TeamSLService._normalize_matches(raw_data, "48714")

        self.assertEqual(result["league_id"], "48714")
        self.assertEqual(len(result["matches"]), 2)

        # Check first match (finished)
        first = result["matches"][0]
        self.assertEqual(first["match_id"], 2688136)
        self.assertEqual(first["match_day"], 1)
        self.assertEqual(first["match_no"], 8303)
        self.assertIsInstance(first["datetime"], datetime)
        self.assertEqual(first["datetime"].strftime("%Y-%m-%d %H:%M"), "2025-09-13 09:00")
        self.assertEqual(first["home_team"]["name"], "TuS Huchting")
        self.assertEqual(first["home_team"]["club_id"], 153)
        self.assertEqual(first["away_team"]["name"], "TV Delmenhorst")
        self.assertEqual(first["score"], "76:64")
        self.assertTrue(first["is_finished"])
        self.assertTrue(first["is_confirmed"])
        self.assertFalse(first["is_cancelled"])

        # Check second match (scheduled)
        second = result["matches"][1]
        self.assertEqual(second["match_id"], 2688137)
        self.assertIsInstance(second["datetime"], datetime)
        self.assertEqual(second["datetime"].strftime("%Y-%m-%d %H:%M"), "2025-09-20 18:00")
        self.assertIsNone(second["score"])
        self.assertFalse(second["is_finished"])
        self.assertFalse(second["is_confirmed"])

    def test_normalize_matches_handles_missing_fields(self):
        """Test that normalization handles missing optional fields gracefully."""
        raw_data = {
            "status": 0,
            "data": {
                "matches": [
                    {
                        "matchId": 12345,
                        "matchDay": 1,
                        "kickoffDate": "2025-09-13",
                        "homeTeam": {"teamname": "Home Team"},
                        "guestTeam": {"teamname": "Away Team"},
                    }
                ]
            }
        }

        result = TeamSLService._normalize_matches(raw_data, "99999")

        self.assertEqual(len(result["matches"]), 1)
        match = result["matches"][0]
        self.assertEqual(match["match_id"], 12345)
        self.assertEqual(match["match_day"], 1)
        self.assertEqual(match["match_no"], 0)  # Default value
        self.assertIsNone(match["score"])
        self.assertFalse(match["is_finished"])
        self.assertFalse(match["is_confirmed"])
        self.assertFalse(match["is_cancelled"])
        self.assertIsNone(match["location"])

    def test_normalize_matches_handles_cancelled_matches(self):
        """Test that normalization correctly identifies cancelled matches."""
        raw_data = {
            "status": 0,
            "data": {
                "matches": [
                    {
                        "matchId": 12345,
                        "matchDay": 1,
                        "matchNo": 1,
                        "kickoffDate": "2025-09-13",
                        "kickoffTime": "09:00",
                        "homeTeam": {"teamname": "Home Team"},
                        "guestTeam": {"teamname": "Away Team"},
                        "result": None,
                        "ergebnisbestaetigt": False,
                        "abgesagt": True,
                    }
                ]
            }
        }

        result = TeamSLService._normalize_matches(raw_data, "12345")

        self.assertEqual(len(result["matches"]), 1)
        match = result["matches"][0]
        self.assertTrue(match["is_cancelled"])
        self.assertFalse(match["is_finished"])

    def test_normalize_matches_handles_empty_matches(self):
        """Test that normalization handles empty matches list gracefully."""
        raw_data = {
            "status": 0,
            "data": {
                "matches": []
            }
        }

        result = TeamSLService._normalize_matches(raw_data, "12345")

        self.assertEqual(result["league_id"], "12345")
        self.assertEqual(len(result["matches"]), 0)

    def test_normalize_matches_handles_date_only(self):
        """Test that normalization handles matches with date but no time."""
        raw_data = {
            "status": 0,
            "data": {
                "matches": [
                    {
                        "matchId": 12345,
                        "matchDay": 1,
                        "matchNo": 1,
                        "kickoffDate": "2025-09-13",
                        "kickoffTime": None,
                        "homeTeam": {"teamname": "Home Team"},
                        "guestTeam": {"teamname": "Away Team"},
                    }
                ]
            }
        }

        result = TeamSLService._normalize_matches(raw_data, "12345")

        self.assertEqual(len(result["matches"]), 1)
        match = result["matches"][0]
        self.assertIsInstance(match["datetime"], datetime)
        self.assertEqual(match["datetime"].strftime("%Y-%m-%d"), "2025-09-13")


class TeamSLClientMatchesTests(SimpleTestCase):
    """Tests for matches functionality in TeamSLClient."""

    @patch('api.services.client.httpx.Client')
    def test_fetch_matches_makes_correct_request(self, mock_client_class):
        """Test that fetch_matches makes the correct HTTP request."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "status": 0,
            "data": {"matches": []}
        }
        mock_response.raise_for_status = Mock()

        mock_client_instance = Mock()
        mock_client_instance.get.return_value = mock_response
        mock_client_class.return_value = mock_client_instance

        client = TeamSLClient(base_url="https://www.basketball-bund.net")
        result = client.fetch_matches("48714")

        mock_client_instance.get.assert_called_once_with("/rest/competition/spielplan/id/48714")
        self.assertEqual(result["status"], 0)

    @patch('api.services.client.httpx.Client')
    def test_fetch_matches_raises_on_non_zero_status(self, mock_client_class):
        """Test that fetch_matches raises ValueError on API error."""
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
            client.fetch_matches("99999")

        self.assertIn("API error", str(context.exception))
        self.assertIn("League not found", str(context.exception))

    @patch('api.services.client.httpx.Client')
    def test_fetch_matches_handles_string_status(self, mock_client_class):
        """Test that fetch_matches handles status returned as string instead of int."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "status": "0",
            "data": {"matches": []}
        }
        mock_response.raise_for_status = Mock()

        mock_client_instance = Mock()
        mock_client_instance.get.return_value = mock_response
        mock_client_class.return_value = mock_client_instance

        client = TeamSLClient(base_url="https://www.basketball-bund.net")
        result = client.fetch_matches("48714")

        # Should not raise an error even though status is a string "0"
        self.assertEqual(result["status"], "0")
        self.assertIn("data", result)


class MatchesEndpointTests(TestCase):
    """Tests for the matches API endpoint."""

    def test_matches_endpoint_returns_matches(self):
        """Test that the matches endpoint returns properly formatted data."""
        # Mock the service to return test data
        with patch('api.api.service') as mock_service:
            mock_service.get_matches.return_value = {
                "league_id": "12345",
                "matches": [
                    {
                        "match_id": 2688136,
                        "match_day": 1,
                        "match_no": 8303,
                        "datetime": datetime(2025, 9, 13, 9, 0),
                        "home_team": {
                            "id": "2000",
                            "name": "Home Team",
                            "club_id": 100,
                        },
                        "away_team": {
                            "id": "2001",
                            "name": "Away Team",
                            "club_id": 101,
                        },
                        "location": None,
                        "score": "76:64",
                        "is_finished": True,
                        "is_confirmed": True,
                        "is_cancelled": False,
                    }
                ]
            }

            response = self.client.get("/leagues/12345/matches")

            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertEqual(data["league_id"], "12345")
            self.assertEqual(len(data["matches"]), 1)
            self.assertEqual(data["matches"][0]["match_id"], 2688136)
            self.assertEqual(data["matches"][0]["match_day"], 1)
            self.assertEqual(data["matches"][0]["home_team"]["name"], "Home Team")
            self.assertEqual(data["matches"][0]["away_team"]["name"], "Away Team")
            self.assertEqual(data["matches"][0]["score"], "76:64")
            self.assertTrue(data["matches"][0]["is_finished"])
            self.assertTrue(data["matches"][0]["is_confirmed"])

    def test_matches_endpoint_respects_use_cache_parameter(self):
        """Test that the use_cache parameter is passed to the service."""
        with patch('api.api.service') as mock_service:
            mock_service.get_matches.return_value = {
                "league_id": "12345",
                "matches": []
            }

            response = self.client.get("/leagues/12345/matches?use_cache=false")

            self.assertEqual(response.status_code, 200)
            mock_service.get_matches.assert_called_once_with("12345", use_cache=False)

    def test_matches_endpoint_distinguishes_finished_and_future_matches(self):
        """Test that the endpoint correctly distinguishes finished and future matches."""
        with patch('api.api.service') as mock_service:
            mock_service.get_matches.return_value = {
                "league_id": "12345",
                "matches": [
                    {
                        "match_id": 1,
                        "match_day": 1,
                        "match_no": 1,
                        "datetime": datetime(2025, 9, 13, 9, 0),
                        "home_team": {"id": "1", "name": "Home Team"},
                        "away_team": {"id": "2", "name": "Away Team"},
                        "location": None,
                        "score": "76:64",
                        "is_finished": True,
                        "is_confirmed": True,
                        "is_cancelled": False,
                    },
                    {
                        "match_id": 2,
                        "match_day": 2,
                        "match_no": 2,
                        "datetime": datetime(2025, 10, 1, 18, 0),
                        "home_team": {"id": "3", "name": "Future Home"},
                        "away_team": {"id": "4", "name": "Future Away"},
                        "location": "Sports Hall",
                        "score": None,
                        "is_finished": False,
                        "is_confirmed": False,
                        "is_cancelled": False,
                    }
                ]
            }

            response = self.client.get("/leagues/12345/matches")

            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertEqual(len(data["matches"]), 2)
            
            # Check finished match
            finished = data["matches"][0]
            self.assertTrue(finished["is_finished"])
            self.assertIsNotNone(finished["score"])
            
            # Check future match
            future = data["matches"][1]
            self.assertFalse(future["is_finished"])
            self.assertIsNone(future["score"])
            self.assertEqual(future["location"], "Sports Hall")

