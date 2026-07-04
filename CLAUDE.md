# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

`WC Forecast` — a single-file Flask app for a private **FIFA World Cup 2026
knockout-stage** prediction game (≤20 friends). Knockout only: Round of 32 → R16
→ QF → SF → Third-place → Final. Spanish-first audience.

Derived from the `UCL-forecast` sibling repo; read its `FIFA_WC_LESSONS_LEARNED.md`
for design rationale. The crucial difference from UCL: **a match is a single game
with one score**, not a two-legged tie.

## Commands

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python app.py                       # dev server, debug=True, port 5000

python -m py_compile app.py translations.py   # syntax check (no test suite)

# Quick scoring check
python -c "
from app import compute_points
m = {'round':'r32','home_score':2,'away_score':1,'advanced_team':'A'}
print(compute_points({'home':2,'away':1,'advance':'A'}, m))  # {'score':6,'advance':2,'total':8}
"
```

## Configuration & deploy

All config is via env vars (read at import in `app.py`):

| Var | Default | Purpose |
|-----|---------|---------|
| `DATA_DIR` | project dir | Where `data.json` lives. **Must point at the Render persistent disk (`/data`) before first signup** or state is wiped each deploy. |
| `SECRET_KEY` | dev fallback | Flask session secret. Set in prod. |
| `ADMIN_PASSWORD` | value in `data.json` | Overrides the stored admin password (the only `sync: false` var in `render.yaml`). |
| `DISPLAY_TZ` | `America/Chicago` | TZ deadlines render in and admin `datetime-local` input is interpreted as. Invalid name falls back via `_resolve_display_tz`. |
| `DISPLAY_TZ_LABEL` | `CT` | Label shown next to times. |
| `MAX_USERS` | `20` | Registration cap. |
| `PORT` | `5000` | HTTP port (Render sets this; `app.py` dev server reads it too). |

Deploy is Render via the `render.yaml` blueprint (Starter plan + 1GB disk at `/data`;
`autoDeploy` on). `Procfile` runs `gunicorn app:app`; `runtime.txt` pins Python 3.12.3;
`tzdata` is a hard requirement in `requirements.txt` (slim images lack a system zone DB).
**Gotcha:** editing env vars in `render.yaml` does **not** sync to a live service — change
them in the Render dashboard too. Free plan has no disk, so it wipes all state per deploy.

## Architecture

**Data layer:** JSON flat file `data.json` (gitignored). `load_data()` /
`save_data()`; `migrate_data()` runs on every load (self-healing schema; on a fresh
deploy `_seed_matches()` builds all 32 matches, then `MATCH_SCHEDULE` is backfilled
field-by-field, fill-if-empty so admin-entered teams/scores/kickoffs are never
clobbered). `DATA_DIR` env var relocates the file to a Render disk. A per-request
`lru_cache` (`load_data_cached`) is used only by `before_request`; routes call
`load_data()` directly.

**Data model:**
```jsonc
{
  "users":   { "yuri": { "email", "password_hash", "reset_token", "reset_expires", "preferred_lang" } },
  "admin_password": "...",
  "matches": [{ "id": "r32-1", "round": "r32", "home_team", "away_team",
                "home_origin", "away_origin", // group-slot codes ("2A", "3rd A/B/C/D/F"); R32 only, null on R16+
                "venue",                  // host city string, or null
                "kickoff_utc",            // tz-aware UTC ISO string, or null (TBD)
                "home_score", "away_score", "advanced_team" }],
  "predictions": { "yuri": { "r32-1": { "home": 2, "away": 1, "advance": "Brazil" } } },
  "simulations": { "yuri": { "winners": { "r32-1": "Canada", "r16-1": "Morocco" } } }
}
```
Match `id` is a **string** everywhere (e.g. `"r32-1"`) — no int/str split like UCL had.
Predictions are keyed by the same string id.

**Real schedule (`MATCH_SCHEDULE`):** the actual FIFA WC 2026 knockout bracket
(origins + venues + UTC kickoffs + now the known **R32 teams**) is hardcoded and
seeded/backfilled fill-if-empty on load (admin edits always win). Source schedule docs:
`knockout-round.md` (R32 matchups + the authoritative non-sequential R16 feed),
`round_of_32_schedule.md`, `round_of_16_and_on_schedule.md`, `schedule_bracket.md`,
`FIFA_WC_2026_Master_Guide.md`. R32 entries carry group-stage `*_origin` slot codes
**and** real `home_team`/`away_team` (the group stage is over); R16+ leave teams null
and rely on bracket feed labels. Note: team names use the GROUPS canonical form
(e.g. `Côte d'Ivoire`, not "Ivory Coast").

**FIFA match numbers (`match_number`):** every knockout game has a FIFA match number
M73–M104, derived from round + numeric id suffix (`r32-1`→73 … `final-1`→104) via
`_MATCH_NO_BASE`. Returns None for unknown rounds. Shown on bracket/dashboard/predict.

**Teams (`GROUPS`, `team_options`, `slot_label`):** `GROUPS` holds the 48 nations by
group letter (A–L); `ALL_TEAMS` is the flat fallback. `team_options(match, side, by_id)`
narrows the admin team dropdown — for R32 to the origin slot's group(s) (via
`_origin_groups`), for R16+ to the winner (`advanced_team`) of the feeding match, for
`third` to the SF losers. `slot_label(match, side)` is the display label with
precedence: real team → origin slot code → feed-label placeholder (`Winner R32-1`) → `TBD`.

**Single-match model:** every knockout game has ONE score (`home_score`/`away_score`)
and an `advanced_team` (covers penalty shootouts). There are no "legs". This is the
deliberate correction of UCL's two-legged-tie assumption.

**Timezones (do not regress):** deadlines stored as tz-aware **UTC** ISO strings.
- `parse_admin_kickoff()` — converts admin `datetime-local` input (in `DISPLAY_TZ`,
  no seconds) → UTC ISO. Appends `:00` for the 16-char no-seconds case.
- `deadline_tz` filter — renders UTC → `DISPLAY_TZ` with year + label.
- `is_locked()` — compares `get_cached_time()` (UTC, fixed once per request via `g`)
  to the stored UTC deadline. Unparseable deadline → **locked** (fail safe, never
  silently open — that was a real UCL bug).

**Predictability:** `is_predictable(match)` = both teams set AND not locked. Seeded
matches start with `home_team`/`away_team` = null (TBD) and open once admin sets them.

**Scoring (`compute_points`):** returns `{"score", "advance", "total"}`. Tier by
`match["round"]` from the `TIERS` table. Score from full-time scoreline using the
`_sign(a,b)` trick; advance points awarded separately (so a penalty shootout can't
zero a correct scoreline). The `TIERS` table (`third` == `final`):

| Outcome              | r32 | r16 | qf | sf | third/final |
|----------------------|-----|-----|----|----|-------------|
| `exact` (scoreline)  | 6   | 7   | 8  | 9  | 10          |
| `gd` (result + GD)   | 4   | 5   | 5  | 6  | 7           |
| `result` (1X2 only)  | 2   | 3   | 3  | 4  | 5           |
| `advance` (added)    | +2  | +2  | +3 | +3 | +4          |

**Leaderboard (`build_leaderboard`, `/leaderboard`):** one row per user with `total`,
`score_points`/`advance_points` (split totals), `round_points` (per-round `{round: pts}`
over `ROUND_ORDER`), and `points_by_id` (`{match_id: compute_points(...)}` for the full
per-match matrix). Rows sort by `total` desc. The template renders a per-round summary
plus a full per-match points matrix; matrix column headers use `match_short(match)` —
`"CAN-MEX"` (3-letter matchup code) when both real teams are set, else `"M{n}"` (FIFA
match number). Codes come from `TEAM_ABBR` (per-team EN/ES 3-letter tuple; `team_abbr`
falls back to `team[:3].upper()`).

**i18n:** EN + ES. Strings go through `translate()` / `_()` (injected into templates).
Spanish lives in `translations.py` (separate module, not inline — a UCL lesson).
Lang resolution: user `preferred_lang` → `session["lang"]` → `Accept-Language` → `en`.

**Auth:** username+password, PBKDF2 (Werkzeug). `/register` self-serve (capped at
`MAX_USERS`). Admin is a separate password gate (`session["is_admin"]`,
`ADMIN_PASSWORD` env overrides stored value). No email reset yet; admin can reset.
Admin POST actions: `save_match` (edits teams, **venue**, kickoff, score,
`advanced_team` in one form — venue is a plain text field, kickoff a `datetime-local`
in `DISPLAY_TZ`), `clear_match_result` / `clear_all_results` (wipe score +
`advanced_team` via `_clear_result`, leaving schedule/teams/kickoff/venue intact so
locking is unaffected), `add_user`, `reset_user_password`, `remove_user`.

**Routes:** `/` (login), `/register`, `/logout`, `/dashboard`, `/predict/<id>`,
`/leaderboard`, `/bracket`, `/simulator`, `/s/<token>` (public, read-only shared sim),
`/admin`, `/set-language/<lang>`.

**Round sorting:** `ROUND_ORDER = {r32:0 … final:5}` sorts matches **chronologically**
(Round of 32 first → Final last); unknown rounds last (99). `sorted_matches()` breaks
ties by the numeric id suffix (`r32-1…r32-16`, not lexicographic). Dashboard and admin
render all rounds via `sorted_matches()` in this sequence; `/bracket` uses its own
tree layout (see Bracket view).

**Bracket view (`/bracket`):** renders the knockout as a **winner-flow tree**, not flat
columns. The feeding relationship is **derived, not stored** — `feeders(match)` maps a
match to the two previous-round matches feeding it. SF→Final use the sequential rule
(match *k* ← `(2k-1, 2k)`; `final`/`third` ← `sf-1`/`sf-2`, winners/losers). **R16 AND QF
are non-sequential exceptions:** the real FIFA WC26 bracket pairs winners
**non-sequentially**, so their feeders come from explicit maps — `_R16_FEED` (`r16-1` ←
`r32-1` + `r32-3`, etc.; source `knockout-round.md`, M89–M96) and `_QF_FEED` (`qf-2` ←
`r16-5` + `r16-6`, `qf-3` ← `r16-3` + `r16-4` — the middle two QFs draw from swapped R16
pairs; source Wikipedia "2026 FIFA World Cup knockout stage", M97–M100: M98 = W93 v W94,
M99 = W91 v W92). SF stays sequential (M101 = W97 v W98, M102 = W99 v W100).
`feed_label_pair()` turns feeders into placeholder labels (`Winner R32-3`, `Loser SF-2`,
via `ROUND_CODE_SHORT`) shown in empty downstream slots until real teams arrive. The route
builds `columns` over `["r32","r16","qf","sf","final"]` (each match resolved through
`_bracket_view`, which adds `*_display`/`*_is_placeholder`), passing `third` **separately**.
The R32 **and R16** columns are ordered by `_tree_order` → `_BRACKET_R32_ORDER` /
`_BRACKET_R16_ORDER` (each downstream match's two feeders laid out adjacently, cascading
through `_QF_FEED`→`_R16_FEED`) so the **pure-CSS** connectors line up — `:is()` elbow
pseudo-elements in `base.html`; alignment relies on equal-flex match cells + flex-default
`align-items:stretch` (load-bearing). Other columns use numeric order; dashboard/admin/predict
use `sorted_matches` (numeric), unaffected.
Design + plan: `docs/superpowers/specs/` and `docs/superpowers/plans/`.

**Simulator (`/simulator`):** a private per-user "what-if" bracket, **completely
separate from `predictions`/scoring** — it earns no points and lives under its own
`data["simulations"][username]` key (`{"winners": {match_id: team}}`). Now that the group
stage is over, **R32 is locked to the real matchups** — the simulator no longer lets users
pick R32 teams; they only **pick the winner** of each match and the bracket cascades
forward. Participants are **derived, not stored** — `_sim_participants()` returns the real
`home_team`/`away_team` for R32, and for R16+ walks `feeders()` (winner of each feeder;
third-place = the SF *loser*). `_prune_sim(sim, by_id)` runs after every mutation (and
self-heals on view): it sheds the legacy `r32` key from pre-lock sims and cascades
r32→final→third to drop winners no longer valid for their (possibly changed) participants.
`_sim_view()` adds `sim_home/sim_away`, `*_display` (team → R32 origin code → feed
placeholder → `TBD`), and `winner`. POST actions: `pick_winner`, `reset`, `share`,
`revoke`. Same winner-flow tree layout as `/bracket` (third rendered separately).

**Shared snapshots:** "Save & share" (`action=share`) deep-copies the user's sim into
`data["shared_sims"][token]` (`token`=`secrets.token_urlsafe(8)`) with a 7-day
`expires_utc`; the public, login-free `GET /s/<token>` (`shared_view`) renders it
read-only via `_sim_view` over the frozen sim. Snapshots are **never** pruned. Owners
see active links (`_user_shares`) with copy + `revoke`. Expiry is lazy — `_purge_expired_shares`
runs on `/simulator` load and when `/s/` hits an expired token. Missing/expired both
return the same 404 `shared_missing.html`.

**Neutral-venue framing:** WC knockouts are at neutral sites, so the UI shows no
home/away (local/visitor) labels (commit `15adefb`). The fields are still named
`home_team`/`away_team`/`home_score`/`away_score` internally — that's storage only;
don't reintroduce home/away wording in templates.

**Templates:** Jinja2 + Bootstrap 5.3 dark theme, **no custom JS**. Keep logic in
Python helpers and inject view helpers via the `inject_i18n_helpers` context processor
(`_`, `lang`, `round_label`, `is_locked`, `is_predictable`, `has_teams`, `has_result`,
`slot_label`, `match_number`, `match_short`, `compute_points`).

## Code style

- 4-space indent, PEP 8, f-strings. `snake_case` funcs/vars, `UPPER_SNAKE` constants.
- `flash(..., "danger"|"warning"|"success"|"info")` for feedback; catch specific
  exceptions (`ValueError`, `TypeError`, `KeyError`).
- Keep business logic in Python helpers, not templates.
- No linter/formatter is configured — style is enforced by convention only;
  `python -m py_compile` is the sole automated check.

## Gotchas

- Match ids are strings (`"r32-1"`); never coerce to int.
- Mutating in-memory `data` without `save_data(data)` silently drops changes.
- Removing a user must also drop `data["predictions"][user]` (orphan cleanup).
- Never store naive local datetimes — UTC in, `DISPLAY_TZ` out only at render.
- Never let an `except` return a "safe" default that hides a broken core mechanic
  (locking). Fail loud or fail locked.
- Valid rounds (lowercase): `r32`, `r16`, `qf`, `sf`, `third`, `final`.

## Pre-completion checklist

1. `python -m py_compile app.py translations.py` passes.
2. Run the quick scoring check if `compute_points`/`TIERS` changed.
3. Test locking around a deadline boundary if time logic changed.
4. No `data.json` or secrets staged.
