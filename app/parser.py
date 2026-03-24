import re
from bs4 import BeautifulSoup, NavigableString, Tag

from app.models import (
    AllOdds,
    BetValueAnalysis,
    BetValueSide,
    BookOdds,
    GameDetailResponse,
    GameSummary,
    Injury,
    Last5Game,
    MoneyLineOdds,
    OddsSection,
    OverUnderOdds,
    OverUnderSection,
    SpreadOdds,
    SpreadOddsSection,
    SteamMoves,
    TeamDetail,
)
from app.scraper import get_game_url


# ──────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────

def _text(el: Tag | None) -> str:
    if el is None:
        return ""
    return el.get_text(strip=True)


def _safe_int(val: str) -> int | None:
    val = val.strip().replace(",", "")
    # Keep leading +/- for sign, but parse as int
    if not val or val == "-":
        return None
    try:
        return int(val)
    except ValueError:
        # Try stripping trailing non-numeric (e.g. "+900Close")
        m = re.match(r"([+-]?\d+)", val)
        return int(m.group(1)) if m else None


def _safe_float(val: str) -> float | None:
    val = val.strip().replace(",", "").replace("%", "")
    if not val or val == "-":
        return None
    try:
        return float(val)
    except ValueError:
        m = re.match(r"([+-]?\d+\.?\d*)", val)
        return float(m.group(1)) if m else None


def _normalize_half(val: str) -> str:
    return val.replace("\u00bd", ".5")


def _slugify_book(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", name.strip().lower()).strip("_")


def _find_next_siblings_until(start: Tag, stop_id_prefix: str, tag_name: str | None = None, **attrs) -> list[Tag]:
    """Find sibling elements after `start` until we hit an element whose id starts with stop_id_prefix."""
    results = []
    el = start.find_next_sibling()
    while el:
        if isinstance(el, Tag):
            eid = el.get("id", "")
            if eid and eid.startswith(stop_id_prefix) and el != start:
                break
            if tag_name is None or el.name == tag_name:
                if not attrs or all(v in el.get(k, []) if isinstance(el.get(k), list) else el.get(k) == v for k, v in attrs.items()):
                    results.append(el)
        el = el.find_next_sibling()
    return results


# ──────────────────────────────────────────────
# Games list page parsing
# ──────────────────────────────────────────────

def parse_games_list(soup: BeautifulSoup, sport: str) -> list[GameSummary]:
    """Parse the sport predictions index page. Structure: div#scroll-upcoming > table > tbody > tr rows."""
    games = []

    upcoming = soup.select_one("div#scroll-upcoming")
    if not upcoming:
        return games

    table = upcoming.find("table")
    if not table:
        return games

    tbody = table.find("tbody")
    if not tbody:
        return games

    uuid_pattern = re.compile(
        r"/predictor/[^/]+/([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})"
    )

    for row in tbody.find_all("tr"):
        cells = row.find_all("td")
        if len(cells) < 2:
            continue

        # Cell 0: date/time link with game_id
        link = cells[0].find("a", href=uuid_pattern)
        if not link:
            continue

        match = uuid_pattern.search(link.get("href", ""))
        if not match:
            continue
        game_id = match.group(1)

        # Date and time from <time> element
        time_el = link.find("time", class_="time-long")
        date_str = ""
        time_str = ""
        if time_el:
            # Date is in the span, time is bare text after <br>
            date_span = time_el.find("span")
            date_str = _text(date_span) if date_span else ""
            # Time: get all text, strip date part
            full = time_el.get_text(separator="\n", strip=True)
            parts = [p.strip() for p in full.split("\n") if p.strip()]
            if len(parts) >= 2:
                time_str = parts[-1]

        # Cell 1: teams — two spans with class table-cell--mw
        team_spans = cells[1].select("span.table-cell--mw")
        away_team = ""
        home_team = ""
        if len(team_spans) >= 2:
            away_link = team_spans[0].find("a")
            home_link = team_spans[1].find("a")
            away_team = _text(away_link) if away_link else _text(team_spans[0])
            home_team = _text(home_link) if home_link else _text(team_spans[1])

        games.append(GameSummary(
            game_id=game_id,
            game_url=get_game_url(sport, game_id),
            away_team=away_team,
            home_team=home_team,
            date=date_str,
            game_time=time_str,
        ))

    return games


# ──────────────────────────────────────────────
# Game detail page parsing
# ──────────────────────────────────────────────

def parse_game_detail(soup: BeautifulSoup, sport: str, game_id: str) -> GameDetailResponse:
    away = _parse_team(soup, "left", "away")
    home = _parse_team(soup, "right", "home")
    _parse_last5(soup, away, home)
    _parse_injuries(soup, away, home)
    venue = _parse_venue(soup)
    date_str, time_str = _parse_game_datetime(soup)
    odds = _parse_all_odds(soup)

    return GameDetailResponse(
        game_id=game_id,
        sport=sport,
        date=date_str,
        game_time=time_str,
        venue=venue,
        away_team=away,
        home_team=home,
        odds=odds,
    )


def _parse_game_datetime(soup: BeautifulSoup) -> tuple[str, str]:
    """Extract date/time from time.time-long-heading element.
    Text format: "11:10 PM • Mar 24, 2026", datetime attr: "2026-03-24T23:10:00Z"
    """
    date_str = ""
    time_str = ""

    time_el = soup.select_one("time.time-long-heading")
    if time_el:
        dt = time_el.get("datetime", "")
        text = _text(time_el)

        # Parse date from datetime attr (YYYY-MM-DDTHH:MM:SSZ -> MM/DD/YYYY)
        if dt:
            m = re.match(r"(\d{4})-(\d{2})-(\d{2})", dt)
            if m:
                date_str = f"{m.group(2)}/{m.group(3)}/{m.group(1)}"

        # Parse time from text (before the bullet)
        if "•" in text:
            time_str = text.split("•")[0].strip()
        elif text:
            time_str = text.strip()

    return date_str, time_str


def _parse_team(soup: BeautifulSoup, side: str, prefix: str) -> TeamDetail:
    """Parse team info from overview-half--left (away) or overview-half--right (home)."""
    half = soup.select_one(f"div.overview-half--{side}")

    name = ""
    record = None
    stats: dict = {}

    if half:
        name_el = half.select_one("h2 a")
        name = _text(name_el) if name_el else ""

        record_el = half.select_one("span.tf--mono.ts--up1")
        if record_el:
            record = _text(record_el).strip("()")

        # Stats: pairs of overview-team-label + overview-team-stat
        labels = half.select("span.overview-team-label")
        values = half.select("span.overview-team-stat")
        for label, value in zip(labels, values):
            lt = _text(label).lower()
            vt = _text(value)
            if "rank" in lt:
                stats["rank"] = _safe_int(vt)
            elif lt == "p/g":
                stats["ppg"] = _safe_float(vt)
            elif lt == "pa/g":
                stats["papg"] = _safe_float(vt)

    # Projections — the span contains nested spans with number and % separately
    win_prob_el = soup.select_one(f"span#{prefix}-breakdown-projection")
    proj_score_el = soup.select_one(f"span#{prefix}-breakdown-projected-score")

    win_prob = None
    if win_prob_el:
        # Text like "9.1%" — extract float
        win_prob = _safe_float(_text(win_prob_el))

    projected_score = None
    if proj_score_el:
        projected_score = _safe_float(_text(proj_score_el))

    return TeamDetail(
        name=name,
        record=record,
        rank=stats.get("rank"),
        ppg=stats.get("ppg"),
        papg=stats.get("papg"),
        win_prob=win_prob,
        projected_score=projected_score,
    )


def _parse_last5(soup: BeautifulSoup, away: TeamDetail, home: TeamDetail):
    away.last_5 = _parse_form_table(soup, "away-form")
    home.last_5 = _parse_form_table(soup, "home-form")


def _parse_form_table(soup: BeautifulSoup, table_id: str) -> list[Last5Game]:
    """Parse last-5-games table. Structure:
    td[0]: result (W/L span with score)
    td[1]: date + location + opponent
    td[2]: moneyline
    td[3]: link arrow (ignored)
    """
    table = soup.find("table", id=table_id)
    if not table:
        return []

    tbody = table.find("tbody")
    if not tbody:
        return []

    games = []
    for row in tbody.find_all("tr"):
        cells = row.find_all("td")
        if len(cells) < 3:
            continue

        # Result
        result_cell = cells[0]
        result_span = result_cell.find("span", class_=re.compile(r"tc--(green|red)"))
        result = ""
        score = ""
        if result_span:
            # The span text is like "W122-126" or "L139-118"
            # First character/text is W or L, inner span has score
            full = _text(result_span)
            if full.startswith("W"):
                result = "W"
                score = full[1:].strip()
            elif full.startswith("L"):
                result = "L"
                score = full[1:].strip()
            else:
                result = full[:1]
                score = full[1:]

        # Date + opponent (cell 1)
        opp_cell = cells[1]
        date_el = opp_cell.find("time", class_="date-short")
        date_str = _text(date_el) if date_el else ""

        # Location: raw text "vs" or "at" between time and link
        location = ""
        opp_text_parts = opp_cell.get_text(separator="|", strip=True).split("|")
        for part in opp_text_parts:
            p = part.strip().lower()
            if p in ("vs", "at"):
                location = p
                break

        opp_link = opp_cell.find("a")
        opponent = _text(opp_link) if opp_link else ""

        # Moneyline (cell 2)
        ml = _safe_int(_text(cells[2]))

        games.append(Last5Game(
            result=result,
            score=score,
            date=date_str,
            opponent=opponent,
            location=location,
            moneyline=ml,
        ))

    return games


def _parse_injuries(soup: BeautifulSoup, away: TeamDetail, home: TeamDetail):
    """Injuries: div#scroll-injuries is a heading, injury lists are in sibling grid-box divs."""
    inj_heading = soup.find("div", id="scroll-injuries")
    if not inj_heading:
        return

    # Collect sibling grid-box divs until we hit the next scroll section
    injury_sections = []
    el = inj_heading.find_next_sibling()
    while el:
        if isinstance(el, Tag):
            eid = el.get("id", "")
            if eid and eid.startswith("scroll-"):
                break
            # Check if it has list-item divs (injury content)
            if el.find("div", class_="list-item"):
                injury_sections.append(el)
        el = el.find_next_sibling()

    if len(injury_sections) >= 2:
        away.injuries = _parse_injury_list(injury_sections[0])
        home.injuries = _parse_injury_list(injury_sections[1])
    elif len(injury_sections) == 1:
        away.injuries = _parse_injury_list(injury_sections[0])


def _parse_injury_list(container: Tag) -> list[Injury]:
    """Parse injuries from a container with div.list-item elements.
    Structure: <li><div class="list-item"><span><strong>POS</strong> Name</span><span class="list-item-column"><span>Status</span></span></div></li>
    """
    injuries = []
    for item in container.find_all("div", class_="list-item"):
        position_el = item.find("strong")
        position = _text(position_el) if position_el else ""

        # Player name: text content of the first span, minus the strong tag
        first_span = item.find("span")
        player = ""
        if first_span:
            # Get all text in the first span, then strip position
            full = _text(first_span)
            if position and full.startswith(position):
                player = full[len(position):].strip()
            else:
                player = full

        # Status: inside span.list-item-column > span
        status_col = item.find("span", class_="list-item-column")
        status = ""
        if status_col:
            inner = status_col.find("span")
            status = _text(inner) if inner else _text(status_col)

        if position or player:
            injuries.append(Injury(position=position, player=player, status=status))

    return injuries


def _parse_venue(soup: BeautifulSoup) -> str | None:
    """Venue is in div#scroll-weather (which is a card), in div.tc--blackT."""
    weather = soup.find("div", id="scroll-weather")
    if not weather:
        # Also try: the weather section might be a card with id
        weather = soup.find("div", class_="card", id="scroll-weather")
    if not weather:
        return None

    venue_el = weather.select_one("div.tc--blackT")
    if venue_el:
        return _text(venue_el) or None
    return None


# ──────────────────────────────────────────────
# Odds parsing
# ──────────────────────────────────────────────

def _get_section_tables(soup: BeautifulSoup, section_id: str, next_section_id: str) -> tuple[Tag | None, Tag | None]:
    """Get the offshore and vegas tables that are siblings after a scroll-* heading div."""
    section = soup.find("div", id=section_id)
    if not section:
        # Try other tag types (spread heading uses div.heading)
        section = soup.find(["div", "h3"], id=section_id)
    if not section:
        return None, None

    offshore = None
    vegas = None
    el = section.find_next_sibling()
    while el:
        if isinstance(el, Tag):
            eid = el.get("id", "")
            cls = el.get("class", [])
            if eid == next_section_id:
                break
            if el.name == "table":
                if "offshore-sportsbook" in cls:
                    offshore = el
                elif "vegas-sportsbook" in cls:
                    vegas = el
                if offshore and vegas:
                    break
        el = el.find_next_sibling()

    return offshore, vegas


def _get_section_margin(section_div: Tag, book_type: str) -> float | None:
    """Get implied margin from the heading div. Margins are in span.heading-column.{book_type} > span.margin > strong.margin-value."""
    col = section_div.select_one(f"span.heading-column.{book_type}")
    if col:
        margin_el = col.find("strong", class_="margin-value")
        if margin_el:
            return _safe_float(_text(margin_el))
    return None


def _parse_all_odds(soup: BeautifulSoup) -> AllOdds:
    return AllOdds(
        moneyline=_parse_moneyline_odds(soup),
        spread=_parse_spread_odds(soup),
        over_under=_parse_ou_odds(soup),
    )


def _parse_odds_table_headers(table: Tag) -> list[str]:
    """Extract header names from the first row of a table."""
    headers = []
    header_row = table.find("tr")
    if header_row:
        for th in header_row.find_all(["th", "td"]):
            headers.append(_text(th))
    return headers


def _parse_moneyline_odds(soup: BeautifulSoup) -> MoneyLineOdds:
    section = soup.find("div", id="scroll-money")
    if not section:
        return MoneyLineOdds()

    offshore_table, vegas_table = _get_section_tables(soup, "scroll-money", "scroll-spread")
    offshore_margin = _get_section_margin(section, "offshore-sportsbook")
    vegas_margin = _get_section_margin(section, "vegas-sportsbook")

    offshore = _parse_ml_table(offshore_table, offshore_margin) if offshore_table else None
    vegas = _parse_ml_table(vegas_table, vegas_margin) if vegas_table else None

    return MoneyLineOdds(offshore=offshore, vegas=vegas)


def _parse_ml_table(table: Tag, margin: float | None) -> OddsSection:
    result = OddsSection(implied_margin=margin)
    headers = _parse_odds_table_headers(table)

    tbody = table.find("tbody")
    if not tbody:
        return result

    rows = tbody.find_all("tr")
    if len(rows) >= 1:
        _process_ml_row(rows[0].find_all("td"), headers, result, "away")
    if len(rows) >= 2:
        _process_ml_row(rows[1].find_all("td"), headers, result, "home")

    return result


def _process_ml_row(cells: list, headers: list, result: OddsSection, side: str):
    for i, cell in enumerate(cells):
        val = _text(cell)
        header = headers[i].lower() if i < len(headers) else ""

        # Skip the team name column (first cell, empty header or team name)
        if i == 0:
            continue

        parsed = _safe_int(val)

        if "open" in header:
            setattr(result, f"{side}_open", parsed)
        elif "best" in header:
            setattr(result, f"{side}_best", parsed)
        elif "no-vig" in header or "novig" in header or "no vig" in header:
            setattr(result, f"{side}_novig", _safe_float(val))
        elif header:
            book_key = _slugify_book(headers[i])
            if book_key and book_key not in ("open_line", "best_line", "no_vig_odds"):
                if book_key not in result.books:
                    result.books[book_key] = BookOdds()
                if side == "away":
                    result.books[book_key].away = parsed
                else:
                    result.books[book_key].home = parsed


def _parse_spread_odds(soup: BeautifulSoup) -> SpreadOdds:
    section = soup.find(["div"], id="scroll-spread")
    if not section:
        return SpreadOdds()

    offshore_table, vegas_table = _get_section_tables(soup, "scroll-spread", "scroll-ou")
    offshore_margin = _get_section_margin(section, "offshore-sportsbook") if section else None
    vegas_margin = _get_section_margin(section, "vegas-sportsbook") if section else None

    offshore = _parse_spread_or_ou_table(offshore_table, offshore_margin) if offshore_table else None
    vegas = _parse_spread_or_ou_table(vegas_table, vegas_margin) if vegas_table else None

    analysis = _parse_bet_analysis(soup, "spread")
    steam = _parse_steam_moves(soup, "spread")

    return SpreadOdds(
        offshore=SpreadOddsSection(**offshore) if offshore else None,
        vegas=SpreadOddsSection(**vegas) if vegas else None,
        analysis=analysis,
        steam_moves=steam,
    )


def _parse_ou_odds(soup: BeautifulSoup) -> OverUnderOdds:
    section = soup.find("div", id="scroll-ou")
    if not section:
        return OverUnderOdds()

    # O/U tables are after scroll-ou, no clear next section — use a sentinel
    offshore_table, vegas_table = _get_section_tables(soup, "scroll-ou", "scroll-NONE")
    offshore_margin = _get_section_margin(section, "offshore-sportsbook") if section else None
    vegas_margin = _get_section_margin(section, "vegas-sportsbook") if section else None

    offshore_data = _parse_spread_or_ou_table(offshore_table, offshore_margin) if offshore_table else None
    vegas_data = _parse_spread_or_ou_table(vegas_table, vegas_margin) if vegas_table else None

    # Map away/home keys to over/under for O/U
    offshore = _remap_ou_keys(offshore_data) if offshore_data else None
    vegas = _remap_ou_keys(vegas_data) if vegas_data else None

    analysis = _parse_bet_analysis(soup, "ou")
    steam = _parse_steam_moves(soup, "ou")

    return OverUnderOdds(
        offshore=OverUnderSection(**offshore) if offshore else None,
        vegas=OverUnderSection(**vegas) if vegas else None,
        analysis=analysis,
        steam_moves=steam,
    )


def _remap_ou_keys(data: dict) -> dict:
    """Remap away_* / home_* to over_* / under_*."""
    return {
        "implied_margin": data.get("implied_margin"),
        "over_open": data.get("away_open"),
        "under_open": data.get("home_open"),
        "over_best": data.get("away_best"),
        "under_best": data.get("home_best"),
        "over_novig": data.get("away_novig"),
        "under_novig": data.get("home_novig"),
        "books": {k: {"over": v.get("away"), "under": v.get("home")} for k, v in data.get("books", {}).items()},
    }


def _parse_spread_or_ou_table(table: Tag, margin: float | None) -> dict:
    """Generic parser for spread/O/U tables. Returns a dict usable for SpreadOddsSection or OverUnderSection."""
    result = {
        "implied_margin": margin,
        "away_open": None, "home_open": None,
        "away_best": None, "home_best": None,
        "away_novig": None, "home_novig": None,
        "books": {},
    }

    headers = _parse_odds_table_headers(table)
    tbody = table.find("tbody")
    if not tbody:
        return result

    rows = tbody.find_all("tr")
    if len(rows) >= 1:
        _process_spread_row(rows[0].find_all("td"), headers, result, "away")
    if len(rows) >= 2:
        _process_spread_row(rows[1].find_all("td"), headers, result, "home")

    return result


def _process_spread_row(cells: list, headers: list, result: dict, side: str):
    for i, cell in enumerate(cells):
        if i == 0:
            continue  # team name cell
        val = _normalize_half(_text(cell))
        header = headers[i].lower() if i < len(headers) else ""

        if "open" in header:
            result[f"{side}_open"] = val or None
        elif "best" in header:
            result[f"{side}_best"] = val or None
        elif "no-vig" in header or "novig" in header or "no vig" in header:
            result[f"{side}_novig"] = val or None
        elif header:
            book_key = _slugify_book(headers[i])
            if book_key and book_key not in ("open_line", "best_line", "no_vig_odds"):
                if book_key not in result["books"]:
                    result["books"][book_key] = {}
                result["books"][book_key][side] = val or None


# ──────────────────────────────────────────────
# Bet value analysis
# ──────────────────────────────────────────────

def _parse_bet_analysis(soup: BeautifulSoup, section_type: str) -> dict[str, BetValueAnalysis]:
    """Parse bet value analysis. Uses div IDs like scroll-{section_type}-overall, scroll-{section_type}-base, etc.
    Each exists twice — once in a div.offshore-sportsbook parent, once in div.vegas-sportsbook parent.
    Values are in span.srt like "Sacramento: 30.0%".
    """
    result = {}

    metrics = {
        "overall": f"scroll-{section_type}-overall",
        "base_rating": f"scroll-{section_type}-base",
        "bet_trends": f"scroll-{section_type}-bet-trends",
        "sharp_line": f"scroll-{section_type}-sharp-line",
    }

    for book_type in ["offshore", "vegas"]:
        analysis = BetValueAnalysis()

        for metric_name, div_id in metrics.items():
            # Find all divs with this ID (duplicated for offshore/vegas)
            bars = soup.find_all("div", id=div_id)
            for bar in bars:
                # Check if this bar is inside an offshore or vegas parent
                parent = bar
                is_match = False
                for _ in range(8):
                    parent = parent.parent
                    if not parent:
                        break
                    pcls = parent.get("class", [])
                    if f"{book_type}-sportsbook" in pcls:
                        is_match = True
                        break
                    # Stop if we hit the other book type
                    other = "vegas" if book_type == "offshore" else "offshore"
                    if f"{other}-sportsbook" in pcls:
                        break

                if is_match:
                    srt = bar.find("span", class_="srt")
                    val = _parse_bar_value(srt)
                    setattr(analysis, metric_name, val)
                    break

        result[book_type] = analysis

    return result


def _parse_bar_value(srt_span: Tag | None) -> BetValueSide:
    """Parse a span.srt like "Sacramento: 30.0%" into a BetValueSide."""
    if not srt_span:
        return BetValueSide()

    text = _text(srt_span)
    # Format: "TeamName: XX.X%"
    m = re.search(r":\s*([\d.]+)", text)
    pct = float(m.group(1)) if m else 0.0

    # These bars are always one-sided (either away or home bar)
    # The bar--left class means away team, bar--right or absence means home
    parent_bar = srt_span.parent
    cls = parent_bar.get("class", []) if parent_bar else []

    if "bar--left" in cls:
        return BetValueSide(away=pct, home=0.0)
    else:
        return BetValueSide(away=0.0, home=pct)


# ──────────────────────────────────────────────
# Steam moves
# ──────────────────────────────────────────────

def _parse_steam_moves(soup: BeautifulSoup, section_type: str) -> dict[str, SteamMoves]:
    """Parse steam move cards. They're in div.compare-card inside div.offshore-sportsbook / div.vegas-sportsbook
    that are siblings after the spread/ou tables."""
    result = {}

    # Find the section heading to scope our search
    section = soup.find("div", id=f"scroll-{section_type}")
    if not section:
        return result

    # Walk siblings to find the analysis/steam div containers
    # These are div.offshore-sportsbook and div.vegas-sportsbook (not tables)
    el = section.find_next_sibling()
    next_section = "scroll-ou" if section_type == "spread" else "scroll-NONE"

    while el:
        if isinstance(el, Tag):
            eid = el.get("id", "")
            if eid == next_section:
                break
            cls = el.get("class", [])
            book_type = None
            if "offshore-sportsbook" in cls and el.name != "table":
                book_type = "offshore"
            elif "vegas-sportsbook" in cls and el.name != "table":
                book_type = "vegas"

            if book_type:
                cards = el.find_all("div", class_="compare-card")
                if cards:
                    moves = SteamMoves()
                    for card in cards:
                        card_text = ""
                        card_time = None

                        # Get the text content (before the time element)
                        for child in card.children:
                            if isinstance(child, NavigableString):
                                card_text += child.strip()
                            elif isinstance(child, Tag) and child.name != "span":
                                card_text += _text(child)

                        card_text = card_text.strip()
                        if not card_text:
                            card_text = _text(card)

                        # Get timestamp
                        time_el = card.find("time", class_="time-long")
                        if time_el:
                            card_time = time_el.get_text(separator=" ", strip=True)

                        # Normalize ½ in steam text
                        card_text = _normalize_half(card_text)

                        # "No Steam Moves" check
                        is_no_move = "no steam" in card_text.lower()

                        if is_no_move:
                            # Assign null for the appropriate side
                            if moves.away is None and not moves.home:
                                moves.away = None
                            else:
                                moves.home = None
                        elif moves.away is None and moves.away_time is None:
                            # Clean card text: remove the timestamp portion
                            clean = card_text.split("03/")[0].split("02/")[0].split("01/")[0].strip()
                            if not clean:
                                clean = card_text
                            moves.away = clean
                            moves.away_time = card_time
                        else:
                            clean = card_text.split("03/")[0].split("02/")[0].split("01/")[0].strip()
                            if not clean:
                                clean = card_text
                            moves.home = clean
                            moves.home_time = card_time

                    result[book_type] = moves

        el = el.find_next_sibling()

    return result
