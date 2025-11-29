from ninja import NinjaAPI

from .auth import APITokenAuth
from .schemas import (
    ClubLeague,
    ClubLeaguesResponse,
    HealthResponse,
    LeagueListResponse,
    League,
    Match,
    MatchListResponse,
    StandingsResponse,
    Standing,
    Team,
    Verband,
    VerbandListResponse,
)
from .services.service import TeamSLService

api = NinjaAPI(
    title="TeamSL API",
    version="0.1.0",
    description="Wrapper API with caching for the German DBB TeamSL data source.",
)

service = TeamSLService()
auth = APITokenAuth()


@api.get("/health", response=HealthResponse, tags=["meta"])
def health_check(request):
    """
    Lightweight endpoint to confirm the API is reachable.
    """
    return {"status": "ok"}


@api.get("/leagues", response=LeagueListResponse, tags=["leagues"], auth=auth)
def list_leagues(request, use_cache: bool = True):
    """
    Return the cached-or-fetched list of available leagues.
    """
    records = service.get_leagues(use_cache=use_cache)
    leagues = [League(**record) for record in records]
    return {"leagues": leagues}


@api.get("/verbaende", response=VerbandListResponse, tags=["associations"], auth=auth)
def list_verbaende(request, use_cache: bool = True):
    """
    Return the cached-or-fetched list of available Verbände.
    """
    records = service.get_associations(use_cache=use_cache)
    verbaende = [Verband(**record) for record in records]
    return {"verbaende": verbaende}

@api.get("/leagues/{league_id}/standings", response=StandingsResponse, tags=["standings"], auth=auth)
def get_standings(request, league_id: str, use_cache: bool = True):
    """
    Return the standings for a specific league.
    
    The standings are returned as an ordered list of teams with their win/loss records,
    points scored, and other statistics.
    """
    data = service.get_standings(league_id, use_cache=use_cache)
    
    # Convert nested dictionaries to schema objects
    standings = [
        Standing(
            position=standing["position"],
            team=Team(**standing["team"]),
            wins=standing["wins"],
            losses=standing["losses"],
            points_for=standing["points_for"],
            points_against=standing["points_against"],
            point_difference=standing["point_difference"],
            win_points=standing["win_points"],
            loss_points=standing["loss_points"],
        )
        for standing in data["standings"]
    ]
    
    return StandingsResponse(league_id=data["league_id"], standings=standings)


@api.get("/leagues/{league_id}/matches", response=MatchListResponse, tags=["matches"], auth=auth)
def get_matches(request, league_id: str, use_cache: bool = True):
    """
    Return the matches (schedule) for a specific league.
    
    The matches are returned as a list containing all matches in the season,
    including both finished matches (with scores) and scheduled future matches.
    Each match includes the datetime, home and away teams, and status information
    (finished, confirmed, cancelled).
    
    Note: Location information is not included by default to improve performance.
    Use the /match/{id} endpoint to get detailed match information including location.
    """
    data = service.get_matches(league_id, use_cache=use_cache)
    
    # Convert nested dictionaries to schema objects
    matches = [
        Match(
            match_id=match["match_id"],
            match_day=match["match_day"],
            match_no=match["match_no"],
            datetime=match["datetime"],
            home_team=Team(**match["home_team"]),
            away_team=Team(**match["away_team"]),
            location=match["location"],
            score=match["score"],
            score_home=match["score_home"],
            score_away=match["score_away"],
            is_finished=match["is_finished"],
            is_confirmed=match["is_confirmed"],
            is_cancelled=match["is_cancelled"],
        )
        for match in data["matches"]
    ]
    
    return MatchListResponse(league_id=data["league_id"], matches=matches)


@api.get("/match/{match_id}", response=Match, tags=["matches"], auth=auth)
def get_match(request, match_id: int, use_cache: bool = True):
    """
    Return detailed information for a specific match including location.
    
    This endpoint fetches comprehensive match information including the venue location,
    which is not included in the /leagues/{league_id}/matches endpoint by default.
    
    Args:
        match_id: The match ID to fetch information for.
        use_cache: If True, check cache first and store results. If False, bypass cache.
    
    Returns:
        Match object with full details including location.
    """
    match_data = service.get_match(match_id, use_cache=use_cache)
    
    # Convert nested dictionaries to schema objects
    return Match(
        match_id=match_data["match_id"],
        match_day=match_data["match_day"],
        match_no=match_data["match_no"],
        datetime=match_data["datetime"],
        home_team=Team(**match_data["home_team"]),
        away_team=Team(**match_data["away_team"]),
        location=match_data["location"],
        score=match_data["score"],
        score_home=match_data["score_home"],
        score_away=match_data["score_away"],
        is_finished=match_data["is_finished"],
        is_confirmed=match_data["is_confirmed"],
        is_cancelled=match_data["is_cancelled"],
    )


@api.get("/clubs/{club_name}/leagues", response=ClubLeaguesResponse, tags=["clubs"], auth=auth)
def get_club_leagues(request, club_name: str, verband_id: int = 7, use_cache: bool = True):
    """
    Return all leagues that a specific club participates in.
    
    This endpoint searches for leagues by club name within a specific association (Verband).
    The club name should match the official name used by the basketball association,
    including any special characters (umlauts like ä, ö, ü are supported).
    
    Args:
        club_name: Name of the club (e.g., "Eisbären Bremerhaven" or "1860 Bremen")
        verband_id: Association ID (default: 7 for Niedersachsen)
        use_cache: If True, check cache first and store results. If False, bypass cache.
    
    Returns:
        ClubLeaguesResponse containing the club name, verband ID, and list of leagues.
    
    Examples:
        - GET /clubs/Eisbären Bremerhaven/leagues
        - GET /clubs/1860 Bremen/leagues?verband_id=7
    """
    data = service.get_club_leagues(club_name, verband_id, use_cache=use_cache)
    
    # Convert dictionaries to schema objects
    leagues = [ClubLeague(**league) for league in data["leagues"]]
    
    return ClubLeaguesResponse(
        club_name=data["club_name"],
        verband_id=data["verband_id"],
        leagues=leagues,
    )

