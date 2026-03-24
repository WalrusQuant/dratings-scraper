from datetime import date
from fastapi import FastAPI, HTTPException

from app.models import GameDetailResponse, GamesResponse
from app.scraper import SPORT_SLUGS, fetch_game_page, fetch_games_page
from app.parser import parse_game_detail, parse_games_list

app = FastAPI(
    title="DRatings Scraper API",
    description="Scrapes DRatings.com game predictions and returns structured JSON.",
    version="1.0.0",
)

VALID_SPORTS = list(SPORT_SLUGS.keys())


@app.get("/")
def health():
    return {"status": "ok", "sports": VALID_SPORTS}


@app.get("/games/{sport}", response_model=GamesResponse)
def get_games(sport: str):
    sport = sport.lower()
    if sport not in SPORT_SLUGS:
        raise HTTPException(status_code=400, detail=f"Unknown sport: {sport}. Valid: {VALID_SPORTS}")

    try:
        soup = fetch_games_page(sport)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to fetch games page: {e}")

    games = parse_games_list(soup, sport)

    return GamesResponse(
        sport=sport,
        date=date.today().isoformat(),
        games=games,
    )


@app.get("/game/{sport}/{game_id}", response_model=GameDetailResponse)
def get_game(sport: str, game_id: str):
    sport = sport.lower()
    if sport not in SPORT_SLUGS:
        raise HTTPException(status_code=400, detail=f"Unknown sport: {sport}. Valid: {VALID_SPORTS}")

    try:
        soup = fetch_game_page(sport, game_id)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to fetch game page: {e}")

    detail = parse_game_detail(soup, sport, game_id)
    return detail
