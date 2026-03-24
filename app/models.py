from pydantic import BaseModel


# --- Games list endpoint models ---

class GameSummary(BaseModel):
    game_id: str
    game_url: str
    away_team: str
    home_team: str
    date: str
    game_time: str


class GamesResponse(BaseModel):
    sport: str
    date: str
    games: list[GameSummary]


# --- Game detail endpoint models ---

class Last5Game(BaseModel):
    result: str
    score: str
    date: str
    opponent: str
    location: str
    moneyline: int | None = None


class Injury(BaseModel):
    position: str
    player: str
    status: str


class TeamDetail(BaseModel):
    name: str
    record: str | None = None
    rank: int | None = None
    ppg: float | None = None
    papg: float | None = None
    win_prob: float | None = None
    projected_score: float | None = None
    last_5: list[Last5Game] = []
    injuries: list[Injury] = []


class BookOdds(BaseModel):
    away: int | None = None
    home: int | None = None


class OddsSection(BaseModel):
    implied_margin: float | None = None
    away_open: int | str | None = None
    home_open: int | str | None = None
    away_best: int | str | None = None
    home_best: int | str | None = None
    away_novig: float | str | None = None
    home_novig: float | str | None = None
    books: dict[str, BookOdds] = {}


class SpreadOddsSection(BaseModel):
    implied_margin: float | None = None
    away_open: str | None = None
    home_open: str | None = None
    away_best: str | None = None
    home_best: str | None = None
    away_novig: str | None = None
    home_novig: str | None = None
    books: dict[str, dict[str, str | None]] = {}


class BetValueSide(BaseModel):
    away: float | None = None
    home: float | None = None


class BetValueAnalysis(BaseModel):
    overall: BetValueSide | None = None
    base_rating: BetValueSide | None = None
    bet_trends: BetValueSide | None = None
    sharp_line: BetValueSide | None = None


class SteamMoves(BaseModel):
    away: str | None = None
    away_time: str | None = None
    home: str | None = None
    home_time: str | None = None


class MoneyLineOdds(BaseModel):
    offshore: OddsSection | None = None
    vegas: OddsSection | None = None


class SpreadOdds(BaseModel):
    offshore: SpreadOddsSection | None = None
    vegas: SpreadOddsSection | None = None
    analysis: dict[str, BetValueAnalysis] = {}
    steam_moves: dict[str, SteamMoves] = {}


class OverUnderSection(BaseModel):
    implied_margin: float | None = None
    over_open: str | None = None
    under_open: str | None = None
    over_best: str | None = None
    under_best: str | None = None
    over_novig: str | None = None
    under_novig: str | None = None
    books: dict[str, dict[str, str | None]] = {}


class OverUnderOdds(BaseModel):
    offshore: OverUnderSection | None = None
    vegas: OverUnderSection | None = None
    analysis: dict[str, BetValueAnalysis] = {}
    steam_moves: dict[str, SteamMoves] = {}


class AllOdds(BaseModel):
    moneyline: MoneyLineOdds | None = None
    spread: SpreadOdds | None = None
    over_under: OverUnderOdds | None = None


class GameDetailResponse(BaseModel):
    game_id: str
    sport: str
    date: str | None = None
    game_time: str | None = None
    venue: str | None = None
    away_team: TeamDetail
    home_team: TeamDetail
    odds: AllOdds | None = None
