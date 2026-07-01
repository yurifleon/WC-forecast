"""
WC Forecast — FIFA World Cup 2026 knockout-stage prediction game.

Built on the lessons from UCL Forecast (see FIFA_WC_LESSONS_LEARNED.md in the
sibling UCL-forecast repo). Key differences baked in from day one:

  * A match is a SINGLE game (one score), not a two-legged tie.
  * Deadlines are stored as timezone-aware UTC and displayed via zoneinfo —
    no naive-datetime-in-a-fixed-offset (that broke UCL locking five times).
  * Knockout draws go to penalties, so users also pick the advancing team,
    scored separately from the 90'/full-time scoreline.

Single-file Flask app. State persists to data.json (gitignored) via
load_data()/save_data(); DATA_DIR env var points it at a Render disk.
"""
import json
import os
import secrets
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from flask import (
    Flask, flash, g, redirect, render_template, request, session, url_for,
)
from werkzeug.security import check_password_hash, generate_password_hash

from translations import SPANISH_TRANSLATIONS

app = Flask(__name__)
# Override in production: export SECRET_KEY=$(python -c "import secrets;print(secrets.token_hex(32))")
app.secret_key = os.environ.get("SECRET_KEY", "wc-forecast-dev-secret-change-me")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
_data_dir = os.environ.get("DATA_DIR", os.path.dirname(os.path.abspath(__file__)))
DATA_FILE = os.path.join(_data_dir, "data.json")

# Timezone the group reads deadlines in. Stored values are always UTC; this is
# only for DISPLAY and for interpreting admin datetime-local input.
# Needs the `tzdata` package on images without a system zone database (see
# requirements.txt). An invalid DISPLAY_TZ (e.g. a typo like "Central" instead of
# "America/Chicago") falls back to US Central rather than crashing boot.
_DEFAULT_TZ = "America/Chicago"


def _resolve_display_tz(name):
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        return ZoneInfo(_DEFAULT_TZ)


DISPLAY_TZ = _resolve_display_tz(os.environ.get("DISPLAY_TZ", _DEFAULT_TZ))
DISPLAY_TZ_LABEL = os.environ.get("DISPLAY_TZ_LABEL", "CT")

MAX_USERS = int(os.environ.get("MAX_USERS", "20"))
SHARE_TTL_DAYS = 7            # a shared simulation snapshot lives this long
MAX_SHARES_PER_USER = 10      # cap active shared links per user
SUPPORTED_LANGS = {"en", "es"}

# ---------------------------------------------------------------------------
# Scoring tiers — per match, by round. (See lessons guide Part 5.)
#   exact   = correct exact score
#   gd      = correct result + correct goal difference
#   result  = correct result only (win/draw/win)
#   advance = correct advancing team (knockout penalty cover), added separately
# ---------------------------------------------------------------------------
TIERS = {
    "r32":   {"exact": 6,  "gd": 4, "result": 2, "advance": 2},
    "r16":   {"exact": 7,  "gd": 5, "result": 3, "advance": 2},
    "qf":    {"exact": 8,  "gd": 5, "result": 3, "advance": 3},
    "sf":    {"exact": 9,  "gd": 6, "result": 4, "advance": 3},
    "third": {"exact": 10, "gd": 7, "result": 5, "advance": 4},
    "final": {"exact": 10, "gd": 7, "result": 5, "advance": 4},
}

# Chronological display order: Round of 32 first → Final last. Unknown rounds last.
# (Third-place play-off is played just before the Final.)
ROUND_ORDER = {"r32": 0, "r16": 1, "qf": 2, "sf": 3, "third": 4, "final": 5}
ROUND_LABELS = {
    "r32": "Round of 32", "r16": "Round of 16", "qf": "Quarter-final",
    "sf": "Semi-final", "third": "Third-place Play-off", "final": "Final",
}

# Compact round codes for bracket feed labels ("Winner R32-1"). Not translated —
# language-neutral and short enough for a narrow bracket column.
ROUND_CODE_SHORT = {"r32": "R32", "r16": "R16", "qf": "QF", "sf": "SF"}

# Standard bracket pairing: match k of a round is fed by matches (2k-1, 2k) of the
# previous round; the third-place play-off and the final both draw from the two
# semifinals (losers and winners respectively). This holds for QF -> Final.
_FEEDER_PREV = {"r16": "r32", "qf": "r16", "sf": "qf", "final": "sf", "third": "sf"}

# Round of 16 is the exception: the real FIFA WC 2026 bracket pairs R32 winners
# NON-sequentially (source: knockout-round.md, M89-M96). Each r16 match maps to its
# two feeding R32 matches explicitly. QF onward stay sequential (2k-1, 2k).
_R16_FEED = {
    "r16-1": ("r32-1", "r32-3"),    # M89: W73 vs W75
    "r16-2": ("r32-2", "r32-5"),    # M90: W74 vs W77
    "r16-3": ("r32-4", "r32-6"),    # M91: W76 vs W78
    "r16-4": ("r32-7", "r32-8"),    # M92: W79 vs W80
    "r16-5": ("r32-11", "r32-12"),  # M93: W83 vs W84
    "r16-6": ("r32-9", "r32-10"),   # M94: W81 vs W82
    "r16-7": ("r32-14", "r32-16"),  # M95: W86 vs W88
    "r16-8": ("r32-13", "r32-15"),  # M96: W85 vs W87
}

# R32 column order for the bracket/simulator tree: each r16's two feeders laid out
# adjacently (top then bottom) so the pure-CSS connectors line up. Other rounds use
# numeric order (sorted_matches); only R32 needs reshuffling because of _R16_FEED.
_BRACKET_R32_ORDER = [fid for k in range(1, 9) for fid in _R16_FEED[f"r16-{k}"]]

# 48 participating nations by group (source: FIFA_WC_2026_Master_Guide.md). Used to
# narrow the admin team dropdown to a match's possible teams.
GROUPS = {
    "A": ["Mexico", "South Africa", "South Korea", "Czechia"],
    "B": ["Canada", "Bosnia and Herzegovina", "Qatar", "Switzerland"],
    "C": ["Brazil", "Morocco", "Haiti", "Scotland"],
    "D": ["United States", "Paraguay", "Australia", "Türkiye"],
    "E": ["Germany", "Ecuador", "Côte d'Ivoire", "Curaçao"],
    "F": ["Netherlands", "Japan", "Sweden", "Tunisia"],
    "G": ["Belgium", "Egypt", "Iran", "New Zealand"],
    "H": ["Spain", "Uruguay", "Saudi Arabia", "Cape Verde"],
    "I": ["France", "Senegal", "Norway", "Iraq"],
    "J": ["Argentina", "Austria", "Algeria", "Jordan"],
    "K": ["Portugal", "Colombia", "Uzbekistan", "DR Congo"],
    "L": ["England", "Croatia", "Ghana", "Panama"],
}
ALL_TEAMS = sorted({t for teams in GROUPS.values() for t in teams})  # 48; dropdown fallback


def feeders(match):
    """Return (word, top_feeder_id, bottom_feeder_id) for a match's two slots, or
    None for Round of 32 / unknown rounds (no feeders). `word` is the untranslated
    key "Winner" or "Loser". Pure: derived from the numeric id suffix, no app
    context required."""
    rnd = match.get("round")
    prev = _FEEDER_PREV.get(rnd)
    if not prev:
        return None
    word = "Loser" if rnd == "third" else "Winner"
    if rnd in ("final", "third"):
        return (word, "sf-1", "sf-2")
    if rnd == "r16":  # non-sequential real bracket; see _R16_FEED
        pair = _R16_FEED.get(match.get("id"))
        return (word, pair[0], pair[1]) if pair else None
    try:
        k = int(str(match["id"]).rsplit("-", 1)[-1])
    except (ValueError, KeyError):
        return None
    return (word, f"{prev}-{2 * k - 1}", f"{prev}-{2 * k}")


def _short_id(feeder_id):
    """'r32-1' -> 'R32-1' for display."""
    rnd, _, num = feeder_id.rpartition("-")
    return f"{ROUND_CODE_SHORT.get(rnd, rnd.upper())}-{num}"


def feed_label_pair(match):
    """Translated placeholder labels for a match's two empty slots, e.g.
    ('Winner R32-1', 'Winner R32-2') — or (None, None) for Round of 32.
    Requires app context (uses translate())."""
    f = feeders(match)
    if not f:
        return (None, None)
    word, top, bot = f
    return (f"{translate(word)} {_short_id(top)}",
            f"{translate(word)} {_short_id(bot)}")


def _origin_groups(origin):
    """Group letters an R32 origin slot can draw from. '2A' -> ['A'];
    '3rd A/B/C/D/F' -> ['A','B','C','D','F']; unknown/empty -> []."""
    if not origin:
        return []
    if origin.startswith("3rd "):
        return [g for g in origin[4:].split("/") if g in GROUPS]
    if origin[0] in "12":  # rank 1 or 2 in a single group; "3rd ..." handled above
        g = origin[1:]
        return [g] if g in GROUPS else []
    return []


def team_options(match, side, by_id):
    """Candidate real teams for one slot of a match, for the admin dropdown.
    R32: teams from the origin's group(s) (fallback to all 48 if unparseable).
    R16/QF/SF/Final: the winner (advanced_team) of the feeding match.
    Third place: the loser of the feeding semifinal. Empty list when undecided.
    `by_id` maps match id -> match dict. Returns a sorted, de-duplicated list."""
    origin = match.get(f"{side}_origin")
    if origin:  # Round of 32
        teams = sorted({t for g in _origin_groups(origin) for t in GROUPS[g]})
        return teams or ALL_TEAMS
    f = feeders(match)
    if not f:
        return []  # unknown/unsupported round — no valid options
    word, top, bot = f
    feeder = by_id.get(top if side == "home" else bot)
    if not feeder:
        return []
    if word == "Loser":
        return [t for t in (feeder.get("home_team"), feeder.get("away_team"))
                if t and t != feeder.get("advanced_team")]
    adv = feeder.get("advanced_team")
    return [adv] if adv else []


def _sim_participants(sim, match, by_id):
    """Return (home, away) team names for a simulator match; either may be None when
    undecided. R32: the real match teams (the bracket is decided, so the simulator no
    longer lets users pick R32 teams — they only pick winners). R16+: the winner of
    each feeder match. Third-place: the LOSER of each feeding semifinal (the
    participant that is not that SF's winner). Pure-ish: reads sim + by_id."""
    rnd = match.get("round")
    if rnd == "r32":
        return (match.get("home_team"), match.get("away_team"))
    f = feeders(match)
    if not f:
        return (None, None)
    word, top, bot = f
    winners = sim.get("winners", {})

    def resolve(feeder_id):
        feeder = by_id.get(feeder_id)
        if not feeder:
            return None
        win = winners.get(feeder_id)
        if not win:
            return None
        if word == "Loser":
            ph, pa = _sim_participants(sim, feeder, by_id)
            others = [t for t in (ph, pa) if t and t != win]
            return others[0] if others else None
        return win

    return (resolve(top), resolve(bot))


def _prune_sim(sim, by_id):
    """Heal a sim in place, then return it. Drop any stored winner that is no longer
    one of its match's current participants, walking rounds in dependency order
    (r32 → final, then third) so invalidations cascade downstream. `by_id` is the real
    {id: match} map, so R32 participants resolve from the actual teams. Also drops the
    obsolete `r32` key left by pre-lock sims (teams are no longer user-picked)."""
    sim.pop("r32", None)  # legacy: simulator no longer stores R32 team picks
    winners = sim.setdefault("winners", {})
    for rnd in ("r32", "r16", "qf", "sf", "final", "third"):
        for mid, match in by_id.items():
            if match.get("round") != rnd:
                continue
            win = winners.get(mid)
            if win is None:
                continue
            home, away = _sim_participants(sim, match, by_id)
            if win not in (home, away):
                del winners[mid]
    return sim


def _share_days_left(expires_utc, now):
    """Whole days until a snapshot expires, rounded UP (6d2h -> 7). Returns 0 when
    already expired or the timestamp is unparseable (fail-closed, so callers treat
    0 as 'expired')."""
    try:
        exp = datetime.fromisoformat(expires_utc)
    except (TypeError, ValueError):
        return 0
    if exp.tzinfo is None:
        exp = exp.replace(tzinfo=timezone.utc)
    secs = (exp - now).total_seconds()
    if secs <= 0:
        return 0
    return int((secs + 86399) // 86400)  # ceil to whole days


def _purge_expired_shares(data, now):
    """Delete every shared snapshot whose TTL has elapsed. Returns True if anything
    was removed (so the caller can decide whether to save_data)."""
    shares = data.setdefault("shared_sims", {})
    dead = [t for t, s in shares.items() if _share_days_left(s.get("expires_utc"), now) == 0]
    for t in dead:
        del shares[t]
    return bool(dead)


def _create_share(data, username, sim, now):
    """Freeze `sim` into a new token-addressed snapshot owned by `username`, valid for
    SHARE_TTL_DAYS. The sim is deep-copied so later edits to the live sim never leak
    into the snapshot. Returns the new token."""
    shares = data.setdefault("shared_sims", {})
    token = secrets.token_urlsafe(8)
    while token in shares:
        token = secrets.token_urlsafe(8)
    shares[token] = {
        "owner": username,
        "created_utc": now.isoformat(),
        "expires_utc": (now + timedelta(days=SHARE_TTL_DAYS)).isoformat(),
        "sim": {
            "r32": {mid: dict(slot) for mid, slot in sim.get("r32", {}).items()},
            "winners": dict(sim.get("winners", {})),
        },
    }
    return token


def _user_shares(data, username, now):
    """Active (non-expired) snapshots owned by `username`, newest first. Each row is
    {token, days_left, created_utc} for the template (which builds the URL)."""
    rows = []
    for token, s in data.get("shared_sims", {}).items():
        if s.get("owner") != username:
            continue
        days = _share_days_left(s.get("expires_utc"), now)
        if days == 0:
            continue
        rows.append({"token": token, "days_left": days, "created_utc": s.get("created_utc", "")})
    rows.sort(key=lambda r: r["created_utc"], reverse=True)
    return rows


def _sim_view(sim, match, by_id):
    """Display fields for one simulator match: resolved participants, the label to
    show in each slot (team → R32 origin code → feed placeholder → 'TBD'), and the
    current winner."""
    home, away = _sim_participants(sim, match, by_id)
    top_lbl, bot_lbl = feed_label_pair(match)
    is_r32 = match.get("round") == "r32"

    def label(team, origin, feed):
        if team:
            return team
        if is_r32 and origin:
            return origin
        return feed or translate("TBD")

    return {
        **match,
        "sim_home": home,
        "sim_away": away,
        "home_display": label(home, match.get("home_origin"), top_lbl),
        "away_display": label(away, match.get("away_origin"), bot_lbl),
        "winner": sim.get("winners", {}).get(match["id"]),
    }


_MATCH_NO_BASE = {"r32": 72, "r16": 88, "qf": 96, "sf": 100, "third": 102, "final": 103}


def match_number(match):
    """FIFA match number (73–104), derived from round + numeric id suffix.
    r32-1->73 … r32-16->88, r16-1->89 … final-1->104. None for unknown rounds."""
    base = _MATCH_NO_BASE.get(match.get("round"))
    if base is None:
        return None
    try:
        return base + int(str(match["id"]).rsplit("-", 1)[-1])
    except (ValueError, KeyError):
        return None


def slot_label(match, side):
    """Display label for one slot of a match. Precedence:
    real team -> origin slot code (R32) -> feed-label placeholder (R16+) -> 'TBD'.
    `side` is 'home' or 'away'. Requires app context (uses translate())."""
    team = match.get(f"{side}_team")
    if team:
        return team
    origin = match.get(f"{side}_origin")
    if origin:
        return origin
    top_lbl, bot_lbl = feed_label_pair(match)
    feed = top_lbl if side == "home" else bot_lbl
    return feed or translate("TBD")


DEFAULT_DATA = {
    "users": {},
    "admin_password": "change-me-admin",
    "matches": [],
    "predictions": {},
}

# Real FIFA World Cup 2026 knockout schedule (sources: round_of_32_schedule.md,
# round_of_16_and_on_schedule.md, schedule_bracket.md). FIFA's match numbering is
# bracket-positional, so M73->r32-1 … M104->final-1 maps onto the app's positional
# pairing. kickoff_utc is converted from each host city's IANA zone (the listed clock
# is venue-local; mismatched tz tags like Houston "ET" / Mexico City "CT" are ignored)
# and re-derived + asserted in this task's test. R32 entries carry group-stage origin
# slots; R16+ rely on the bracket feed labels ("Winner R32-1") instead.
MATCH_SCHEDULE = {
    # Round of 32 (origins + real teams + kickoff + venue). Teams set once the group
    # stage finished (source: knockout-round.md, M73-M88; "Ivory Coast" -> the GROUPS
    # canonical "Côte d'Ivoire"). Backfilled fill-if-empty, so admin edits win.
    "r32-1":  {"home_origin": "2A", "away_origin": "2B",            "home_team": "South Africa", "away_team": "Canada",                 "kickoff_utc": "2026-06-28T19:00:00+00:00", "venue": "Los Angeles, USA"},
    "r32-2":  {"home_origin": "1E", "away_origin": "3rd A/B/C/D/F", "home_team": "Germany",      "away_team": "Paraguay",               "kickoff_utc": "2026-06-29T20:30:00+00:00", "venue": "Boston, USA"},
    "r32-3":  {"home_origin": "1F", "away_origin": "2C",            "home_team": "Netherlands",  "away_team": "Morocco",                "kickoff_utc": "2026-06-30T01:00:00+00:00", "venue": "Monterrey, Mexico"},
    "r32-4":  {"home_origin": "1C", "away_origin": "2F",            "home_team": "Brazil",       "away_team": "Japan",                  "kickoff_utc": "2026-06-29T17:00:00+00:00", "venue": "Houston, USA"},
    "r32-5":  {"home_origin": "1I", "away_origin": "3rd C/D/F/G/H", "home_team": "France",       "away_team": "Sweden",                 "kickoff_utc": "2026-06-29T21:00:00+00:00", "venue": "New York/New Jersey, USA"},
    "r32-6":  {"home_origin": "2E", "away_origin": "2I",            "home_team": "Côte d'Ivoire","away_team": "Norway",                 "kickoff_utc": "2026-06-30T17:00:00+00:00", "venue": "Dallas, USA"},
    "r32-7":  {"home_origin": "1A", "away_origin": "3rd C/E/F/H/I", "home_team": "Mexico",       "away_team": "Ecuador",                "kickoff_utc": "2026-07-01T01:00:00+00:00", "venue": "Mexico City, Mexico"},
    "r32-8":  {"home_origin": "1L", "away_origin": "3rd E/H/I/J/K", "home_team": "England",      "away_team": "DR Congo",               "kickoff_utc": "2026-06-30T16:00:00+00:00", "venue": "Atlanta, USA"},
    "r32-9":  {"home_origin": "1D", "away_origin": "3rd B/E/F/I/J", "home_team": "United States","away_team": "Bosnia and Herzegovina", "kickoff_utc": "2026-07-01T00:00:00+00:00", "venue": "San Francisco Bay Area, USA"},
    "r32-10": {"home_origin": "1G", "away_origin": "3rd A/E/H/I/J", "home_team": "Belgium",      "away_team": "Senegal",                "kickoff_utc": "2026-07-01T20:00:00+00:00", "venue": "Seattle, USA"},
    "r32-11": {"home_origin": "2K", "away_origin": "2L",            "home_team": "Portugal",     "away_team": "Croatia",                "kickoff_utc": "2026-07-02T23:00:00+00:00", "venue": "Toronto, Canada"},
    "r32-12": {"home_origin": "1H", "away_origin": "2J",            "home_team": "Spain",        "away_team": "Austria",                "kickoff_utc": "2026-07-02T19:00:00+00:00", "venue": "Los Angeles, USA"},
    "r32-13": {"home_origin": "1B", "away_origin": "3rd E/F/G/I/J", "home_team": "Switzerland",  "away_team": "Algeria",                "kickoff_utc": "2026-07-03T03:00:00+00:00", "venue": "Vancouver, Canada"},
    "r32-14": {"home_origin": "1J", "away_origin": "2H",            "home_team": "Argentina",    "away_team": "Cape Verde",             "kickoff_utc": "2026-07-03T22:00:00+00:00", "venue": "Miami, USA"},
    "r32-15": {"home_origin": "1K", "away_origin": "3rd D/E/I/J/L", "home_team": "Colombia",     "away_team": "Ghana",                  "kickoff_utc": "2026-07-04T01:30:00+00:00", "venue": "Kansas City, USA"},
    "r32-16": {"home_origin": "2D", "away_origin": "2G",            "home_team": "Australia",    "away_team": "Egypt",                  "kickoff_utc": "2026-07-03T18:00:00+00:00", "venue": "Dallas, USA"},
    # Round of 16 -> Final (kickoff + venue; origins omitted — feed labels render "Winner M…")
    "r16-1":  {"kickoff_utc": "2026-07-05T16:00:00+00:00", "venue": "Philadelphia, USA"},
    "r16-2":  {"kickoff_utc": "2026-07-05T22:00:00+00:00", "venue": "Houston, USA"},
    "r16-3":  {"kickoff_utc": "2026-07-06T21:00:00+00:00", "venue": "Mexico City, Mexico"},
    "r16-4":  {"kickoff_utc": "2026-07-06T19:00:00+00:00", "venue": "Arlington (Dallas), USA"},
    "r16-5":  {"kickoff_utc": "2026-07-07T16:00:00+00:00", "venue": "Atlanta, USA"},
    "r16-6":  {"kickoff_utc": "2026-07-08T02:30:00+00:00", "venue": "Seattle, USA"},
    "r16-7":  {"kickoff_utc": "2026-07-08T19:00:00+00:00", "venue": "Miami, USA"},
    "r16-8":  {"kickoff_utc": "2026-07-09T00:00:00+00:00", "venue": "Guadalajara, Mexico"},
    "qf-1":   {"kickoff_utc": "2026-07-09T21:00:00+00:00", "venue": "Boston, USA"},
    "qf-2":   {"kickoff_utc": "2026-07-11T01:00:00+00:00", "venue": "Los Angeles, USA"},
    "qf-3":   {"kickoff_utc": "2026-07-11T21:00:00+00:00", "venue": "Kansas City, USA"},
    "qf-4":   {"kickoff_utc": "2026-07-11T20:00:00+00:00", "venue": "Miami, USA"},
    "sf-1":   {"kickoff_utc": "2026-07-15T01:00:00+00:00", "venue": "Arlington (Dallas), USA"},
    "sf-2":   {"kickoff_utc": "2026-07-16T00:00:00+00:00", "venue": "Atlanta, USA"},
    "third-1": {"kickoff_utc": "2026-07-18T19:00:00+00:00", "venue": "Miami, USA"},
    "final-1": {"kickoff_utc": "2026-07-19T19:00:00+00:00", "venue": "East Rutherford (MetLife Stadium), USA"},
}


def _seed_matches():
    """Seed the 32-match knockout structure with TBD slots.

    Real teams aren't known until the group stage ends, so every slot starts as
    null (TBD); the admin fills team names + kickoff time as each round is set.
    Matches are predictable only once both team names are present (is_predictable).
    """
    matches = []
    plan = [("r32", 16), ("r16", 8), ("qf", 4), ("sf", 2), ("third", 1), ("final", 1)]
    for rnd, count in plan:
        for i in range(1, count + 1):
            mid = f"{rnd}-{i}"
            sched = MATCH_SCHEDULE.get(mid, {})
            matches.append({
                "id": mid,
                "round": rnd,
                "home_team": sched.get("home_team"),  # real team once known, else None (TBD)
                "away_team": sched.get("away_team"),
                "home_origin": sched.get("home_origin"),  # R32 slot code; None for R16+
                "away_origin": sched.get("away_origin"),
                "venue": sched.get("venue"),               # host city, or None
                "kickoff_utc": sched.get("kickoff_utc"),   # tz-aware UTC ISO, or None
                "home_score": None,
                "away_score": None,
                "advanced_team": None,                     # who went through (covers penalties)
            })
    return matches


# ---------------------------------------------------------------------------
# Data layer
# ---------------------------------------------------------------------------
def migrate_data(data):
    """Self-healing schema migration; runs on every load. Carried over from UCL —
    it let the schema evolve with zero manual migration steps."""
    changed = False
    data.setdefault("users", {})
    data.setdefault("predictions", {})
    data.setdefault("simulations", {})
    data.setdefault("shared_sims", {})
    data.setdefault("admin_password", DEFAULT_DATA["admin_password"])

    # Old format: users stored as a flat list of names.
    if isinstance(data["users"], list):
        data["users"] = {
            name.strip().lower(): {
                "email": None, "password_hash": None,
                "reset_token": None, "reset_expires": None,
                "preferred_lang": None,
            }
            for name in data["users"]
        }
        changed = True

    # Backfill missing user fields.
    for rec in data["users"].values():
        for field in ("email", "password_hash", "reset_token",
                      "reset_expires", "preferred_lang"):
            if field not in rec:
                rec[field] = None
                changed = True

    # Seed the knockout bracket on a fresh deploy.
    if not data.get("matches"):
        data["matches"] = _seed_matches()
        changed = True

    # Backfill missing match fields.
    for m in data["matches"]:
        for field in ("home_team", "away_team", "home_origin", "away_origin",
                      "venue", "kickoff_utc", "home_score", "away_score", "advanced_team"):
            if field not in m:
                m[field] = None
                changed = True
        if "round" not in m:
            m["round"] = "r32"
            changed = True

    # Backfill the real knockout schedule (origins/teams/kickoff/venue) where still
    # empty. Fill-if-empty + idempotent: never clobber admin-entered teams/scores or a
    # manually-set kickoff. Known R32 teams (MATCH_SCHEDULE) seed empty slots here too.
    for m in data["matches"]:
        sched = MATCH_SCHEDULE.get(m["id"])
        if not sched:
            continue
        for field, value in sched.items():
            if m.get(field) is None:
                m[field] = value
                changed = True

    if changed:
        _write(data)
    return data


def _write(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def load_data():
    """Read + migrate. Routes call this directly (uncached)."""
    if not os.path.exists(DATA_FILE):
        data = json.loads(json.dumps(DEFAULT_DATA))
        data = migrate_data(data)
        return data
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    return migrate_data(data)


def save_data(data):
    _write(data)
    invalidate_cache()


@lru_cache(maxsize=1)
def load_data_cached():
    """Cached read used only by before_request (lang lookup)."""
    return load_data()


def invalidate_cache():
    load_data_cached.cache_clear()


def get_match_by_id(match_id):
    if not hasattr(g, "_match_cache"):
        data = load_data()
        g._match_cache = {m["id"]: m for m in data["matches"]}
    return g._match_cache.get(str(match_id))


# ---------------------------------------------------------------------------
# Time / deadlines — UTC storage, zoneinfo display. (Lesson #1 done right.)
# ---------------------------------------------------------------------------
def get_cached_time():
    """Current time as a tz-aware UTC datetime, fixed once per request."""
    if not hasattr(g, "now"):
        g.now = datetime.now(timezone.utc)
    return g.now


@app.template_filter("deadline_tz")
def deadline_tz_filter(iso_str):
    """Render a UTC ISO deadline in the group's display timezone, WITH year."""
    if not iso_str:
        return "TBD"
    try:
        dt = datetime.fromisoformat(iso_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        local = dt.astimezone(DISPLAY_TZ)
        return f"{local.strftime('%b %d %Y, %I:%M %p')} {DISPLAY_TZ_LABEL}"
    except (ValueError, TypeError):
        return iso_str


def parse_admin_kickoff(local_str):
    """Convert an admin datetime-local string (in DISPLAY_TZ, no tz/seconds)
    into a tz-aware UTC ISO string for storage.

    datetime-local submits 'YYYY-MM-DDTHH:MM'. We attach DISPLAY_TZ, convert to
    UTC, and store full ISO with offset — so locking never hits the
    fromisoformat-without-seconds trap that silently unlocked UCL on Python<=3.10.
    """
    if not local_str:
        return None
    try:
        if len(local_str) == 16:       # no seconds
            local_str += ":00"
        naive = datetime.fromisoformat(local_str)
        localized = naive.replace(tzinfo=DISPLAY_TZ)
        return localized.astimezone(timezone.utc).isoformat()
    except (ValueError, TypeError):
        return None


def utc_iso_to_local_input(iso_str):
    """Inverse of parse_admin_kickoff, for prefilling the admin form."""
    if not iso_str:
        return ""
    try:
        dt = datetime.fromisoformat(iso_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(DISPLAY_TZ).strftime("%Y-%m-%dT%H:%M")
    except (ValueError, TypeError):
        return ""


def is_locked(match):
    """A match is locked once its kickoff has passed. TBD kickoff = not locked
    (but also not predictable until teams are set — see is_predictable)."""
    iso = match.get("kickoff_utc")
    if not iso:
        return False
    try:
        dt = datetime.fromisoformat(iso)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return get_cached_time() >= dt
    except (ValueError, TypeError):
        # Fail LOUD-ish: treat unparseable deadline as locked, never silently open.
        return True


def is_predictable(match):
    """Users can predict only matches with both teams set and not yet locked."""
    return bool(match.get("home_team") and match.get("away_team")) and not is_locked(match)


def has_teams(match):
    return bool(match.get("home_team") and match.get("away_team"))


def has_result(match):
    """A match has a result once a score or an advancing team is recorded."""
    return (match.get("home_score") is not None
            or match.get("away_score") is not None
            or bool(match.get("advanced_team")))


def _clear_result(match):
    """Wipe a match's result (score + advancing team), leaving schedule intact."""
    match["home_score"] = None
    match["away_score"] = None
    match["advanced_team"] = None


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------
def _sign(a, b):
    return (a > b) - (a < b)


def compute_points(prediction, match):
    """Points for a single knockout match prediction.

    Returns {"score": int, "advance": int, "total": int}.
    Score points come from the 90'/full-time scoreline; advance points are
    awarded separately so a penalty shootout can't zero a correct scoreline.
    """
    points = {"score": 0, "advance": 0, "total": 0}
    if not prediction:
        return points

    tier = TIERS.get(match.get("round", "r32"), TIERS["r32"])

    ah, aa = match.get("home_score"), match.get("away_score")
    if ah is not None and aa is not None:
        ph, pa = prediction.get("home"), prediction.get("away")
        if ph is not None and pa is not None:
            if ph == ah and pa == aa:
                points["score"] = tier["exact"]
            elif _sign(ph, pa) == _sign(ah, aa):
                points["score"] = tier["gd"] if (ph - pa) == (ah - aa) else tier["result"]

    actual_adv = match.get("advanced_team")
    if actual_adv and prediction.get("advance") == actual_adv:
        points["advance"] = tier["advance"]

    points["total"] = points["score"] + points["advance"]
    return points


def build_leaderboard(data):
    rows = []
    for user in data["users"].keys():
        user_preds = data["predictions"].get(user, {})
        total = 0
        score_points = 0
        advance_points = 0
        points_by_id = {}
        round_points = {rnd: 0 for rnd in ROUND_ORDER}
        for match in data["matches"]:
            pred = user_preds.get(match["id"])
            pts = compute_points(pred, match)
            points_by_id[match["id"]] = pts
            round_points[match["round"]] += pts["total"]
            score_points += pts["score"]
            advance_points += pts["advance"]
            total += pts["total"]
        rows.append({
            "user": user,
            "total": total,
            "round_points": round_points,
            "points_by_id": points_by_id,
            "score_points": score_points,
            "advance_points": advance_points,
        })
    rows.sort(key=lambda r: r["total"], reverse=True)
    return rows


def _match_sort_key(m):
    """Sort by round (chronological) then by the numeric suffix of the id
    (so r32-1 … r32-16 order numerically, not lexicographically as 1, 10, 2…)."""
    rnd = ROUND_ORDER.get(m.get("round"), 99)
    try:
        num = int(str(m["id"]).rsplit("-", 1)[-1])
    except (ValueError, KeyError):
        num = 0
    return (rnd, num)


def sorted_matches(matches):
    return sorted(matches, key=_match_sort_key)


def _tree_order(rnd, matches):
    """Order one round's matches for the bracket/simulator winner-flow tree. R32 is
    laid out by _BRACKET_R32_ORDER so each r16's feeders sit adjacent (CSS connectors
    line up); every other round uses numeric order."""
    if rnd == "r32":
        idx = {mid: i for i, mid in enumerate(_BRACKET_R32_ORDER)}
        return sorted(matches, key=lambda m: idx.get(m["id"], 99))
    return sorted_matches(matches)


# ---------------------------------------------------------------------------
# i18n
# ---------------------------------------------------------------------------
def translate(text, **kwargs):
    if getattr(g, "lang", "en") == "es":
        text = SPANISH_TRANSLATIONS.get(text, text)
    return text.format(**kwargs) if kwargs else text


def resolve_lang(data):
    username = session.get("username")
    if username:
        rec = data["users"].get(username)
        if rec and rec.get("preferred_lang") in SUPPORTED_LANGS:
            return rec["preferred_lang"]
    if session.get("lang") in SUPPORTED_LANGS:
        return session["lang"]
    best = request.accept_languages.best_match(SUPPORTED_LANGS)
    return best or "en"


@app.before_request
def before_request():
    data = load_data_cached()
    g.lang = resolve_lang(data)
    get_cached_time()


@app.context_processor
def inject_i18n_helpers():
    return {
        "_": translate,
        "lang": getattr(g, "lang", "en"),
        "round_label": lambda r: translate(ROUND_LABELS.get(r, r)),
        "is_locked": is_locked,
        "is_predictable": is_predictable,
        "has_teams": has_teams,
        "has_result": has_result,
        "slot_label": slot_label,
        "match_number": match_number,
        "compute_points": compute_points,
    }


# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------
def current_user(data):
    username = session.get("username")
    return data["users"].get(username) if username else None


def login_required():
    return bool(session.get("username"))


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.route("/", methods=["GET", "POST"])
def home():
    if request.method == "POST":
        data = load_data()
        username = request.form.get("username", "").strip().lower()
        password = request.form.get("password", "")
        rec = data["users"].get(username)
        if rec and rec.get("password_hash") and check_password_hash(rec["password_hash"], password):
            session["username"] = username
            return redirect(url_for("dashboard"))
        flash(translate("Invalid username or password."), "danger")
        return redirect(url_for("home"))

    if login_required():
        return redirect(url_for("dashboard"))
    return render_template("home.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        data = load_data()
        username = request.form.get("username", "").strip().lower()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")

        if not username or not password:
            flash(translate("Username and password are required."), "warning")
            return redirect(url_for("register"))
        if username in data["users"]:
            flash(translate("That username is taken."), "warning")
            return redirect(url_for("register"))
        if len(data["users"]) >= MAX_USERS:
            flash(translate("Registration is full ({n} players max).", n=MAX_USERS), "danger")
            return redirect(url_for("register"))

        data["users"][username] = {
            "email": email or None,
            "password_hash": generate_password_hash(password),
            "reset_token": None, "reset_expires": None,
            "preferred_lang": g.lang,
        }
        save_data(data)
        session["username"] = username
        flash(translate("Welcome, {name}!", name=username), "success")
        return redirect(url_for("dashboard"))

    return render_template("register.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("home"))


@app.route("/dashboard")
def dashboard():
    if not login_required():
        return redirect(url_for("home"))
    data = load_data()
    username = session["username"]
    preds = data["predictions"].get(username, {})
    matches = sorted_matches(data["matches"])
    leaderboard = build_leaderboard(data)[:5]
    return render_template("dashboard.html", matches=matches, predictions=preds,
                           leaderboard=leaderboard, username=username)


@app.route("/predict/<match_id>", methods=["GET", "POST"])
def predict(match_id):
    if not login_required():
        return redirect(url_for("home"))
    data = load_data()
    username = session["username"]
    match = next((m for m in data["matches"] if m["id"] == str(match_id)), None)
    if not match:
        flash(translate("Match not found."), "danger")
        return redirect(url_for("dashboard"))
    if not is_predictable(match):
        flash(translate("This match is not open for predictions."), "warning")
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        try:
            home = int(request.form.get("home", ""))
            away = int(request.form.get("away", ""))
        except (ValueError, TypeError):
            flash(translate("Please enter whole numbers for both scores."), "warning")
            return redirect(url_for("predict", match_id=match_id))
        if home < 0 or away < 0:
            flash(translate("Scores cannot be negative."), "warning")
            return redirect(url_for("predict", match_id=match_id))

        advance = request.form.get("advance", "")
        if advance not in (match["home_team"], match["away_team"]):
            flash(translate("Pick which team advances."), "warning")
            return redirect(url_for("predict", match_id=match_id))

        data["predictions"].setdefault(username, {})[match["id"]] = {
            "home": home, "away": away, "advance": advance,
        }
        save_data(data)
        flash(translate("Prediction saved."), "success")
        return redirect(url_for("dashboard"))

    existing = data["predictions"].get(username, {}).get(match["id"])
    return render_template("predict.html", match=match, prediction=existing)


@app.route("/leaderboard")
def leaderboard():
    data = load_data()
    rows = build_leaderboard(data)
    matches = sorted_matches(data["matches"])
    rounds = [
        ("r32", "R32"), ("r16", "R16"), ("qf", "QF"),
        ("sf", "SF"), ("third", "3rd"), ("final", "F"),
    ]
    return render_template("leaderboard.html", rows=rows, matches=matches, rounds=rounds)


def _bracket_view(match):
    """Resolve a match into display fields for the bracket: real team names when
    set, else origin slot codes (R32), else feed-label placeholders."""
    return {
        **match,
        "home_display": slot_label(match, "home"),
        "away_display": slot_label(match, "away"),
        "home_is_placeholder": not match.get("home_team"),
        "away_is_placeholder": not match.get("away_team"),
    }


@app.route("/bracket")
def bracket():
    data = load_data()
    tree_order = ["r32", "r16", "qf", "sf", "final"]
    columns = []
    for rnd in tree_order:
        rnd_matches = _tree_order(rnd, [m for m in data["matches"] if m.get("round") == rnd])
        columns.append({"round": rnd, "matches": [_bracket_view(m) for m in rnd_matches]})
    third_match = next((m for m in data["matches"] if m.get("round") == "third"), None)
    third = _bracket_view(third_match) if third_match else None
    return render_template("bracket.html", columns=columns, third=third)


@app.route("/simulator", methods=["GET", "POST"])
def simulator():
    if not login_required():
        return redirect(url_for("home"))
    data = load_data()
    username = session["username"]
    sims = data.setdefault("simulations", {})
    sim = sims.setdefault(username, {"winners": {}})
    sim.setdefault("winners", {})
    by_id = {m["id"]: m for m in data["matches"]}

    if request.method == "POST":
        action = request.form.get("action")
        if action == "reset":
            sims[username] = {"winners": {}}
            flash(translate("Simulator reset."), "info")
        elif action == "pick_winner":
            match = by_id.get(request.form.get("match_id"))
            team = request.form.get("team")
            if match:
                home, away = _sim_participants(sim, match, by_id)
                if team and team in (home, away):
                    sim["winners"][match["id"]] = team
                    _prune_sim(sim, by_id)
                else:
                    flash(translate("Pick a valid team for that match."), "warning")
        elif action == "share":
            if not sim.get("winners"):
                flash(translate("Nothing to share yet — make some picks first."), "warning")
            elif len(_user_shares(data, username, get_cached_time())) >= MAX_SHARES_PER_USER:
                flash(translate("You have too many active links. Revoke one first."), "warning")
            else:
                token = _create_share(data, username, sim, get_cached_time())
                url = url_for("shared_view", token=token, _external=True)
                flash(translate("Copy this link to share:") + " " + url, "success")
        elif action == "revoke":
            token = request.form.get("token")
            share = data.get("shared_sims", {}).get(token)
            if share and share.get("owner") == username:
                data["shared_sims"].pop(token, None)
                flash(translate("Link revoked."), "info")
        save_data(data)
        return redirect(url_for("simulator"))

    # Self-heal sims on view: drop winners no longer valid for their match's current
    # participants and shed the legacy r32 key. Persist only if something changed.
    before = json.dumps(sim, sort_keys=True)
    _prune_sim(sim, by_id)
    changed = json.dumps(sim, sort_keys=True) != before
    changed = _purge_expired_shares(data, get_cached_time()) or changed
    if changed:
        save_data(data)
    shares = _user_shares(data, username, get_cached_time())

    tree_order = ["r32", "r16", "qf", "sf", "final"]
    columns = []
    for rnd in tree_order:
        rnd_matches = _tree_order(rnd, [m for m in data["matches"] if m.get("round") == rnd])
        columns.append({"round": rnd, "matches": [_sim_view(sim, m, by_id) for m in rnd_matches]})
    third_match = next((m for m in data["matches"] if m.get("round") == "third"), None)
    third = _sim_view(sim, third_match, by_id) if third_match else None
    return render_template("simulator.html", columns=columns, third=third, shares=shares)


@app.route("/s/<token>")
def shared_view(token):
    data = load_data()
    now = get_cached_time()
    share = data.get("shared_sims", {}).get(token)
    expired = share is not None and _share_days_left(share.get("expires_utc"), now) == 0
    if share is None or expired:
        if expired:
            data["shared_sims"].pop(token, None)
            save_data(data)
        return render_template("shared_missing.html"), 404

    sim = share["sim"]
    by_id = {m["id"]: m for m in data["matches"]}
    tree_order = ["r32", "r16", "qf", "sf", "final"]
    columns = []
    for rnd in tree_order:
        rnd_matches = _tree_order(rnd, [m for m in data["matches"] if m.get("round") == rnd])
        columns.append({"round": rnd, "matches": [_sim_view(sim, m, by_id) for m in rnd_matches]})
    third_match = next((m for m in data["matches"] if m.get("round") == "third"), None)
    third = _sim_view(sim, third_match, by_id) if third_match else None
    return render_template(
        "shared.html",
        columns=columns,
        third=third,
        owner=share["owner"],
        days_left=_share_days_left(share["expires_utc"], now),
    )


@app.route("/set-language/<lang>")
def set_language(lang):
    if lang in SUPPORTED_LANGS:
        session["lang"] = lang
        if login_required():
            data = load_data()
            rec = data["users"].get(session["username"])
            if rec:
                rec["preferred_lang"] = lang
                save_data(data)
    return redirect(request.referrer or url_for("home"))


# ---------------------------------------------------------------------------
# Admin
# ---------------------------------------------------------------------------
@app.route("/admin", methods=["GET", "POST"])
def admin():
    data = load_data()

    if request.method == "POST":
        action = request.form.get("action")

        if action == "login":
            stored = os.environ.get("ADMIN_PASSWORD", data.get("admin_password"))
            if request.form.get("password") == stored:
                session["is_admin"] = True
                flash(translate("Admin unlocked."), "success")
            else:
                flash(translate("Wrong admin password."), "danger")
            return redirect(url_for("admin"))

        if not session.get("is_admin"):
            flash(translate("Admin access required."), "danger")
            return redirect(url_for("admin"))

        if action == "save_match":
            # One single match per pairing: teams, kickoff, and (optionally) the
            # result are all saved in a single form. Scores left blank => not yet
            # played (None); filled => the final scoreline.
            mid = request.form.get("match_id")
            m = next((x for x in data["matches"] if x["id"] == mid), None)
            if m:
                m["home_team"] = (request.form.get("home_team") or "").strip() or None
                m["away_team"] = (request.form.get("away_team") or "").strip() or None
                m["kickoff_utc"] = parse_admin_kickoff(request.form.get("kickoff"))

                scores = {}
                for side in ("home", "away"):
                    raw = (request.form.get(f"{side}_score") or "").strip()
                    if raw == "":
                        scores[side] = None
                    else:
                        try:
                            scores[side] = int(raw)
                        except ValueError:
                            flash(translate("Enter whole numbers for both scores."), "warning")
                            return redirect(url_for("admin"))
                m["home_score"], m["away_score"] = scores["home"], scores["away"]

                adv = (request.form.get("advanced_team") or "").strip()
                m["advanced_team"] = adv if adv in (m["home_team"], m["away_team"]) else None
                flash(translate("Match saved."), "success")

        elif action == "clear_match_result":
            # Wipe just this match's result (score + advancing team); leave the
            # schedule (teams, kickoff, venue) intact so locking/predictability
            # are unchanged.
            mid = request.form.get("match_id")
            m = next((x for x in data["matches"] if x["id"] == mid), None)
            if m:
                _clear_result(m)
                flash(translate("Match result cleared."), "success")

        elif action == "clear_all_results":
            for m in data["matches"]:
                _clear_result(m)
            flash(translate("All results cleared."), "success")

        elif action == "add_user":
            uname = request.form.get("username", "").strip().lower()
            pwd = request.form.get("password", "")
            if not uname or not pwd:
                flash(translate("Username and password are required."), "warning")
            elif uname in data["users"]:
                flash(translate("That username is taken."), "warning")
            elif len(data["users"]) >= MAX_USERS:
                flash(translate("Registration is full ({n} players max).", n=MAX_USERS), "danger")
            else:
                data["users"][uname] = {
                    "email": request.form.get("email", "").strip() or None,
                    "password_hash": generate_password_hash(pwd),
                    "reset_token": None, "reset_expires": None, "preferred_lang": None,
                }
                flash(translate("User created."), "success")

        elif action == "reset_user_password":
            uname = request.form.get("username", "").strip().lower()
            new_pwd = request.form.get("password") or secrets.token_urlsafe(8)
            rec = data["users"].get(uname)
            if rec:
                rec["password_hash"] = generate_password_hash(new_pwd)
                flash(translate("Password for {name} set to: {pw}", name=uname, pw=new_pwd), "info")

        elif action == "remove_user":
            uname = request.form.get("username", "").strip().lower()
            data["users"].pop(uname, None)
            data["predictions"].pop(uname, None)   # clean orphaned predictions
            data["simulations"].pop(uname, None)   # clean orphaned simulation
            data["shared_sims"] = {t: s for t, s in data.get("shared_sims", {}).items()
                                   if s.get("owner") != uname}  # drop their shared links
            flash(translate("User removed."), "success")

        save_data(data)
        return redirect(url_for("admin"))

    by_id = {m["id"]: m for m in data["matches"]}
    matches = [
        {**m, "home_options": team_options(m, "home", by_id),
              "away_options": team_options(m, "away", by_id)}
        for m in sorted_matches(data["matches"])
    ]
    return render_template(
        "admin.html",
        is_admin=session.get("is_admin", False),
        matches=matches,
        users=data["users"],
        utc_iso_to_local_input=utc_iso_to_local_input,
        tz_label=DISPLAY_TZ_LABEL,
    )


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=True)
