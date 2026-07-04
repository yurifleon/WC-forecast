# Reveal player forecasts in the classification table — Design

_2026-07-04_

## Goal

On the `/leaderboard` ("Clasificación") page, show each player's **forecast**
(predicted scoreline + advancing-team pick) for every knockout match — but reveal
another player's forecast for a match only **after that match has kicked off**, so
players can't copy each other before the deadline. A player always sees their own
forecast.

## Where

Augment the existing **"Points by match"** matrix (`leaderboard.html`, the second
table). Each cell is already one `player × match`, showing a points badge. The
forecast renders **in that same cell, beneath the points badge** — mirroring the
column header, which already stacks the match code over the final score.

No new page, no new table. The top summary table and the scoring key are unchanged.

## Visibility rule (evaluated per cell)

A cell's forecast is **shown** when **either**:

- the cell's player **is the current viewer** (`row.user == viewer`) — your own is
  always visible; **or**
- the match has **kicked off**: `is_locked(match)` is true.

Otherwise the cell shows a muted placeholder (`·`) with a `title="Hidden until
kickoff"` tooltip.

`viewer = session.get("username")` — may be `None`, because `/leaderboard` is public
(no `login_required`). For an anonymous viewer there is no "own", so forecasts are
gated purely by `is_locked`.

Rationale: `is_locked` already returns true once kickoff (the prediction deadline)
passes, and fails **locked** on an unparseable/missing deadline — so a forecast can
never leak early through a bad timestamp.

## Content per cell

Given visibility above:

| State | Render (below the points badge) |
|-------|---------------------------------|
| Visible, prediction exists | `2-1` + advance pick as a 3-letter code, e.g. **`2-1 ·BRA`** |
| Visible, no prediction made | muted `—` |
| Not visible | muted placeholder `·` (tooltip "Hidden until kickoff") |

- Scoreline is `pred.home`-`pred.away`.
- Advance code uses the existing `team_abbr(team, lang)` helper (lang-aware; falls
  back to `team[:3].upper()`), applied to `pred.advance`.
- The points badge above is **unchanged** (green badge for >0, muted `0` otherwise).

## Data flow

- **`build_leaderboard`** — add `pred_by_id` to each row: the user's raw predictions
  map `{match_id: {"home", "away", "advance"}}` (i.e. `data["predictions"].get(user,
  {})`). This sits next to the existing `points_by_id`. No other aggregate changes.
- **`leaderboard()` route** — pass `viewer=session.get("username")` to the template.
- **`leaderboard.html`** — in each matrix cell, after the points badge, render the
  forecast gated by `row.user == viewer or is_locked(m)`. `is_locked` and `team_abbr`
  are already injected via `inject_i18n_helpers`.

**No data-model change. No scoring change.** `compute_points`, `TIERS`, and the
summary/round aggregates are untouched. This is purely additive display.

## i18n

- Reuse `team_abbr` for the advance code (no new logic).
- Add one string: **"Hidden until kickoff"** (EN) → **"Oculto hasta el inicio"** (ES)
  in `translations.py`.

## Testing (manual, via Flask test client — no suite exists)

Seed a match that is locked (kickoff in the past) and one open (future), with two
users who have predictions, and render `/leaderboard`:

1. **Own visible pre-lock** — viewer=userA sees userA's forecast on the *open* match.
2. **Others hidden pre-lock** — viewer=userA does **not** see userB's forecast on the
   open match (placeholder shown).
3. **Others revealed post-lock** — viewer=userA sees userB's forecast on the *locked*
   match.
4. **No prediction** — a user with no prediction for a visible match shows `—`.
5. **Anonymous viewer** — no session: forecasts show only for locked matches.
6. Points badges and totals are unchanged (regression guard).

## Out of scope

- No reveal on the dashboard or predict pages (leaderboard only).
- No "reveal all at round start" global mode — per-match kickoff gating only.
- No change to how or when predictions are made/locked.
