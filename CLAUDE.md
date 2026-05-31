# CLAUDE.md

Guidance for Claude Code when working in this repo.

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

## Architecture

**Data layer:** JSON flat file `data.json` (gitignored). `load_data()` /
`save_data()`; `migrate_data()` runs on every load (self-healing schema, seeds the
32-match bracket if empty). `DATA_DIR` env var relocates the file to a Render disk.
A per-request `lru_cache` (`load_data_cached`) is used only by `before_request`;
routes call `load_data()` directly.

**Data model:**
```jsonc
{
  "users":   { "yuri": { "email", "password_hash", "reset_token", "reset_expires", "preferred_lang" } },
  "admin_password": "...",
  "matches": [{ "id": "r32-1", "round": "r32", "home_team", "away_team",
                "kickoff_utc",            // tz-aware UTC ISO string, or null (TBD)
                "home_score", "away_score", "advanced_team" }],
  "predictions": { "yuri": { "r32-1": { "home": 2, "away": 1, "advance": "Brazil" } } }
}
```
Match `id` is a **string** everywhere (e.g. `"r32-1"`) — no int/str split like UCL had.
Predictions are keyed by the same string id.

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
`_sign(a,b)` trick; advance points awarded separately. See README for the table.

**i18n:** EN + ES. Strings go through `translate()` / `_()` (injected into templates).
Spanish lives in `translations.py` (separate module, not inline — a UCL lesson).
Lang resolution: user `preferred_lang` → `session["lang"]` → `Accept-Language` → `en`.

**Auth:** username+password, PBKDF2 (Werkzeug). `/register` self-serve (capped at
`MAX_USERS`). Admin is a separate password gate (`session["is_admin"]`,
`ADMIN_PASSWORD` env overrides stored value). No email reset yet; admin can reset.

**Routes:** `/` (login), `/register`, `/logout`, `/dashboard`, `/predict/<id>`,
`/leaderboard`, `/bracket`, `/admin`, `/set-language/<lang>`.

**Round sorting:** `ROUND_ORDER = {r32:0 … final:5}` sorts matches **chronologically**
(Round of 32 first → Final last); unknown rounds last (99). `sorted_matches()` breaks
ties by the numeric id suffix (`r32-1…r32-16`, not lexicographic). Dashboard and admin
render all rounds via `sorted_matches()` in this sequence; `/bracket` uses its own
tree layout (see Bracket view).

**Bracket view (`/bracket`):** renders the knockout as a **winner-flow tree**, not flat
columns. The feeding relationship is **derived, not stored** — `feeders(match)` maps a
match to the two previous-round matches feeding it (match *k* ← `(2k-1, 2k)`;
`final`/`third` ← `sf-1`/`sf-2`, winners/losers respectively). `feed_label_pair()` turns
that into placeholder labels (`Winner R32-1`, `Loser SF-2`, via `ROUND_CODE_SHORT`)
shown in empty downstream slots until the admin fills real teams. The route builds
`columns` over `["r32","r16","qf","sf","final"]` (each match resolved through
`_bracket_view`, which adds `*_display`/`*_is_placeholder` fields) and passes `third`
**separately** as a standalone card (it's fed by SF losers, so it sits outside the
winner tree). Connectors are **pure CSS** — `:is()` elbow pseudo-elements in
`base.html`; alignment relies on equal-flex match cells + the flex-default
`align-items:stretch` (load-bearing). Design + plan: `docs/superpowers/specs/` and
`docs/superpowers/plans/`.

**Neutral-venue framing:** WC knockouts are at neutral sites, so the UI shows no
home/away (local/visitor) labels (commit `15adefb`). The fields are still named
`home_team`/`away_team`/`home_score`/`away_score` internally — that's storage only;
don't reintroduce home/away wording in templates.

**Templates:** Jinja2 + Bootstrap 5.3 dark theme, **no custom JS**. Keep logic in
Python helpers and inject view helpers via the `inject_i18n_helpers` context processor
(`_`, `round_label`, `is_locked`, `is_predictable`, `has_teams`, `compute_points`).

## Code style

- 4-space indent, PEP 8, f-strings. `snake_case` funcs/vars, `UPPER_SNAKE` constants.
- `flash(..., "danger"|"warning"|"success"|"info")` for feedback; catch specific
  exceptions (`ValueError`, `TypeError`, `KeyError`).
- Keep business logic in Python helpers, not templates.

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
