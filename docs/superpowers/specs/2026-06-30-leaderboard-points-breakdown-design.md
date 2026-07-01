# Leaderboard points breakdown — design

**Date:** 2026-06-30
**Status:** Approved (pending spec review)

## Goal

Emulate the UCL-forecast points-breakdown table on the WC-forecast
`/leaderboard` page: show, for each user, how many points they have
accumulated **per round** (summary) and **per match** (detail). No new
routes, no data-model changes, no custom JS.

## Non-goals

- No changes to scoring logic (`compute_points`, `TIERS`).
- No new persisted fields; everything is derived at render time.
- No per-user drill-down / collapse interaction (the matrix shows everyone).

## Changes

### 1. Data layer — `build_leaderboard(data)` (app.py)

Each row already carries `breakdown` (a list of
`{"match": match, "points": {"score","advance","total"}}`). Add one derived
aggregate per row:

```python
row["round_points"] = { round_key: total_points_in_that_round }
```

- Computed by iterating the row's existing `breakdown` and summing
  `points["total"]` grouped by `match["round"]`.
- Seed every one of the six valid rounds to `0` first
  (`r32, r16, qf, sf, third, final`) so absent/incomplete rounds render `0`,
  not a missing key.
- Rows remain sorted by grand `total` (unchanged).
- In the same loop, also set `row["score_points"]` and
  `row["advance_points"]` (sums of `points["score"]` / `points["advance"]`
  across `breakdown`), replacing the `| sum(attribute=...)` the template
  currently does, and `row["points_by_id"] = {match_id: points}` for the
  matrix (§3b).

Logic stays in Python (per CLAUDE.md: no business logic in templates).

### 2. Route — `leaderboard()` (app.py)

Pass two extra template values alongside `rows` and `matches`:

- `rounds` — the ordered list of `(round_key, short_label)` pairs:
  `[("r32","R32"), ("r16","R16"), ("qf","QF"), ("sf","SF"), ("third","3rd"),
  ("final","F")]`. Ordering follows `ROUND_ORDER`. Short labels are defined
  here (not by extending `ROUND_CODE_SHORT`, which is load-bearing for feed
  labels and only covers r32–sf).

`matches` continues to come from `sorted_matches(data["matches"])`.

### 3. Template — `templates/leaderboard.html` (rewrite)

Three stacked sections inside the page:

**(a) Per-round summary table (main, ranked leaderboard)**

| Rank | Player | R32 | R16 | QF | SF | 3rd | F | Score | Adv | Total |
|------|--------|-----|-----|----|----|-----|---|-------|-----|-------|

- One row per `rows` entry, in existing rank order (`loop.index` = rank).
- Round cells: `row.round_points[round_key]`; render `0` in a muted style,
  positive values plain.
- `Score` / `Adv` cells: the existing score-vs-advance split, summed from
  `breakdown` (`points.score` / `points.advance`). **Kept** (per user
  request) — these carry over from the current table and sit just before
  `Total`. Computed the same way the current template does it, but moved into
  the data layer for consistency (see §1).
- `Total` cell: `row.total`, emphasized (accent, bold) as today.
- Empty state: `No players yet.` spanning all columns.
- This augments the current Rank/Player/Score/Advance/Total table with the
  six per-round columns; the score/advance split is retained.

**(b) Full per-match matrix (detail)**

| Player | M73 | M74 | … | M104 | Total |
|--------|-----|-----|---|------|-------|

- Header: one column per match in `matches`, labelled with its FIFA match
  number via `match_number(m)`; the matchup (`slot_label(m,'home')` vs
  `slot_label(m,'away')`, or `home_team`/`away_team`) goes in the `th`'s
  `title` tooltip.
- Rows: same users in the same ranked order; each cell = that match's
  `points.total` from `row.breakdown` (aligned index-for-index with
  `matches`, since both derive from the same match list). `> 0` → green
  Bootstrap badge; `0` → muted text (matches UCL style).
- Wrapped in `<div class="table-responsive">` for horizontal scroll (wide).
- Trailing `Total` column = `row.total`.

> Alignment note: `build_leaderboard` builds `breakdown` by iterating
> `data["matches"]`, while the matrix header iterates
> `sorted_matches(data["matches"])`. To keep cells under the right header,
> the template must index breakdown **by match id**, not by position. Provide
> a per-row lookup `row["points_by_id"] = {match_id: points}` from the data
> layer (built in the same loop as `round_points`) and have the matrix read
> `row.points_by_id[m.id]`.

**(c) Scoring reference card** — unchanged from the current template.

## i18n

Reuse existing translated strings where present (`Leaderboard`, `Rank`,
`Player`, `Total`, `Scoring`, round labels, `No players yet.`). Any genuinely
new UI string (e.g. a matrix section heading like `Points by match`) goes
through `_()` and gets a Spanish entry in `translations.py`. Short round
headers (`R32/R16/QF/SF/3rd/F`) are codes, not translated.

## Testing / verification

- `python -m py_compile app.py translations.py`.
- Manual: load `/leaderboard` with existing `data.json` — confirm per-round
  columns sum to `Total`, and each user's matrix row also sums to `Total`.
- Spot check a user with mixed correct/incorrect predictions and at least one
  completed round so non-zero cells appear.
- Verify empty-state renders when there are no users.

## Risks

- **Matrix width** with 32 matches — mitigated by `table-responsive`.
- **Header/cell misalignment** — mitigated by keying cells on match id
  (`points_by_id`) rather than list position.
