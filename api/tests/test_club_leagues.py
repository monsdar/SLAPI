from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase, TestCase

from api.services.cache import FileCache
from api.services.client import TeamSLClient
from api.services.service import TeamSLService


class TeamSLClientClubLeaguesTests(SimpleTestCase):
    """Tests for the fetch_club_leagues method in TeamSLClient."""

    def test_parse_league_table_extracts_data(self):
        """Test that _parse_league_table correctly extracts league data from HTML."""
        html = """
        <html>
            <table>
                <tr>
                    <th>Klasse</th>
                    <th>Alter</th>
                    <th>m/w</th>
                    <th>Bezirk</th>
                    <th>Kreis</th>
                    <th>Liganame</th>
                    <th>Liganr</th>
                </tr>
                <tr>
                    <td>2. Bundesliga</td>
                    <td>Senioren</td>
                    <td>männlich</td>
                    <td></td>
                    <td></td>
                    <td><a href="index.jsp?liga_id=51529">Herren ProA</a></td>
                    <td>12345</td>
                </tr>
            </table>
        </html>
        """
        
        client = TeamSLClient()
        leagues = client._parse_league_table(html)
        
        self.assertEqual(len(leagues), 1)
        self.assertEqual(leagues[0]["liga_id"], 51529)
        self.assertEqual(leagues[0]["liganame"], "Herren ProA")
        self.assertEqual(leagues[0]["spielklasse"], "2. Bundesliga")
        self.assertEqual(leagues[0]["altersklasse"], "Senioren")
        self.assertEqual(leagues[0]["geschlecht"], "männlich")

    def test_parse_league_table_handles_empty_html(self):
        """Test that _parse_league_table handles empty HTML gracefully."""
        html = "<html><body></body></html>"
        
        client = TeamSLClient()
        leagues = client._parse_league_table(html)
        
        self.assertEqual(leagues, [])

    def test_parse_league_table_handles_no_tables(self):
        """Test that _parse_league_table handles HTML with no tables."""
        html = "<html><body><div>No tables here</div></body></html>"
        
        client = TeamSLClient()
        leagues = client._parse_league_table(html)
        
        self.assertEqual(leagues, [])


class TeamSLServiceClubLeaguesTests(SimpleTestCase):
    """Tests for the get_club_leagues method in TeamSLService."""

    def test_get_club_leagues_returns_normalized_data(self):
        """Test that get_club_leagues returns normalized league data."""
        class DummyClient:
            def fetch_leagues(self):
                return []

            def fetch_standings(self, league_id):
                return {}

            def fetch_matches(self, league_id):
                return {}

            def fetch_associations(self):
                return {}

            def fetch_club_leagues(self, club_name, verband_id):
                return [
                    {
                        "liga_id": 12345,
                        "liganame": "Test League",
                        "liganr": "99",
                        "spielklasse": "Test Class",
                        "altersklasse": "Senioren",
                        "geschlecht": "männlich",
                        "bezirk": "Test District",
                        "kreis": "Test Kreis",
                    }
                ]

        with TemporaryDirectory() as directory:
            cache = FileCache(Path(directory))
            client = DummyClient()
            service = TeamSLService(cache=cache, client=client)

            result = service.get_club_leagues("Test Club", 7, use_cache=False)

            self.assertEqual(result["club_name"], "Test Club")
            self.assertEqual(result["verband_id"], 7)
            self.assertEqual(len(result["leagues"]), 1)
            self.assertEqual(result["leagues"][0]["liga_id"], 12345)
            self.assertEqual(result["leagues"][0]["liganame"], "Test League")

    def test_get_club_leagues_uses_cache(self):
        """Test that get_club_leagues uses cache after first fetch."""
        class DummyClient:
            def __init__(self):
                self.call_count = 0

            def fetch_leagues(self):
                return []

            def fetch_standings(self, league_id):
                return {}

            def fetch_matches(self, league_id):
                return {}

            def fetch_associations(self):
                return {}

            def fetch_club_leagues(self, club_name, verband_id):
                self.call_count += 1
                return [
                    {
                        "liga_id": 12345,
                        "liganame": f"League {self.call_count}",
                        "liganr": "99",
                        "spielklasse": "Test Class",
                        "altersklasse": "Senioren",
                        "geschlecht": "männlich",
                        "bezirk": "",
                        "kreis": "",
                    }
                ]

        with TemporaryDirectory() as directory:
            cache = FileCache(Path(directory))
            client = DummyClient()
            service = TeamSLService(cache=cache, client=client)

            first = service.get_club_leagues("Test Club", 7)
            second = service.get_club_leagues("Test Club", 7)

            self.assertEqual(first, second)
            self.assertEqual(client.call_count, 1)

    def test_get_club_leagues_bypasses_cache_when_requested(self):
        """Test that get_club_leagues bypasses cache when use_cache=False."""
        class DummyClient:
            def __init__(self):
                self.call_count = 0

            def fetch_leagues(self):
                return []

            def fetch_standings(self, league_id):
                return {}

            def fetch_matches(self, league_id):
                return {}

            def fetch_associations(self):
                return {}

            def fetch_club_leagues(self, club_name, verband_id):
                self.call_count += 1
                return [
                    {
                        "liga_id": 12345 + self.call_count,
                        "liganame": f"League {self.call_count}",
                        "liganr": "99",
                        "spielklasse": "Test Class",
                        "altersklasse": "Senioren",
                        "geschlecht": "männlich",
                        "bezirk": "",
                        "kreis": "",
                    }
                ]

        with TemporaryDirectory() as directory:
            cache = FileCache(Path(directory))
            client = DummyClient()
            service = TeamSLService(cache=cache, client=client)

            first = service.get_club_leagues("Test Club", 7, use_cache=False)
            second = service.get_club_leagues("Test Club", 7, use_cache=False)

            self.assertNotEqual(first["leagues"][0]["liga_id"], second["leagues"][0]["liga_id"])
            self.assertEqual(client.call_count, 2)


class ClubLeaguesAPITests(TestCase):
    """Tests for the /clubs/{club_name}/leagues API endpoint."""

    def test_club_leagues_endpoint_exists(self):
        """Test that the club leagues endpoint exists and returns a response."""
        # Use a simple club name that won't require actual HTTP requests
        with patch('api.api.service.get_club_leagues') as mock_get:
            mock_get.return_value = {
                "club_name": "Test Club",
                "verband_id": 7,
                "leagues": [
                    {
                        "liga_id": 12345,
                        "liganame": "Test League",
                        "liganr": "99",
                        "spielklasse": "Test Class",
                        "altersklasse": "Senioren",
                        "geschlecht": "männlich",
                        "bezirk": "",
                        "kreis": "",
                    }
                ],
            }

            response = self.client.get("/clubs/Test%20Club/leagues")

            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertEqual(data["club_name"], "Test Club")
            self.assertEqual(data["verband_id"], 7)
            self.assertEqual(len(data["leagues"]), 1)
            self.assertEqual(data["leagues"][0]["liganame"], "Test League")

    def test_club_leagues_endpoint_with_custom_verband(self):
        """Test that the club leagues endpoint accepts custom verband_id."""
        with patch('api.api.service.get_club_leagues') as mock_get:
            mock_get.return_value = {
                "club_name": "Test Club",
                "verband_id": 10,
                "leagues": [],
            }

            response = self.client.get("/clubs/Test%20Club/leagues?verband_id=10")

            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertEqual(data["verband_id"], 10)

    def test_club_leagues_endpoint_handles_special_characters(self):
        """Test that the endpoint handles club names with special characters."""
        with patch('api.api.service.get_club_leagues') as mock_get:
            mock_get.return_value = {
                "club_name": "Eisbären Bremerhaven",
                "verband_id": 7,
                "leagues": [],
            }

            # URL-encoded club name with umlauts
            response = self.client.get("/clubs/Eisb%C3%A4ren%20Bremerhaven/leagues")

            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertEqual(data["club_name"], "Eisbären Bremerhaven")

