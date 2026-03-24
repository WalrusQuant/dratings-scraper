import time
import requests
from bs4 import BeautifulSoup

BASE_URL = "https://www.dratings.com/predictor"

SPORT_SLUGS = {
    "nba": "nba-basketball-predictions",
    "nhl": "nhl-hockey-predictions",
    "nfl": "nfl-football-predictions",
    "mlb": "mlb-baseball-predictions",
    "ncaab": "ncaa-basketball-predictions",
    "ncaaf": "ncaa-football-predictions",
}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}

_last_request_time: float = 0.0
MIN_REQUEST_INTERVAL = 1.5  # seconds between requests


def _rate_limit():
    global _last_request_time
    now = time.time()
    elapsed = now - _last_request_time
    if elapsed < MIN_REQUEST_INTERVAL:
        time.sleep(MIN_REQUEST_INTERVAL - elapsed)
    _last_request_time = time.time()


def get_sport_slug(sport: str) -> str:
    slug = SPORT_SLUGS.get(sport.lower())
    if not slug:
        raise ValueError(f"Unknown sport: {sport}. Supported: {list(SPORT_SLUGS.keys())}")
    return slug


def fetch_games_page(sport: str) -> BeautifulSoup:
    slug = get_sport_slug(sport)
    url = f"{BASE_URL}/{slug}/"
    _rate_limit()
    resp = requests.get(url, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    return BeautifulSoup(resp.text, "lxml")


def fetch_game_page(sport: str, game_id: str) -> BeautifulSoup:
    slug = get_sport_slug(sport)
    url = f"{BASE_URL}/{slug}/{game_id}"
    _rate_limit()
    resp = requests.get(url, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    return BeautifulSoup(resp.text, "lxml")


def get_game_url(sport: str, game_id: str) -> str:
    slug = get_sport_slug(sport)
    return f"{BASE_URL}/{slug}/{game_id}"
