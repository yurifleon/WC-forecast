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
from datetime import datetime, timezone
from functools import lru_cache
from zoneinfo import ZoneInfo

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
DISPLAY_TZ = ZoneInfo(os.environ.get("DISPLAY_TZ", "America/Lima"))
DISPLAY_TZ_LABEL = os.environ.get("DISPLAY_TZ_LABEL", "LIM")

MAX_USERS = int(os.environ.get("MAX_USERS", "20"))
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
SHORT = {"r32": "R32", "r16": "R16", "qf": "QF", "sf": "SF"}

# Standard bracket pairing: match k of a round is fed by matches (2k-1, 2k) of the
# previous round; the third-place play-off and the final both draw from the two
# semifinals (losers and winners respectively).
_FEEDER_PREV = {"r16": "r32", "qf": "r16", "sf": "qf", "final": "sf", "third": "sf"}


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
    try:
        k = int(str(match["id"]).rsplit("-", 1)[-1])
    except (ValueError, KeyError):
        return None
    return (word, f"{prev}-{2 * k - 1}", f"{prev}-{2 * k}")


DEFAULT_DATA = {
    "users": {},
    "admin_password": "change-me-admin",
    "matches": [],
    "predictions": {},
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
            matches.append({
                "id": f"{rnd}-{i}",
                "round": rnd,
                "home_team": None,
                "away_team": None,
                "kickoff_utc": None,        # tz-aware UTC ISO string, or None (TBD)
                "home_score": None,
                "away_score": None,
                "advanced_team": None,      # who went through (covers penalties)
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
        for field in ("home_team", "away_team", "kickoff_utc",
                      "home_score", "away_score", "advanced_team"):
            if field not in m:
                m[field] = None
                changed = True
        if "round" not in m:
            m["round"] = "r32"
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
        breakdown = []
        for match in data["matches"]:
            pred = user_preds.get(match["id"])
            pts = compute_points(pred, match)
            breakdown.append({"match": match, "points": pts})
            total += pts["total"]
        rows.append({"user": user, "total": total, "breakdown": breakdown})
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
    return render_template("leaderboard.html", rows=rows, matches=matches)


@app.route("/bracket")
def bracket():
    data = load_data()
    by_round = {r: [] for r in ROUND_LABELS}
    for m in sorted(data["matches"], key=lambda x: x["id"]):
        by_round.setdefault(m["round"], []).append(m)
    order = ["r32", "r16", "qf", "sf", "third", "final"]
    return render_template("bracket.html", by_round=by_round, order=order)


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
            flash(translate("User removed."), "success")

        save_data(data)
        return redirect(url_for("admin"))

    matches = sorted_matches(data["matches"])
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
