from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from .cache import FileCache
from .client import TeamSLClient
from .decorators import (
    CachedClient,
    MetricsClient,
    RetryClient,
    TransformClient,
)


class TeamSLService:
    """
    High-level orchestrator responsible for caching and normalizing upstream data.
    
    Uses the decorator pattern to compose cross-cutting concerns:
    - Metrics: Collects performance metrics
    - Cache: Handles response caching
    - Retry: Handles retries and throttling
    - Transform: Transforms/normalizes data
    - Base Client: Pure HTTP client
    """

    def __init__(
        self,
        cache: Optional[FileCache] = None,
        client: Optional[TeamSLClient] = None,
    ) -> None:
        # Store cache and client for backward compatibility
        self.cache = cache or FileCache()
        base_client = client or TeamSLClient()
        
        # Compose decorators in order: Metrics → Cache → Retry → Transform → Base Client
        # This ensures:
        # - Metrics capture everything (including cache hits)
        # - Cache intercepts before retries (avoids unnecessary retries)
        # - Retries happen before transformation (transform errors don't trigger retries)
        # - Base client stays pure
        transformed = TransformClient(base_client)
        retried = RetryClient(transformed)
        cached = CachedClient(retried, cache=self.cache)
        self._decorated_client = MetricsClient(cached)

    def get_leagues(self, use_cache: bool = True) -> List[Dict[str, str]]:
        """
        Fetch leagues with all decorators applied (caching, retries, metrics, etc.).
        
        Args:
            use_cache: If True, check cache first and store results. If False, bypass cache.
        
        Returns:
            Normalized list of league dictionaries.
        """
        leagues = self._decorated_client.fetch_leagues(use_cache=use_cache)
        normalized = [self._normalize_league(entry) for entry in leagues]
        return normalized

    def get_standings(self, league_id: str, use_cache: bool = True) -> Dict[str, Any]:
        """
        Fetch standings for a league with all decorators applied (caching, retries, metrics, etc.).
        
        Args:
            league_id: The league ID to fetch standings for.
            use_cache: If True, check cache first and store results. If False, bypass cache.
        
        Returns:
            Dictionary containing normalized standings data with league_id and standings list.
        """
        raw_data = self._decorated_client.fetch_standings(league_id, use_cache=use_cache)
        standings = self._normalize_standings(raw_data, league_id)
        return standings

    def get_matches(self, league_id: str, use_cache: bool = True) -> Dict[str, Any]:
        """
        Fetch matches for a league with all decorators applied (caching, retries, metrics, etc.).
        
        Args:
            league_id: The league ID to fetch matches for.
            use_cache: If True, check cache first and store results. If False, bypass cache.
        
        Returns:
            Dictionary containing normalized matches data with league_id and matches list.
        """
        raw_data = self._decorated_client.fetch_matches(league_id, use_cache=use_cache)
        matches = self._normalize_matches(raw_data, league_id)
        return matches

    def get_associations(self, use_cache: bool = True) -> List[Dict[str, Any]]:
        """
        Fetch Verbände (associations) with all decorators applied.
        
        Args:
            use_cache: If True, check cache first and store results. If False, bypass cache.
        
        Returns:
            Normalized list of association dictionaries.
        """
        raw_data = self._decorated_client.fetch_associations(use_cache=use_cache)
        return self._normalize_associations(raw_data)

    def get_club_leagues(
        self, club_name: str, verband_id: int = 7, use_cache: bool = True
    ) -> Dict[str, Any]:
        """
        Fetch leagues for a specific club with all decorators applied.
        
        Args:
            club_name: Name of the club to search for (e.g., "Eisbären Bremerhaven").
            verband_id: Association ID (default: 7 for Niedersachsen).
            use_cache: If True, check cache first and store results. If False, bypass cache.
        
        Returns:
            Dictionary containing club_name, verband_id, and normalized leagues list.
        """
        leagues = self._decorated_client.fetch_club_leagues(
            club_name, verband_id, use_cache=use_cache
        )
        normalized_leagues = [self._normalize_club_league(league) for league in leagues]
        return {
            "club_name": club_name,
            "verband_id": verband_id,
            "leagues": normalized_leagues,
        }

    @staticmethod
    def _normalize_league(entry: Dict[str, str]) -> Dict[str, str]:
        """
        Ensure each league entry conforms to the schema consumed by the API layer.
        """
        identifier = entry.get("id") or entry.get("slug") or "unknown"
        name = entry.get("name") or entry.get("title") or "Unknown League"
        return {"id": identifier, "name": name}

    @staticmethod
    def _normalize_standings(raw_data: Dict[str, Any], league_id: str) -> Dict[str, Any]:
        """
        Normalize raw standings data from the upstream API into our schema format.
        
        Args:
            raw_data: Raw response from the API containing data.tabelle.entries
            league_id: The league ID for the standings
        
        Returns:
            Dictionary with league_id and normalized standings list.
        """
        data = raw_data.get("data", {})
        tabelle = data.get("tabelle", {})
        entries = tabelle.get("entries", [])
        
        normalized_standings = []
        for position, entry in enumerate(entries, start=1):
            team_data = entry.get("team", {})
            
            # Extract team information
            team = {
                "id": str(team_data.get("seasonTeamId", team_data.get("teamPermanentId", ""))),
                "name": team_data.get("teamname", team_data.get("teamnameSmall", "Unknown Team")),
                "club_id": team_data.get("clubId"),
                "team_permanent_id": team_data.get("teamPermanentId"),
                "season_team_id": team_data.get("seasonTeamId"),
            }
            
            # Extract standings data
            # s = wins (Siege), n = losses (Niederlagen)
            standing = {
                "position": position,
                "team": team,
                "wins": entry.get("s", 0),
                "losses": entry.get("n", 0),
                "points_for": entry.get("koerbe"),
                "points_against": entry.get("gegenKoerbe"),
                "point_difference": entry.get("korbdiff"),
                "win_points": entry.get("anzGewinnpunkte"),
                "loss_points": entry.get("anzVerlustpunkte"),
            }
            
            normalized_standings.append(standing)
        
        return {
            "league_id": league_id,
            "standings": normalized_standings,
        }

    @staticmethod
    def _normalize_matches(raw_data: Dict[str, Any], league_id: str) -> Dict[str, Any]:
        """
        Normalize raw matches data from the upstream API into our schema format.
        
        Args:
            raw_data: Raw response from the API containing data.matches
            league_id: The league ID for the matches
        
        Returns:
            Dictionary with league_id and normalized matches list.
        """
        data = raw_data.get("data", {})
        matches = data.get("matches", [])
        
        normalized_matches = []
        for match in matches:
            # Extract match metadata
            match_id = match.get("matchId")
            match_day = match.get("matchDay", 0)
            match_no = match.get("matchNo", 0)
            
            # Parse datetime from kickoffDate and kickoffTime
            kickoff_date = match.get("kickoffDate", "")
            kickoff_time = match.get("kickoffTime", "")
            match_datetime = None
            
            if kickoff_date:
                if kickoff_time:
                    try:
                        # Combine date and time, format is typically "YYYY-MM-DD" and "HH:MM"
                        datetime_str = f"{kickoff_date} {kickoff_time}"
                        match_datetime = datetime.strptime(datetime_str, "%Y-%m-%d %H:%M")
                    except (ValueError, TypeError):
                        # If parsing fails, try with just the date
                        try:
                            match_datetime = datetime.strptime(kickoff_date, "%Y-%m-%d")
                        except (ValueError, TypeError):
                            pass
                else:
                    # Only date provided, no time
                    try:
                        match_datetime = datetime.strptime(kickoff_date, "%Y-%m-%d")
                    except (ValueError, TypeError):
                        pass
            
            # Extract home team
            home_team_data = match.get("homeTeam", {})
            home_team = {
                "id": str(home_team_data.get("seasonTeamId", home_team_data.get("teamPermanentId", ""))),
                "name": home_team_data.get("teamname", home_team_data.get("teamnameSmall", "Unknown Team")),
                "club_id": home_team_data.get("clubId"),
                "team_permanent_id": home_team_data.get("teamPermanentId"),
                "season_team_id": home_team_data.get("seasonTeamId"),
            }
            
            # Extract away team (guestTeam)
            away_team_data = match.get("guestTeam", {})
            away_team = {
                "id": str(away_team_data.get("seasonTeamId", away_team_data.get("teamPermanentId", ""))),
                "name": away_team_data.get("teamname", away_team_data.get("teamnameSmall", "Unknown Team")),
                "club_id": away_team_data.get("clubId"),
                "team_permanent_id": away_team_data.get("teamPermanentId"),
                "season_team_id": away_team_data.get("seasonTeamId"),
            }
            
            # Extract result/score
            result = match.get("result")
            score = result if result else None
            
            # Parse score into home and away components
            score_home = None
            score_away = None
            if score:
                try:
                    # Score format is typically "100:50" or "76-64"
                    # Try colon separator first, then dash
                    if ':' in score:
                        parts = score.split(':')
                    elif '-' in score:
                        parts = score.split('-')
                    else:
                        parts = []
                    
                    if len(parts) == 2:
                        score_home = int(parts[0].strip())
                        score_away = int(parts[1].strip())
                except (ValueError, AttributeError):
                    # If parsing fails, leave as None
                    pass
            
            # Determine match status
            is_finished = result is not None and result != ""
            is_confirmed = match.get("ergebnisbestaetigt", False)
            
            # A match is cancelled if:
            # 1. It's explicitly marked as cancelled (abgesagt), OR
            # 2. The match is marked as forfeit (verzicht), OR
            # 3. Either team has forfeited (verzicht)
            is_cancelled = (
                match.get("abgesagt", False) or
                match.get("verzicht", False) or
                home_team_data.get("verzicht", False) or
                away_team_data.get("verzicht", False)
            )
            
            # Extract location if available (check common field names)
            location = (
                match.get("spielfeld") or
                match.get("halle") or
                match.get("location") or
                match.get("venue") or
                None
            )
            
            normalized_match = {
                "match_id": match_id,
                "match_day": match_day,
                "match_no": match_no,
                "datetime": match_datetime,
                "home_team": home_team,
                "away_team": away_team,
                "location": location,
                "score": score,
                "score_home": score_home,
                "score_away": score_away,
                "is_finished": is_finished,
                "is_confirmed": is_confirmed,
                "is_cancelled": is_cancelled,
            }
            
            normalized_matches.append(normalized_match)
        
        return {
            "league_id": league_id,
            "matches": normalized_matches,
        }

    @staticmethod
    def _normalize_associations(raw_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Normalize raw Verbände data from the upstream API.
        
        Args:
            raw_data: Raw response from the API containing data.verbaende
        
        Returns:
            List of normalized association dictionaries.
        """
        data = raw_data.get("data", {})
        verbaende = data.get("verbaende", [])

        normalized: List[Dict[str, Any]] = []
        for entry in verbaende:
            identifier = entry.get("id")
            label = entry.get("label") or entry.get("bezirk") or entry.get("name") or "Unknown Verband"
            hits_value = entry.get("hits", 0)
            try:
                hits = int(hits_value)
            except (TypeError, ValueError):
                hits = 0

            normalized.append(
                {
                    "id": str(identifier) if identifier is not None else "unknown",
                    "label": label,
                    "hits": hits,
                }
            )

        return normalized

    @staticmethod
    def _normalize_club_league(league: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normalize a club league entry from the HTML parsing.
        
        Args:
            league: Raw league dictionary from the client.
        
        Returns:
            Normalized league dictionary matching the ClubLeague schema.
        """
        return {
            "liga_id": league.get("liga_id"),
            "liganame": league.get("liganame", ""),
            "liganr": league.get("liganr"),
            "spielklasse": league.get("spielklasse"),
            "altersklasse": league.get("altersklasse"),
            "geschlecht": league.get("geschlecht"),
            "bezirk": league.get("bezirk"),
            "kreis": league.get("kreis"),
        }

