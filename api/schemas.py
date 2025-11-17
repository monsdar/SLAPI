from datetime import datetime
from typing import List, Optional

from ninja import Schema


class HealthResponse(Schema):
    status: str


class League(Schema):
    id: str
    name: str


class LeagueListResponse(Schema):
    leagues: List[League]


class Team(Schema):
    """Represents a basketball team."""
    id: Optional[str] = None
    name: str
    club_id: Optional[int] = None
    team_permanent_id: Optional[int] = None
    season_team_id: Optional[int] = None


class Standing(Schema):
    """Represents a team's position in the standings."""
    position: int
    team: Team
    wins: int
    losses: int
    points_for: Optional[int] = None
    points_against: Optional[int] = None
    point_difference: Optional[int] = None
    win_points: Optional[int] = None
    loss_points: Optional[int] = None


class StandingsResponse(Schema):
    """Response containing the standings for a league."""
    league_id: str
    standings: List[Standing]


class Match(Schema):
    """Represents a basketball match."""
    match_id: int
    match_day: int
    match_no: int
    datetime: datetime
    home_team: Team
    away_team: Team
    location: Optional[str] = None
    score: Optional[str] = None
    is_finished: bool
    is_confirmed: bool
    is_cancelled: bool


class MatchListResponse(Schema):
    """Response containing the matches for a league."""
    league_id: str
    matches: List[Match]


class Verband(Schema):
    """Represents a basketball association (Verband)."""
    id: str
    label: str
    hits: int


class VerbandListResponse(Schema):
    """Response containing the available Verbände."""
    verbaende: List[Verband]


class ClubLeague(Schema):
    """Represents a league that a club participates in."""
    liga_id: Optional[int] = None
    liganame: str
    liganr: Optional[str] = None
    spielklasse: Optional[str] = None
    altersklasse: Optional[str] = None
    geschlecht: Optional[str] = None
    bezirk: Optional[str] = None
    kreis: Optional[str] = None


class ClubLeaguesResponse(Schema):
    """Response containing the leagues a club participates in."""
    club_name: str
    verband_id: int
    leagues: List[ClubLeague]