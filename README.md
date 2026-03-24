# DRatings Scraper API

FastAPI app that scrapes [DRatings.com](https://www.dratings.com) game predictions and returns structured JSON. Designed to run alongside n8n in Docker.

## Supported Sports

| Sport | Endpoint slug |
|-------|--------------|
| NBA | `nba` |
| NHL | `nhl` |
| NFL | `nfl` |
| MLB | `mlb` |
| NCAAB | `ncaab` |
| NCAAF | `ncaaf` |

## API Endpoints

### `GET /`
Health check. Returns supported sports list.

### `GET /games/{sport}`
Returns today's games for a sport with game IDs, teams, date/time, and URLs.

```bash
curl http://localhost:8000/games/nhl
```

```json
{
  "sport": "nhl",
  "date": "2026-03-24",
  "games": [
    {
      "game_id": "853066fb-18de-521e-84c8-8ed679fb5b56",
      "game_url": "https://www.dratings.com/predictor/nhl-hockey-predictions/853066fb-...",
      "away_team": "Toronto Maple Leafs",
      "home_team": "Boston Bruins",
      "date": "03/24/2026",
      "game_time": "11:07 PM"
    }
  ]
}
```

### `GET /game/{sport}/{game_id}`
Returns full game breakdown including:
- Team stats (record, rank, PPG, PAPG)
- Win probabilities and projected scores
- Last 5 games for each team
- Injuries
- Venue
- Moneyline odds (offshore + Vegas, all books)
- Spread odds with bet value analysis and steam moves
- Over/under odds with bet value analysis and steam moves

```bash
curl http://localhost:8000/game/nhl/853066fb-18de-521e-84c8-8ed679fb5b56
```

## Deploy to VPS (Hostinger)

### Prerequisites
- VPS with Docker and Docker Compose installed
- n8n already running in Docker (on the `root_default` network)

### Setup

1. SSH into your VPS (or use Hostinger's Terminal button in Docker Manager)

2. Clone the repo:
```bash
cd /opt
git clone https://github.com/WalrusQuant/dratings-scraper.git
cd dratings-scraper
```

3. Verify your n8n Docker network name:
```bash
docker network ls
```
The `docker-compose.yml` expects `root_default`. If yours is different, edit the file.

4. Build and start:
```bash
docker compose up -d --build
```

5. Test:
```bash
curl http://localhost:8000/
curl http://localhost:8000/games/nba
```

### Calling from n8n

Use the container name as the hostname (they share the same Docker network):

```
http://dratings-scraper:8000/games/nba
http://dratings-scraper:8000/game/nba/{game_id}
```

### Updating

After pushing changes to GitHub:

```bash
cd /opt/dratings-scraper
git pull
docker compose up -d --build
```

### Stopping

```bash
cd /opt/dratings-scraper
docker compose down
```

### Viewing logs

```bash
docker logs dratings-scraper
docker logs -f dratings-scraper  # follow/stream logs
```

## Local Development

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

API docs available at `http://localhost:8000/docs`.

## Project Structure

```
app/
  main.py       — FastAPI app and endpoint definitions
  scraper.py    — HTTP fetching with rate limiting
  parser.py     — BeautifulSoup HTML parsing
  models.py     — Pydantic response models
Dockerfile
docker-compose.yml
requirements.txt
```

## License

MIT
