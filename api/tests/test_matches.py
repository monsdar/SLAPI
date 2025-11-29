from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch
from zoneinfo import ZoneInfo

from django.test import TestCase, SimpleTestCase, override_settings

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

            def fetch_matches(self, league_id, use_cache=True):
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

            def fetch_match_info(self, match_id, use_cache=True):
                # Return empty spielfeld for old tests (no location)
                return {
                    "status": 0,
                    "data": {
                        "matchId": match_id,
                        "matchInfo": {
                            "spielfeld": {}
                        }
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

            def fetch_matches(self, league_id, use_cache=True):
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

            def fetch_match_info(self, match_id, use_cache=True):
                # Return empty spielfeld for old tests (no location)
                return {
                    "status": 0,
                    "data": {
                        "matchId": match_id,
                        "matchInfo": {
                            "spielfeld": {}
                        }
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

    def test_get_matches_does_not_fetch_match_info(self):
        """Test that get_matches does not fetch match info (location is None by default)."""
        class DummyClient:
            def __init__(self):
                self.fetch_matches_call_count = 0
                self.fetch_match_info_call_count = 0

            def fetch_matches(self, league_id, use_cache=True):
                self.fetch_matches_call_count += 1
                return {
                    "status": 0,
                    "data": {
                        "matches": [
                            {
                                "matchId": 2708876,
                                "matchDay": 1,
                                "matchNo": 2101,
                                "kickoffDate": "2025-09-14",
                                "kickoffTime": "16:00",
                                "homeTeam": {
                                    "teamname": "TuS Hohnstorf/Elbe I",
                                    "clubId": 927,
                                    "seasonTeamId": 406405,
                                },
                                "guestTeam": {
                                    "teamname": "TV Falkenberg",
                                    "clubId": 2606,
                                    "seasonTeamId": 415879,
                                },
                                "result": "61:77",
                                "ergebnisbestaetigt": True,
                                "abgesagt": False,
                            }
                        ]
                    }
                }

            def fetch_match_info(self, match_id, use_cache=True):
                self.fetch_match_info_call_count += 1
                return {
                    "status": 0,
                    "data": {
                        "matchId": match_id,
                        "matchInfo": {
                            "spielfeld": {
                                "id": 214,
                                "bezeichnung": "Grundschule Hohnstorf",
                                "strasse": "Schulstr./Elbdeich",
                                "plz": "21522",
                                "ort": "Hohnstorf/Elbe"
                            }
                        }
                    }
                }

        with TemporaryDirectory() as directory:
            cache = FileCache(Path(directory))
            client = DummyClient()
            service = TeamSLService(cache=cache, client=client)

            result = service.get_matches("48693")

            self.assertEqual(client.fetch_matches_call_count, 1)
            # Should NOT fetch match info anymore
            self.assertEqual(client.fetch_match_info_call_count, 0)
            self.assertEqual(len(result["matches"]), 1)
            # Location should be None since we don't fetch match info
            self.assertIsNone(result["matches"][0]["location"])

    def test_get_matches_does_not_call_match_info(self):
        """Test that get_matches does not call fetch_match_info at all."""
        class DummyClient:
            def __init__(self):
                self.fetch_matches_call_count = 0
                self.fetch_match_info_call_count = 0

            def fetch_matches(self, league_id, use_cache=True):
                self.fetch_matches_call_count += 1
                return {
                    "status": 0,
                    "data": {
                        "matches": [
                            {
                                "matchId": 2708876,
                                "matchDay": 1,
                                "matchNo": 2101,
                                "kickoffDate": "2025-09-14",
                                "kickoffTime": "16:00",
                                "homeTeam": {
                                    "teamname": "TuS Hohnstorf/Elbe I",
                                    "clubId": 927,
                                },
                                "guestTeam": {
                                    "teamname": "TV Falkenberg",
                                    "clubId": 2606,
                                },
                                "result": None,
                                "ergebnisbestaetigt": False,
                                "abgesagt": False,
                            }
                        ]
                    }
                }

            def fetch_match_info(self, match_id, use_cache=True):
                self.fetch_match_info_call_count += 1
                raise ValueError("Match not found")

        with TemporaryDirectory() as directory:
            cache = FileCache(Path(directory))
            client = DummyClient()
            service = TeamSLService(cache=cache, client=client)

            # Should not raise an exception, and should not call fetch_match_info
            result = service.get_matches("48693")

            self.assertEqual(client.fetch_matches_call_count, 1)
            # Should NOT call fetch_match_info at all
            self.assertEqual(client.fetch_match_info_call_count, 0)
            self.assertEqual(len(result["matches"]), 1)
            self.assertIsNone(result["matches"][0]["location"])

    def test_get_matches_does_not_call_match_info_for_none_match_info(self):
        """Test that get_matches does not call match_info (location handling is now in get_match)."""
        class DummyClient:
            def __init__(self):
                self.fetch_matches_call_count = 0
                self.fetch_match_info_call_count = 0

            def fetch_matches(self, league_id, use_cache=True):
                self.fetch_matches_call_count += 1
                return {
                    "status": 0,
                    "data": {
                        "matches": [
                            {
                                "matchId": 2707599,
                                "matchDay": 1,
                                "matchNo": 1,
                                "kickoffDate": "2025-09-14",
                                "kickoffTime": "16:00",
                                "homeTeam": {
                                    "teamname": "Home Team",
                                    "clubId": 100,
                                },
                                "guestTeam": {
                                    "teamname": "Away Team",
                                    "clubId": 101,
                                },
                                "result": None,
                                "ergebnisbestaetigt": False,
                                "abgesagt": False,
                            }
                        ]
                    }
                }

            def fetch_match_info(self, match_id, use_cache=True):
                self.fetch_match_info_call_count += 1
                return {
                    "status": 0,
                    "data": {
                        "matchId": match_id,
                        "matchInfo": None
                    }
                }

        with TemporaryDirectory() as directory:
            cache = FileCache(Path(directory))
            client = DummyClient()
            service = TeamSLService(cache=cache, client=client)

            # Should not raise an exception, and should not call fetch_match_info
            result = service.get_matches("48693")

            self.assertEqual(client.fetch_matches_call_count, 1)
            # Should NOT call fetch_match_info anymore
            self.assertEqual(client.fetch_match_info_call_count, 0)
            self.assertEqual(len(result["matches"]), 1)
            self.assertIsNone(result["matches"][0]["location"])

    def test_get_matches_does_not_call_match_info_for_none_spielfeld(self):
        """Test that get_matches does not call match_info (spielfeld handling is now in get_match)."""
        class DummyClient:
            def __init__(self):
                self.fetch_matches_call_count = 0
                self.fetch_match_info_call_count = 0

            def fetch_matches(self, league_id, use_cache=True):
                self.fetch_matches_call_count += 1
                return {
                    "status": 0,
                    "data": {
                        "matches": [
                            {
                                "matchId": 2707609,
                                "matchDay": 1,
                                "matchNo": 1,
                                "kickoffDate": "2025-09-14",
                                "kickoffTime": "16:00",
                                "homeTeam": {
                                    "teamname": "Home Team",
                                    "clubId": 100,
                                },
                                "guestTeam": {
                                    "teamname": "Away Team",
                                    "clubId": 101,
                                },
                                "result": None,
                                "ergebnisbestaetigt": False,
                                "abgesagt": False,
                            }
                        ]
                    }
                }

            def fetch_match_info(self, match_id, use_cache=True):
                self.fetch_match_info_call_count += 1
                return {
                    "status": 0,
                    "data": {
                        "matchId": match_id,
                        "matchInfo": {
                            "spielfeld": None
                        }
                    }
                }

        with TemporaryDirectory() as directory:
            cache = FileCache(Path(directory))
            client = DummyClient()
            service = TeamSLService(cache=cache, client=client)

            # Should not raise an exception, and should not call fetch_match_info
            result = service.get_matches("48693")

            self.assertEqual(client.fetch_matches_call_count, 1)
            # Should NOT call fetch_match_info anymore
            self.assertEqual(client.fetch_match_info_call_count, 0)
            self.assertEqual(len(result["matches"]), 1)
            self.assertIsNone(result["matches"][0]["location"])

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
        # Verify timezone-aware datetime with Europe/Berlin timezone
        self.assertIsNotNone(first["datetime"].tzinfo)
        self.assertEqual(first["datetime"].tzinfo, ZoneInfo("Europe/Berlin"))
        self.assertEqual(first["datetime"].strftime("%Y-%m-%d %H:%M"), "2025-09-13 09:00")
        self.assertEqual(first["home_team"]["name"], "TuS Huchting")
        self.assertEqual(first["home_team"]["club_id"], 153)
        self.assertEqual(first["away_team"]["name"], "TV Delmenhorst")
        self.assertEqual(first["score"], "76:64")
        self.assertEqual(first["score_home"], 76)
        self.assertEqual(first["score_away"], 64)
        self.assertTrue(first["is_finished"])
        self.assertTrue(first["is_confirmed"])
        self.assertFalse(first["is_cancelled"])

        # Check second match (scheduled)
        second = result["matches"][1]
        self.assertEqual(second["match_id"], 2688137)
        self.assertIsInstance(second["datetime"], datetime)
        # Verify timezone-aware datetime with Europe/Berlin timezone
        self.assertIsNotNone(second["datetime"].tzinfo)
        self.assertEqual(second["datetime"].tzinfo, ZoneInfo("Europe/Berlin"))
        self.assertEqual(second["datetime"].strftime("%Y-%m-%d %H:%M"), "2025-09-20 18:00")
        self.assertIsNone(second["score"])
        self.assertIsNone(second["score_home"])
        self.assertIsNone(second["score_away"])
        self.assertFalse(second["is_finished"])
        self.assertFalse(second["is_confirmed"])

    def test_normalize_matches_extracts_location_from_match_locations(self):
        """Test that normalization extracts location from match_locations parameter."""
        raw_data = {
            "status": 0,
            "data": {
                "matches": [
                    {
                        "matchId": 2708876,
                        "matchDay": 1,
                        "matchNo": 2101,
                        "kickoffDate": "2025-09-14",
                        "kickoffTime": "16:00",
                        "homeTeam": {
                            "teamname": "TuS Hohnstorf/Elbe I",
                            "clubId": 927,
                            "seasonTeamId": 406405,
                        },
                        "guestTeam": {
                            "teamname": "TV Falkenberg",
                            "clubId": 2606,
                            "seasonTeamId": 415879,
                        },
                        "result": "61:77",
                        "ergebnisbestaetigt": True,
                        "abgesagt": False,
                    }
                ]
            }
        }

        match_locations = {2708876: "Grundschule Hohnstorf"}
        result = TeamSLService._normalize_matches(raw_data, "48693", match_locations=match_locations)

        self.assertEqual(len(result["matches"]), 1)
        match = result["matches"][0]
        self.assertEqual(match["location"], "Grundschule Hohnstorf")

    def test_normalize_matches_falls_back_to_match_data_if_location_not_in_match_locations(self):
        """Test that normalization falls back to match data if location not in match_locations."""
        raw_data = {
            "status": 0,
            "data": {
                "matches": [
                    {
                        "matchId": 2708876,
                        "matchDay": 1,
                        "matchNo": 2101,
                        "kickoffDate": "2025-09-14",
                        "kickoffTime": "16:00",
                        "homeTeam": {
                            "teamname": "TuS Hohnstorf/Elbe I",
                            "clubId": 927,
                        },
                        "guestTeam": {
                            "teamname": "TV Falkenberg",
                            "clubId": 2606,
                        },
                        "result": None,
                        "ergebnisbestaetigt": False,
                        "abgesagt": False,
                        "spielfeld": "Fallback Location",
                    }
                ]
            }
        }

        # Empty match_locations - should fall back to match data
        match_locations = {}
        result = TeamSLService._normalize_matches(raw_data, "48693", match_locations=match_locations)

        self.assertEqual(len(result["matches"]), 1)
        match = result["matches"][0]
        self.assertEqual(match["location"], "Fallback Location")

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
        self.assertIsNone(match["score_home"])
        self.assertIsNone(match["score_away"])
        self.assertFalse(match["is_finished"])
        self.assertFalse(match["is_confirmed"])
        self.assertFalse(match["is_cancelled"])
        self.assertIsNone(match["location"])

    def test_normalize_matches_handles_cancelled_matches(self):
        """Test that normalization correctly identifies cancelled matches (abgesagt)."""
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
                        "homeTeam": {"teamname": "Home Team", "verzicht": False},
                        "guestTeam": {"teamname": "Away Team", "verzicht": False},
                        "result": None,
                        "ergebnisbestaetigt": False,
                        "abgesagt": True,
                        "verzicht": False,
                    }
                ]
            }
        }

        result = TeamSLService._normalize_matches(raw_data, "12345")

        self.assertEqual(len(result["matches"]), 1)
        match = result["matches"][0]
        self.assertTrue(match["is_cancelled"])
        self.assertFalse(match["is_finished"])

    def test_normalize_matches_handles_forfeited_match(self):
        """Test that normalization correctly identifies matches marked as verzicht."""
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
                        "homeTeam": {"teamname": "Home Team", "verzicht": False},
                        "guestTeam": {"teamname": "Away Team", "verzicht": False},
                        "result": None,
                        "ergebnisbestaetigt": False,
                        "abgesagt": False,
                        "verzicht": True,
                    }
                ]
            }
        }

        result = TeamSLService._normalize_matches(raw_data, "12345")

        self.assertEqual(len(result["matches"]), 1)
        match = result["matches"][0]
        self.assertTrue(match["is_cancelled"])
        self.assertFalse(match["is_finished"])

    def test_normalize_matches_handles_home_team_forfeit(self):
        """Test that normalization identifies matches as cancelled when home team forfeits."""
        raw_data = {
            "status": 0,
            "data": {
                "matches": [
                    {
                        "matchId": 2788891,
                        "matchDay": 1,
                        "matchNo": 1,
                        "kickoffDate": "2025-09-28",
                        "kickoffTime": "14:00",
                        "homeTeam": {
                            "teamname": "Bremen 1860 wbl.",
                            "seasonTeamId": 415078,
                            "verzicht": True,
                        },
                        "guestTeam": {
                            "teamname": "TSV Okel e.V.",
                            "seasonTeamId": 430852,
                            "verzicht": False,
                        },
                        "result": None,
                        "ergebnisbestaetigt": False,
                        "abgesagt": False,
                        "verzicht": True,
                    }
                ]
            }
        }

        result = TeamSLService._normalize_matches(raw_data, "48722")

        self.assertEqual(len(result["matches"]), 1)
        match = result["matches"][0]
        self.assertTrue(match["is_cancelled"])
        self.assertFalse(match["is_finished"])
        self.assertEqual(match["home_team"]["name"], "Bremen 1860 wbl.")

    def test_normalize_matches_handles_away_team_forfeit(self):
        """Test that normalization identifies matches as cancelled when away team forfeits."""
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
                        "homeTeam": {
                            "teamname": "Home Team",
                            "verzicht": False,
                        },
                        "guestTeam": {
                            "teamname": "Away Team",
                            "verzicht": True,
                        },
                        "result": None,
                        "ergebnisbestaetigt": False,
                        "abgesagt": False,
                        "verzicht": False,
                    }
                ]
            }
        }

        result = TeamSLService._normalize_matches(raw_data, "12345")

        self.assertEqual(len(result["matches"]), 1)
        match = result["matches"][0]
        self.assertTrue(match["is_cancelled"])
        self.assertFalse(match["is_finished"])

    def test_normalize_matches_not_cancelled_when_no_forfeit_or_abgesagt(self):
        """Test that matches are not marked as cancelled when verzicht and abgesagt are false."""
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
                        "homeTeam": {"teamname": "Home Team", "verzicht": False},
                        "guestTeam": {"teamname": "Away Team", "verzicht": False},
                        "result": None,
                        "ergebnisbestaetigt": False,
                        "abgesagt": False,
                        "verzicht": False,
                    }
                ]
            }
        }

        result = TeamSLService._normalize_matches(raw_data, "12345")

        self.assertEqual(len(result["matches"]), 1)
        match = result["matches"][0]
        self.assertFalse(match["is_cancelled"])
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
        # Verify timezone-aware datetime with Europe/Berlin timezone
        self.assertIsNotNone(match["datetime"].tzinfo)
        self.assertEqual(match["datetime"].tzinfo, ZoneInfo("Europe/Berlin"))
        self.assertEqual(match["datetime"].strftime("%Y-%m-%d"), "2025-09-13")

    def test_normalize_matches_parses_score_with_colon(self):
        """Test that score parsing works with colon separator (standard format)."""
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
                        "result": "100:50",
                    }
                ]
            }
        }

        result = TeamSLService._normalize_matches(raw_data, "12345")

        match = result["matches"][0]
        self.assertEqual(match["score"], "100:50")
        self.assertEqual(match["score_home"], 100)
        self.assertEqual(match["score_away"], 50)

    def test_normalize_matches_parses_score_with_dash(self):
        """Test that score parsing works with dash separator (alternative format)."""
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
                        "result": "85-72",
                    }
                ]
            }
        }

        result = TeamSLService._normalize_matches(raw_data, "12345")

        match = result["matches"][0]
        self.assertEqual(match["score"], "85-72")
        self.assertEqual(match["score_home"], 85)
        self.assertEqual(match["score_away"], 72)

    def test_normalize_matches_parses_score_with_whitespace(self):
        """Test that score parsing handles extra whitespace."""
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
                        "result": " 95 : 88 ",
                    }
                ]
            }
        }

        result = TeamSLService._normalize_matches(raw_data, "12345")

        match = result["matches"][0]
        self.assertEqual(match["score"], " 95 : 88 ")
        self.assertEqual(match["score_home"], 95)
        self.assertEqual(match["score_away"], 88)

    def test_normalize_matches_handles_invalid_score_format(self):
        """Test that invalid score formats are handled gracefully."""
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
                        "result": "Invalid",
                    }
                ]
            }
        }

        result = TeamSLService._normalize_matches(raw_data, "12345")

        match = result["matches"][0]
        self.assertEqual(match["score"], "Invalid")
        self.assertIsNone(match["score_home"])
        self.assertIsNone(match["score_away"])

    def test_normalize_matches_handles_empty_score(self):
        """Test that empty score strings are handled correctly."""
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
                        "result": "",
                    }
                ]
            }
        }

        result = TeamSLService._normalize_matches(raw_data, "12345")

        match = result["matches"][0]
        self.assertIsNone(match["score"])
        self.assertIsNone(match["score_home"])
        self.assertIsNone(match["score_away"])
        self.assertFalse(match["is_finished"])

    def test_get_match_fetches_match_info_with_location(self):
        """Test that get_match fetches match info and includes location."""
        class DummyClient:
            def __init__(self):
                self.fetch_match_info_call_count = 0

            def fetch_matches(self, league_id, use_cache=True):
                return {"status": 0, "data": {"matches": []}}

            def fetch_match_info(self, match_id, use_cache=True):
                self.fetch_match_info_call_count += 1
                return {
                    "status": 0,
                    "data": {
                        "matchId": 2708876,
                        "matchDay": 1,
                        "matchNo": 2101,
                        "kickoffDate": "2025-09-14",
                        "kickoffTime": "16:00",
                        "homeTeam": {
                            "teamname": "TuS Hohnstorf/Elbe I",
                            "clubId": 927,
                            "seasonTeamId": 406405,
                        },
                        "guestTeam": {
                            "teamname": "TV Falkenberg",
                            "clubId": 2606,
                            "seasonTeamId": 415879,
                        },
                        "result": "61:77",
                        "ergebnisbestaetigt": True,
                        "abgesagt": False,
                        "matchInfo": {
                            "spielfeld": {
                                "id": 214,
                                "bezeichnung": "Grundschule Hohnstorf",
                                "strasse": "Schulstr./Elbdeich",
                                "plz": "21522",
                                "ort": "Hohnstorf/Elbe"
                            }
                        }
                    }
                }

        with TemporaryDirectory() as directory:
            cache = FileCache(Path(directory))
            client = DummyClient()
            service = TeamSLService(cache=cache, client=client)

            result = service.get_match(2708876)

            self.assertEqual(client.fetch_match_info_call_count, 1)
            self.assertEqual(result["match_id"], 2708876)
            self.assertEqual(result["location"], "Grundschule Hohnstorf")
            self.assertEqual(result["score"], "61:77")
            self.assertEqual(result["home_team"]["name"], "TuS Hohnstorf/Elbe I")
            self.assertEqual(result["away_team"]["name"], "TV Falkenberg")

    def test_get_match_handles_missing_location(self):
        """Test that get_match handles missing location gracefully."""
        class DummyClient:
            def fetch_matches(self, league_id, use_cache=True):
                return {"status": 0, "data": {"matches": []}}

            def fetch_match_info(self, match_id, use_cache=True):
                return {
                    "status": 0,
                    "data": {
                        "matchId": 2708876,
                        "matchDay": 1,
                        "matchNo": 2101,
                        "kickoffDate": "2025-09-14",
                        "kickoffTime": "16:00",
                        "homeTeam": {
                            "teamname": "Home Team",
                            "clubId": 100,
                        },
                        "guestTeam": {
                            "teamname": "Away Team",
                            "clubId": 101,
                        },
                        "result": None,
                        "ergebnisbestaetigt": False,
                        "abgesagt": False,
                        "matchInfo": {
                            "spielfeld": None
                        }
                    }
                }

        with TemporaryDirectory() as directory:
            cache = FileCache(Path(directory))
            client = DummyClient()
            service = TeamSLService(cache=cache, client=client)

            result = service.get_match(2708876)

            self.assertEqual(result["match_id"], 2708876)
            self.assertIsNone(result["location"])

    def test_get_match_raises_on_not_found(self):
        """Test that get_match raises ValueError when match is not found."""
        class DummyClient:
            def fetch_matches(self, league_id, use_cache=True):
                return {"status": 0, "data": {"matches": []}}

            def fetch_match_info(self, match_id, use_cache=True):
                return {
                    "status": 0,
                    "data": {}  # Empty data - no match
                }

        with TemporaryDirectory() as directory:
            cache = FileCache(Path(directory))
            client = DummyClient()
            service = TeamSLService(cache=cache, client=client)

            with self.assertRaises(ValueError) as context:
                service.get_match(99999)

            self.assertIn("not found", str(context.exception).lower())


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

    @patch('api.services.client.httpx.Client')
    def test_fetch_match_info_makes_correct_request(self, mock_client_class):
        """Test that fetch_match_info makes the correct HTTP request."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "status": 0,
            "data": {
                "matchId": 2708876,
                "matchInfo": {
                    "spielfeld": {
                        "id": 214,
                        "bezeichnung": "Grundschule Hohnstorf",
                        "strasse": "Schulstr./Elbdeich",
                        "plz": "21522",
                        "ort": "Hohnstorf/Elbe"
                    }
                }
            }
        }
        mock_response.raise_for_status = Mock()

        mock_client_instance = Mock()
        mock_client_instance.get.return_value = mock_response
        mock_client_class.return_value = mock_client_instance

        client = TeamSLClient(base_url="https://www.basketball-bund.net")
        result = client.fetch_match_info(2708876)

        mock_client_instance.get.assert_called_once_with("/rest/match/id/2708876/matchInfo")
        self.assertEqual(result["status"], 0)
        self.assertEqual(result["data"]["matchInfo"]["spielfeld"]["bezeichnung"], "Grundschule Hohnstorf")

    @patch('api.services.client.httpx.Client')
    def test_fetch_match_info_raises_on_non_zero_status(self, mock_client_class):
        """Test that fetch_match_info raises ValueError on API error."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "status": 1,
            "message": "Match not found"
        }
        mock_response.raise_for_status = Mock()

        mock_client_instance = Mock()
        mock_client_instance.get.return_value = mock_response
        mock_client_class.return_value = mock_client_instance

        client = TeamSLClient(base_url="https://www.basketball-bund.net")

        with self.assertRaises(ValueError) as context:
            client.fetch_match_info(99999)

        self.assertIn("API error", str(context.exception))
        self.assertIn("Match not found", str(context.exception))


@override_settings(SLAPI_API_TOKEN=None)
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
                        "datetime": datetime(2025, 9, 13, 9, 0, tzinfo=ZoneInfo("Europe/Berlin")),
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
                        "score_home": 76,
                        "score_away": 64,
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
            # Verify datetime includes timezone information in ISO format
            datetime_str = data["matches"][0]["datetime"]
            self.assertIn("+", datetime_str or "", msg="Datetime should include timezone offset")
            self.assertIn("2025-09-13T09:00", datetime_str, msg="Datetime should include date and time")
            self.assertEqual(data["matches"][0]["home_team"]["name"], "Home Team")
            self.assertEqual(data["matches"][0]["away_team"]["name"], "Away Team")
            self.assertEqual(data["matches"][0]["score"], "76:64")
            self.assertEqual(data["matches"][0]["score_home"], 76)
            self.assertEqual(data["matches"][0]["score_away"], 64)
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
                        "datetime": datetime(2025, 9, 13, 9, 0, tzinfo=ZoneInfo("Europe/Berlin")),
                        "home_team": {"id": "1", "name": "Home Team"},
                        "away_team": {"id": "2", "name": "Away Team"},
                        "location": None,
                        "score": "76:64",
                        "score_home": 76,
                        "score_away": 64,
                        "is_finished": True,
                        "is_confirmed": True,
                        "is_cancelled": False,
                    },
                    {
                        "match_id": 2,
                        "match_day": 2,
                        "match_no": 2,
                        "datetime": datetime(2025, 10, 1, 18, 0, tzinfo=ZoneInfo("Europe/Berlin")),
                        "home_team": {"id": "3", "name": "Future Home"},
                        "away_team": {"id": "4", "name": "Future Away"},
                        "location": None,  # Location is not included by default
                        "score": None,
                        "score_home": None,
                        "score_away": None,
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
            self.assertEqual(finished["score_home"], 76)
            self.assertEqual(finished["score_away"], 64)
            
            # Check future match
            future = data["matches"][1]
            self.assertFalse(future["is_finished"])
            self.assertIsNone(future["score"])
            self.assertIsNone(future["score_home"])
            self.assertIsNone(future["score_away"])
            # Location is None by default (use /match/{id} endpoint for location)
            self.assertIsNone(future["location"])

    def test_match_endpoint_returns_match_with_location(self):
        """Test that the /match/{id} endpoint returns match with location."""
        with patch('api.api.service') as mock_service:
            mock_service.get_match.return_value = {
                "match_id": 2708876,
                "match_day": 1,
                "match_no": 2101,
                "datetime": datetime(2025, 9, 14, 16, 0, tzinfo=ZoneInfo("Europe/Berlin")),
                "home_team": {
                    "id": "406405",
                    "name": "TuS Hohnstorf/Elbe I",
                    "club_id": 927,
                    "season_team_id": 406405,
                },
                "away_team": {
                    "id": "415879",
                    "name": "TV Falkenberg",
                    "club_id": 2606,
                    "season_team_id": 415879,
                },
                "location": "Grundschule Hohnstorf",  # Location is included
                "score": "61:77",
                "score_home": 61,
                "score_away": 77,
                "is_finished": True,
                "is_confirmed": True,
                "is_cancelled": False,
            }

            response = self.client.get("/match/2708876")

            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertEqual(data["match_id"], 2708876)
            # Verify datetime includes timezone information in ISO format
            datetime_str = data["datetime"]
            self.assertIn("+", datetime_str or "", msg="Datetime should include timezone offset")
            self.assertIn("2025-09-14T16:00", datetime_str, msg="Datetime should include date and time")
            self.assertEqual(data["location"], "Grundschule Hohnstorf")
            self.assertEqual(data["score"], "61:77")
            self.assertEqual(data["home_team"]["name"], "TuS Hohnstorf/Elbe I")
            self.assertEqual(data["away_team"]["name"], "TV Falkenberg")
            mock_service.get_match.assert_called_once_with(2708876, use_cache=True)

    def test_match_endpoint_respects_use_cache_parameter(self):
        """Test that the use_cache parameter is passed to the service."""
        with patch('api.api.service') as mock_service:
            mock_service.get_match.return_value = {
                "match_id": 2708876,
                "match_day": 1,
                "match_no": 2101,
                "datetime": datetime(2025, 9, 14, 16, 0, tzinfo=ZoneInfo("Europe/Berlin")),
                "home_team": {"id": "1", "name": "Home Team"},
                "away_team": {"id": "2", "name": "Away Team"},
                "location": None,
                "score": None,
                "score_home": None,
                "score_away": None,
                "is_finished": False,
                "is_confirmed": False,
                "is_cancelled": False,
            }

            response = self.client.get("/match/2708876?use_cache=false")

            self.assertEqual(response.status_code, 200)
            mock_service.get_match.assert_called_once_with(2708876, use_cache=False)

