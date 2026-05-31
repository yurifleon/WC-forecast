# R32 Schedule → Bracket Mapping — Design

**Date:** 2026-05-31
**Scope:** Seed the 16 Round-of-32 matches with their real FIFA 2026 kickoff times and
team-origin slot labels (`2A`, `1E`, `3rd A/B/C/D/F`, …), and display the origins until
real teams are known. Touches `app.py` (schema seed + migration + one view helper),
`templates/bracket.html`, `templates/dashboard.html`, `templates/predict.html`. No
scoring/locking change.

**Sources (committed into the repo as reference data):**
`round_of_32_schedule.md` (fixtures: date, local time, host city, origins) and
`schedule_bracket.md` (full M73→M104 adjacency).

## Key insight: sequential mapping is bracket-faithful

FIFA's match numbers are already bracket-positional: M73&M74→M89, M75&M76→M90, …,
M101&M102→Final (M104), losers→Third (M103). This maps exactly onto the app's positional
pairing (`feeders()`: `r16-k ← r32-(2k-1), r32-(2k)`). Therefore **M73→`r32-1`,
M74→`r32-2`, … M88→`r32-16`** makes the bracket tree show true future matchups. No
reordering needed; the existing `Winner R32-1`-style feed labels correctly describe R16+.

## Data model: two new fields

Add to every match:
- `home_origin` — string slot code (e.g. `"2A"`, `"3rd A/B/C/D/F"`) for R32; `null` for
  R16+ (the feed-label system already covers those).
- `away_origin` — same.

Real `home_team`/`away_team` remain `null` until the admin sets them after the group
stage. Origins are **display-only** — see "Display & predictability" below.

## Source-of-truth table

A module constant in `app.py`:

```python
R32_SCHEDULE = {
    "r32-1":  {"home_origin": "2A", "away_origin": "2B",              "kickoff_utc": "2026-06-28T19:00:00+00:00"},
    "r32-2":  {"home_origin": "1E", "away_origin": "3rd A/B/C/D/F",   "kickoff_utc": "2026-06-29T20:30:00+00:00"},
    "r32-3":  {"home_origin": "1F", "away_origin": "2C",              "kickoff_utc": "2026-06-30T01:00:00+00:00"},
    "r32-4":  {"home_origin": "1C", "away_origin": "2F",              "kickoff_utc": "2026-06-29T17:00:00+00:00"},
    "r32-5":  {"home_origin": "1I", "away_origin": "3rd C/D/F/G/H",   "kickoff_utc": "2026-06-29T21:00:00+00:00"},
    "r32-6":  {"home_origin": "2E", "away_origin": "2I",              "kickoff_utc": "2026-06-30T17:00:00+00:00"},
    "r32-7":  {"home_origin": "1A", "away_origin": "3rd C/E/F/H/I",   "kickoff_utc": "2026-07-01T01:00:00+00:00"},
    "r32-8":  {"home_origin": "1L", "away_origin": "3rd E/H/I/J/K",   "kickoff_utc": "2026-06-30T16:00:00+00:00"},
    "r32-9":  {"home_origin": "1D", "away_origin": "3rd B/E/F/I/J",   "kickoff_utc": "2026-07-01T00:00:00+00:00"},
    "r32-10": {"home_origin": "1G", "away_origin": "3rd A/E/H/I/J",   "kickoff_utc": "2026-07-01T20:00:00+00:00"},
    "r32-11": {"home_origin": "2K", "away_origin": "2L",              "kickoff_utc": "2026-07-02T23:00:00+00:00"},
    "r32-12": {"home_origin": "1H", "away_origin": "2J",              "kickoff_utc": "2026-07-02T19:00:00+00:00"},
    "r32-13": {"home_origin": "1B", "away_origin": "3rd E/F/G/I/J",   "kickoff_utc": "2026-07-03T03:00:00+00:00"},
    "r32-14": {"home_origin": "1J", "away_origin": "2H",              "kickoff_utc": "2026-07-03T22:00:00+00:00"},
    "r32-15": {"home_origin": "1K", "away_origin": "3rd D/E/I/J/L",   "kickoff_utc": "2026-07-04T01:30:00+00:00"},
    "r32-16": {"home_origin": "2D", "away_origin": "2G",              "kickoff_utc": "2026-07-03T18:00:00+00:00"},
}
```

These UTC values are pre-verified with `zoneinfo` (see "Timezone conversion"). The plan
includes a check that regenerates them from the venue zones and asserts equality, so the
table can't silently drift.

## Timezone conversion — by venue, not abbreviation

The schedule's `PT/ET/MT/CT` tags are inconsistent with the actual venue zones (notably
Mexico City, tagged `CT` but actually UTC-6, not US-Central UTC-5). Each kickoff is
converted from the **host city's IANA zone** using `zoneinfo`, which handles DST
correctly (US/Canada observe DST in late June/early July 2026; Mexico does not):

| Venue(s) | IANA zone | Summer 2026 offset |
|---|---|---|
| Los Angeles, San Francisco Bay, Seattle | `America/Los_Angeles` | UTC-7 |
| Vancouver | `America/Vancouver` | UTC-7 |
| Boston, New York/New Jersey, Atlanta, Miami | `America/New_York` | UTC-4 |
| Toronto | `America/Toronto` | UTC-4 |
| Houston, Dallas, Kansas City | `America/Chicago` | UTC-5 |
| Monterrey | `America/Monterrey` | UTC-6 |
| Mexico City | `America/Mexico_City` | UTC-6 |

**Resolved judgment call:** Mexico City (M79) 7:00 PM local → `2026-07-01T01:00:00+00:00`
(UTC-6), overriding the file's `CT` tag. Monterrey (M75) coincides at UTC-6 either way.

## Seed + self-healing migration (no throwaway script)

`data.json` is gitignored and lives on the Render persistent disk, so editing a local
copy would not reach production. Instead, following the app's existing self-healing
pattern:

1. **`_seed_matches()`** — when building an R32 match, populate `home_origin`,
   `away_origin`, and `kickoff_utc` from `R32_SCHEDULE[id]`. R16+ matches get
   `home_origin`/`away_origin` = `None` (and `kickoff_utc` = `None` as today). Fresh
   deploys get the full schedule immediately.

2. **`migrate_data()`** — runs on every load; backfill **fill-if-empty, idempotent**:
   - Ensure every match dict has `home_origin`/`away_origin` keys (default `None`),
     alongside the existing field-backfill loop.
   - For each `r32-*` match: if `home_origin` is `None`, set it from the table; same for
     `away_origin`; if `kickoff_utc` is `None`, set it from the table.
   - **Never overwrite** a non-null value. This protects admin-entered teams/scores and
     any manually-adjusted kickoff. (Real `home_team`/`away_team` are never touched here.)
   - Set `changed = True` and persist (existing mechanism) when any backfill occurs.

This upgrades the existing on-disk `data.json` (16 R32 matches currently all-null) on the
next load, on both local and Render.

## Display & predictability

- **Resolution helper (single source of truth):** add one Python helper
  `slot_label(match, side)` returning `team or origin or <feed label> or "TBD"` for
  `side in {"home","away"}`. `_bracket_view` calls it for `home_display`/`away_display`
  (replacing its current `team or feed_label or TBD` chain by inserting `origin`), and it
  is injected into templates (via the existing `inject_i18n_helpers` context processor)
  so the dashboard/predict views use the exact same precedence. Logic stays in Python per
  CLAUDE.md; no duplicated fallback chains.
- **Bracket:** R32 cards now read e.g. **"2A vs 2B"** (muted, like other placeholders)
  instead of "TBD"; R16+ keep `Winner R32-1` feed labels unchanged.
- **Dashboard & predict:** the match list / heading read "2A vs 2B" before teams are set.
- **Predictability unchanged:** `is_predictable()` still requires real `home_team` AND
  `away_team`, so origin-only matches are **not** predictable (you can't pick a scoreline
  or an advancing team for `2A`). This is intentional and matches the current design.
- **Locking:** seeded kickoffs flow through `is_locked()`/`deadline_tz` exactly as a
  hand-entered kickoff would. Today (2026-05-31) all R32 kickoffs are in the future, so
  nothing is locked yet.

## i18n

No new user-facing English strings are required: slot codes (`2A`, `3rd …`) are
language-neutral, and `"TBD"`/`"vs"` already have translations. The `"3rd"` token inside
an origin string is data, not a translated UI label, and stays as-is in both languages.

## Testing (no pytest suite — `python -c` idiom)

- `python -m py_compile app.py translations.py`.
- **Timezone regeneration check:** recompute all 16 `kickoff_utc` from the venue IANA
  zones + local times and assert each equals the value in `R32_SCHEDULE` (guards against
  drift / typos).
- **Migration backfill:** load the existing all-null `data.json`; assert all 16 R32
  matches now have non-null `home_origin`, `away_origin`, `kickoff_utc`, and that R16+
  origins are `None`; assert `r32-1` origins are `2A`/`2B` and kickoff is the expected
  UTC string.
- **No-clobber:** set a real `home_team` + a custom `kickoff_utc` on one R32 match, run
  `migrate_data` again, assert those values are preserved (only the empty fields fill).
- **Idempotency:** run `migrate_data` twice; second run reports no change.
- **Render:** `GET /bracket` (and `/dashboard` while logged in) shows `2A`…`2G` origins
  and the formatted kickoff dates; matches with only origins are not linkable to a
  prediction (not predictable).
- Reset `data.json` to a clean state after manual checks (it is gitignored).

## Out of scope (YAGNI)

Host city/venue field, FIFA match number field, origin labels for R16+, opening
predictions on origin-only matches, and any admin "import schedule" UI. These can be
separate efforts if wanted later.
