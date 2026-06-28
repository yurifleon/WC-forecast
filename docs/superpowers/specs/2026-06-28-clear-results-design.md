# Admin "clear results" — design

**Date:** 2026-06-28

## Goal

Give the admin a way to wipe match results, both individually and all at once,
without touching schedule data (teams, kickoffs, venues).

## Scope decisions

- **Both** a global "clear all results" action and a per-match "clear" action.
- A **result** is `home_score`, `away_score`, and `advanced_team`. Teams,
  `kickoff_utc`, `venue`, and the `*_origin` slot codes are left untouched.
- No effect on `predictions` or `simulations` — those are separate `data` keys.

## Why scores+advance only is safe

Clearing only the result fields leaves teams and kickoffs intact, so `is_locked()`
and `is_predictable()` behave exactly as before — a pre-kickoff match reopens for
prediction once its result is cleared. `compute_points()` already treats a `None`
scoreline as "not played" and awards nothing, so the leaderboard self-corrects on
the next load.

## Backend (`app.py`, `/admin` POST dispatch)

Add after the existing `save_match` block, inside the `is_admin`-gated section so
both actions are already protected. Both fall through to the existing
`save_data(data)` + redirect at the end of the handler.

- `_clear_result(m)` — module-level helper; sets `home_score`, `away_score`,
  `advanced_team` to `None`. Single source of truth for both actions.
- `action == "clear_match_result"` — find match by `match_id` (same lookup as
  `save_match`); if found, `_clear_result(m)` and flash `"Match result cleared."`.
- `action == "clear_all_results"` — loop every match, `_clear_result(m)`; flash
  `"All results cleared."`.

## UI (`templates/admin.html`)

- **Per-match:** a separate `Clear` form (HTML forbids nested forms, so it is a
  sibling placed right after the save form), right-aligned, rendered only when the
  match has a result (`m.home_score is not none or m.advanced_team`). Guarded with
  `onsubmit="return confirm(...)"`, matching the existing remove-user idiom.
- **Global:** one `Clear all results` danger button at the top of the matches tab,
  also `confirm`-guarded.

## i18n (`translations.py`)

Spanish for: `Clear`, `Clear all results`, the two confirm prompts, and the two
flash messages (`Match result cleared.`, `All results cleared.`).

## Verification

1. `python -m py_compile app.py translations.py`.
2. Set a result, clear it per-match → score/advance blank; if before kickoff the
   match is predictable again.
3. Clear all → every match's result empty; schedule (teams/kickoffs) intact.
