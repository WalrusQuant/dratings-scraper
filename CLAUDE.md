# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

A FastAPI scraper that fetches game predictions from DRatings.com and returns structured JSON. Runs in Docker alongside n8n on a Hostinger VPS. n8n calls this API on a daily cron to pull game data for AI-generated sports articles.

## Commands

```bash
# Local development
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload

# Docker
docker compose up -d --build
docker logs dratings-scraper

# Deploy updates to VPS
git push  # then on VPS:
# cd /opt/dratings-scraper && git pull && docker compose up -d --build
```

## Architecture

The request flow is: **FastAPI endpoint → scraper (HTTP fetch) → parser (BeautifulSoup) → Pydantic model → JSON response**.

- `scraper.py` — Fetches raw HTML from DRatings with rate limiting (1.5s between requests). All sports use the same URL pattern, just different slugs.
- `parser.py` — The bulk of the codebase. Parses two page types:
  - **Index page** (`parse_games_list`): Table rows in `div#scroll-upcoming` with game links, teams, dates.
  - **Detail page** (`parse_game_detail`): Multiple sections identified by `div#scroll-{section}` IDs. Key quirk: odds tables and analysis divs are **siblings** of their heading divs, not children. The parser walks siblings to find them.
- `models.py` — Pydantic models matching the JSON response structure.
- `main.py` — Two endpoints: `/games/{sport}` (list) and `/game/{sport}/{game_id}` (detail).

## DRatings HTML Patterns

The site is server-rendered. No JS rendering needed. Key selectors:

- Game list: `div#scroll-upcoming > table > tbody > tr`
- Teams: `div.overview-half--left` (away), `div.overview-half--right` (home)
- Projections: `span#away-breakdown-projection`, `span#home-breakdown-projection`
- Game time: `time.time-long-heading` (not `time.time-long`, which is steam move timestamps)
- Last 5: `table#away-form`, `table#home-form`
- Injuries: sibling divs after `div#scroll-injuries` containing `div.list-item` elements
- Venue: `div#scroll-weather div.tc--blackT`
- Odds tables: `table.offshore-sportsbook` and `table.vegas-sportsbook` as siblings after `div#scroll-money`, `div#scroll-spread`, `div#scroll-ou`
- Margins: inside heading divs in `span.heading-column.{offshore|vegas}-sportsbook > strong.margin-value`
- Analysis bars: `div#scroll-{type}-overall`, `div#scroll-{type}-base`, etc. — duplicated IDs, disambiguated by `div.offshore-sportsbook` / `div.vegas-sportsbook` ancestor
- Steam moves: `div.compare-card` inside non-table `div.offshore-sportsbook` / `div.vegas-sportsbook`

## Deployment

Runs on Hostinger VPS at `/opt/dratings-scraper`. Shares `root_default` Docker network with n8n. n8n calls it via `http://dratings-scraper:8000`.
