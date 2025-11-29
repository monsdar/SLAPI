from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional

import httpx
from bs4 import BeautifulSoup
from django.conf import settings

logger = logging.getLogger(__name__)


class TeamSLClient:
    """
    HTTP client for fetching data from the TeamSL REST API.
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        client: Optional[httpx.Client] = None,
    ) -> None:
        # Use the base URL without the /static/#/ligaauswahl path for REST API calls
        configured_url = base_url or settings.SLAPI_UPSTREAM_BASE_URL
        # Extract base domain if full URL is provided
        if "/static" in configured_url:
            self.base_url = configured_url.split("/static")[0]
        else:
            self.base_url = configured_url.rstrip("/")
        self._client = client or httpx.Client(base_url=self.base_url, timeout=10.0)

    def fetch_leagues(self) -> List[Dict[str, Any]]:
        """
        Fetch and parse upstream leagues.
        For now this returns an empty list but logs that the scraper has not yet been implemented.
        """
        logger.info("fetch_leagues called for base_url=%s", self.base_url)
        # Placeholder - future implementation will parse the upstream HTML
        return []

    def fetch_standings(self, league_id: str) -> Dict[str, Any]:
        """
        Fetch standings for a specific league from the upstream API.
        
        Args:
            league_id: The league ID to fetch standings for.
        
        Returns:
            Raw response dictionary from the API.
        
        Raises:
            httpx.HTTPError: If the request fails.
        """
        endpoint = f"/rest/competition/actual/id/{league_id}"
        logger.info("fetch_standings called for league_id=%s, endpoint=%s", league_id, endpoint)
        
        response = self._client.get(endpoint)
        response.raise_for_status()
        
        data = response.json()
        
        # Validate response structure - convert status to int for consistent comparison
        status = data.get("status")
        try:
            status_int = int(status) if status is not None else None
        except (ValueError, TypeError):
            status_int = None
        
        if status_int != 0:
            error_msg = data.get("message", "Unknown error")
            logger.error("API returned non-zero status: %s, message: %s", status, error_msg)
            raise ValueError(f"API error: {error_msg}")
        
        return data

    def fetch_matches(self, league_id: str) -> Dict[str, Any]:
        """
        Fetch matches (schedule) for a specific league from the upstream API.
        
        Args:
            league_id: The league ID to fetch matches for.
        
        Returns:
            Raw response dictionary from the API.
        
        Raises:
            httpx.HTTPError: If the request fails.
        """
        endpoint = f"/rest/competition/spielplan/id/{league_id}"
        logger.info("fetch_matches called for league_id=%s, endpoint=%s", league_id, endpoint)
        
        response = self._client.get(endpoint)
        response.raise_for_status()
        
        data = response.json()
        
        # Validate response structure - convert status to int for consistent comparison
        status = data.get("status")
        try:
            status_int = int(status) if status is not None else None
        except (ValueError, TypeError):
            status_int = None
        
        if status_int != 0:
            error_msg = data.get("message", "Unknown error")
            logger.error("API returned non-zero status: %s, message: %s", status, error_msg)
            raise ValueError(f"API error: {error_msg}")
        
        return data

    def fetch_match_info(self, match_id: int) -> Dict[str, Any]:
        """
        Fetch detailed match information including location (spielfeld) for a specific match.
        
        Args:
            match_id: The match ID to fetch information for.
        
        Returns:
            Raw response dictionary from the API.
        
        Raises:
            httpx.HTTPError: If the request fails.
        """
        endpoint = f"/rest/match/id/{match_id}/matchInfo"
        logger.info("fetch_match_info called for match_id=%s, endpoint=%s", match_id, endpoint)
        
        response = self._client.get(endpoint)
        response.raise_for_status()
        
        data = response.json()
        
        # Validate response structure - convert status to int for consistent comparison
        status = data.get("status")
        try:
            status_int = int(status) if status is not None else None
        except (ValueError, TypeError):
            status_int = None
        
        if status_int != 0:
            error_msg = data.get("message", "Unknown error")
            logger.error("API returned non-zero status: %s, message: %s", status, error_msg)
            raise ValueError(f"API error: {error_msg}")
        
        return data

    def fetch_associations(self) -> Dict[str, Any]:
        """
        Fetch the list of Verbände (associations) from the upstream API.
        
        Returns:
            Raw response dictionary from the API.
        
        Raises:
            httpx.HTTPError: If the request fails.
        """
        endpoint = "/rest/wam/data"
        logger.info("fetch_associations called for endpoint=%s", endpoint)

        response = self._client.post(endpoint, json={})
        response.raise_for_status()

        data = response.json()
        
        # Validate response structure - convert status to int for consistent comparison
        status = data.get("status")
        try:
            status_int = int(status) if status is not None else None
        except (ValueError, TypeError):
            status_int = None

        if status_int != 0:
            error_msg = data.get("message", "Unknown error")
            logger.error("API returned non-zero status: %s, message: %s", status, error_msg)
            raise ValueError(f"API error: {error_msg}")

        return data

    def fetch_club_leagues(self, club_name: str, verband_id: int = 7) -> List[Dict[str, Any]]:
        """
        Fetch leagues for a specific club using the legacy HTML form endpoint.
        
        This method searches for all leagues a club participates in by submitting
        a POST request to the legacy HTML form endpoint, then parsing the results.
        It handles pagination automatically to fetch all matching leagues.
        
        Args:
            club_name: Name of the club to search for (e.g., "Eisbären Bremerhaven").
                      Supports German umlauts (ä, ö, ü, ß) which are automatically URL-encoded.
            verband_id: Association ID (default: 7 for Niedersachsen).
        
        Returns:
            List of dictionaries containing league information with keys:
            - liga_id: League ID (int or None)
            - liganame: League name
            - liganr: League number
            - spielklasse: League class/level
            - altersklasse: Age group
            - geschlecht: Gender (männlich/weiblich/mix)
            - bezirk: District/region
            - kreis: Sub-district
        
        Raises:
            httpx.HTTPError: If the request fails.
        """
        endpoint = "/index.jsp"
        initial_url = f"{endpoint}?Action=100&Verband={verband_id}"
        
        logger.info(
            "fetch_club_leagues called for club_name=%s, verband_id=%s",
            club_name,
            verband_id,
        )
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
        }
        
        # First, GET the page to establish a session and get cookies
        logger.debug("GET %s to establish session", initial_url)
        initial_response = self._client.get(initial_url, headers=headers)
        initial_response.raise_for_status()
        
        # Prepare form data for the search
        form_data = {
            "Action": "100",
            "Verband": str(verband_id),
            "search": club_name,
            "cbSpielklasseFilter": "0",  # 0 = all classes
            "spieltyp_id": "0",  # 0 = all types
            "cbAltersklasseFilter": "0",  # 0 = all age groups
            "cbGeschlechtFilter": "0",  # 0 = all genders
            "cbBezirkFilter": "0",  # 0 = all districts
            "cbKreisFilter": "0",  # 0 = all sub-districts
        }
        
        # Make POST request with form data and session cookies
        post_headers = headers.copy()
        post_headers["Content-Type"] = "application/x-www-form-urlencoded"
        post_headers["Referer"] = f"{self.base_url}{initial_url}"
        post_headers["Origin"] = self.base_url
        
        logger.debug("POST %s with search=%s", initial_url, club_name)
        response = self._client.post(
            initial_url,
            data=form_data,
            headers=post_headers,
        )
        response.raise_for_status()
        
        # Parse the first page
        leagues = self._parse_league_table(response.text)
        
        # Check for pagination
        soup = BeautifulSoup(response.text, "html.parser")
        text_blob = soup.get_text(" ", strip=True)
        pagination_match = re.search(r"Seite\s+(\d+)\s*/\s*(\d+)\s*\((\d+)\s+Treffer", text_blob)
        
        if pagination_match:
            current_page = int(pagination_match.group(1))
            total_pages = int(pagination_match.group(2))
            total_hits = int(pagination_match.group(3))
            logger.debug(
                "Pagination detected - page %d/%d, total hits %d",
                current_page,
                total_pages,
                total_hits,
            )
            
            # Fetch remaining pages if any
            page_size = len(leagues) or 10
            if total_pages > 1 and page_size > 0:
                logger.debug("Fetching additional %d page(s)", total_pages - 1)
                for page_index in range(2, total_pages + 1):
                    startrow = (page_index - 1) * page_size
                    page_url = f"{initial_url}&startrow={startrow}"
                    page_headers = headers.copy()
                    page_headers["Referer"] = f"{self.base_url}{initial_url}"
                    
                    logger.debug("GET %s for page %d/%d", page_url, page_index, total_pages)
                    page_response = self._client.get(page_url, headers=page_headers)
                    page_response.raise_for_status()
                    
                    page_leagues = self._parse_league_table(page_response.text)
                    leagues.extend(page_leagues)
        
        logger.info("Found %d league(s) for club_name=%s", len(leagues), club_name)
        return leagues
    
    def _parse_league_table(self, html: str) -> List[Dict[str, Any]]:
        """
        Parse the HTML table containing leagues and return structured rows.
        
        Args:
            html: HTML content from the response.
        
        Returns:
            List of dictionaries containing league information.
        """
        soup = BeautifulSoup(html, "html.parser")
        leagues = []
        
        # Find the main data table
        tables = soup.find_all("table")
        if not tables:
            logger.warning("No tables found in response")
            return leagues
        
        # Look for the table with league data
        table = None
        for t in tables:
            first_row = t.find("tr")
            if first_row:
                header_text = first_row.get_text()
                if "Klasse" in header_text or "Liganame" in header_text or "Liganr" in header_text:
                    table = t
                    break
        
        if not table:
            # Fallback: use the largest table
            table = max(tables, key=lambda t: len(t.find_all("tr")))
        
        # Get table rows
        tbody = table.find("tbody")
        rows = tbody.find_all("tr") if tbody else table.find_all("tr")
        
        if len(rows) < 2:
            logger.warning("Table has fewer than 2 rows (expected header + data)")
            return leagues
        
        # Skip header row
        data_rows = rows[1:]
        
        for row in data_rows:
            cells = row.find_all("td")
            if len(cells) < 5:
                continue
            
            # Extract league information
            # The typical column order is:
            # 1. Klasse (league class)
            # 2. Alter (age group)
            # 3. m/w (gender)
            # 4. Bezirk (district)
            # 5. Kreis (sub-district)
            # 6. Liganame (league name)
            # 7. Liganr (league number)
            
            liga_id = None
            liganame = ""
            liganr = ""
            spielklasse = ""
            altersklasse = ""
            geschlecht = ""
            bezirk = ""
            kreis = ""
            
            # Extract liga_id from links
            links = row.find_all("a", href=True)
            for link in links:
                href = link.get("href", "")
                if "liga_id" in href:
                    match = re.search(r"liga_id=(\d+)", href)
                    if match:
                        liga_id = int(match.group(1))
                        break
            
            # Extract text values based on column positions (if we have 7 columns)
            if len(cells) >= 7:
                spielklasse = cells[0].get_text(strip=True)
                altersklasse = cells[1].get_text(strip=True)
                geschlecht = cells[2].get_text(strip=True)
                bezirk = cells[3].get_text(strip=True)
                kreis = cells[4].get_text(strip=True)
                liganame = cells[5].get_text(strip=True)
                liganr = cells[6].get_text(strip=True)
            else:
                # Fallback: try to extract from any cell
                for cell in cells:
                    cell_text = cell.get_text(strip=True)
                    if not cell_text:
                        continue
                    lowered = cell_text.lower()
                    
                    if not spielklasse and any(x in lowered for x in [
                        "bundesliga", "oberliga", "landesliga", "bezirks", "kreis",
                        "pokal", "meisterschaft", "regionsliga", "regionsklasse"
                    ]):
                        spielklasse = cell_text
                    elif not altersklasse and any(x in lowered for x in [
                        "senioren", "u19", "u18", "u17", "u16", "u15", "u14",
                        "u13", "u12", "u11", "u10", "u9", "u8"
                    ]):
                        altersklasse = cell_text
                    elif not geschlecht and any(x in lowered for x in [
                        "männlich", "weiblich", "mix", "maennlich", "weibl"
                    ]):
                        geschlecht = cell_text
                    elif not liganame and len(cell_text) > 5 and not cell_text.isdigit():
                        liganame = cell_text
                    elif not liganr and cell_text.isdigit() and len(cell_text) >= 2:
                        liganr = cell_text
            
            # Only add if we have at least a league name or ID
            if liganame or liga_id:
                leagues.append({
                    "liga_id": liga_id,
                    "liganame": liganame,
                    "liganr": liganr,
                    "spielklasse": spielklasse,
                    "altersklasse": altersklasse,
                    "geschlecht": geschlecht,
                    "bezirk": bezirk,
                    "kreis": kreis,
                })
        
        return leagues
