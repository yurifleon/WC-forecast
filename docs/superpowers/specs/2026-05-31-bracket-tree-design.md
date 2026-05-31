# Bracket Tree — Design

**Date:** 2026-05-31
**Scope:** `/bracket` view only — `app.py` (`bracket()` route + one helper), `templates/bracket.html`, `base.html` (CSS), `translations.py`. No data-model, scoring, or time-logic change.

## Goal

Render the existing six knockout rounds as a connected **winner-flow tree**. Each
later-round match sits vertically centered against the pair that feeds it, pure-CSS
elbow connectors draw the joins, and empty downstream slots show
`Winner R32-1`-style feed labels instead of a bare `TBD`.

## Pairing convention (derived, not stored)

No schema change. Feeders are computed from arithmetic on the numeric id suffix `k`
(ids are strings like `r32-1`; `k = int(id.rsplit("-",1)[-1])`):

| Match     | Top feeder    | Bottom feeder | Word   |
|-----------|---------------|---------------|--------|
| `r16-k`   | `r32-(2k-1)`  | `r32-2k`      | Winner |
| `qf-k`    | `r16-(2k-1)`  | `r16-2k`      | Winner |
| `sf-k`    | `qf-(2k-1)`   | `qf-2k`       | Winner |
| `final-1` | `sf-1`        | `sf-2`        | Winner |
| `third-1` | `sf-1`        | `sf-2`        | Loser  |

`r32` has no feeders — its empty slots stay `TBD`. This is the standard bracket
numbering (match `i` & `i+1` feed match `ceil(i/2)` of the next round). The admin
still types real team names as each round is set; feed labels are placeholders shown
only until a slot's team is filled.

## Python (`app.py`)

- **New helper** `feed_labels(match)` → `(top_label, bottom_label)` or `None` for
  `r32`. Uses `SHORT = {"r32":"R32","r16":"R16","qf":"QF","sf":"SF"}`; produces
  strings like `"Winner R32-1"` / `"Loser SF-2"`. The word (`Winner`/`Loser`) is run
  through `translate()`; the short code is not (R32/QF/SF read the same in both langs
  and stay compact in a ~230px column).
- **`bracket()` route** builds a `columns` structure. Each match dict carries:
  - `home_display` / `away_display` — the real team name if set, else the
    corresponding feed label (or `TBD` for `r32`).
  - `home_is_placeholder` / `away_is_placeholder` — bool, for muted styling.
  - existing fields (`home_score`, `away_score`, `advanced_team`, etc.).
  Business logic stays in Python (per CLAUDE.md), template just iterates.
- **Bug fix:** the route currently sorts with `lambda x: x["id"]` (lexicographic, so
  `r32-10` precedes `r32-2`). Switch to the existing numeric `_match_sort_key` /
  `sorted_matches` so slots read 1…16 and align with the next round.
- **Column order:** the tree uses `["r32","r16","qf","sf","final"]`. `third` is
  excluded from the tree and passed separately as a single `third_match` for the
  standalone card.

## Template + CSS (`templates/bracket.html`, `base.html`)

- **Layout:** `.bracket` is a flex row; each `.round` is a flex column and every
  `.bracket-match` is `flex:1 1 0; justify-content:center`, so equal-height match
  cells center their connector stubs deterministically — each later match lines up
  against its feeding pair. (This equal-flex approach replaced the originally
  sketched `justify-content:space-around`; it aligns more robustly. All columns
  share a height via the flex default `align-items:stretch`, which is load-bearing.)
  Horizontal scroll (`overflow-x:auto`) is preserved.
- **Connectors:** pure-CSS elbow connectors via `::before`/`::after` border
  pseudo-elements on the match cards, drawn for the receiving rounds
  `r16, qf, sf, final`. No JavaScript. CSS lives in the `base.html` `<style>` block,
  matching the existing convention (CSS vars `--wc-*`, `.accent`).
- **Per-slot rendering:** each card shows `home_display` then `away_display`; a slot
  whose `*_is_placeholder` is true renders muted (e.g. `text-muted`/italic). Real
  team names and the champion 🏆 line on the final are unchanged.
- **Third-place:** rendered as a standalone card **below** the bracket tree, labelled
  Third-place Play-off, showing `Loser SF-1` / `Loser SF-2` feed labels (or real teams
  once set). No connectors.

## The tail (resolved)

Connectors run the full winner tree **R32 → R16 → QF → SF → Final**. Third-place is a
standalone card below the bracket (not a column), so the Final keeps its real SF→Final
joins and nothing is ambiguous. (This supersedes an earlier option of placing
third-place as its own column before the final.)

## i18n (`translations.py`)

Add:
- `"Winner"` → `"Ganador"`
- `"Loser"` → `"Perdedor"`

(`"Third-place Play-off"`, `"TBD"`, `"Champion"` already exist.)

## Testing

- `python -m py_compile app.py translations.py` passes.
- No scoring/time/data-model change, so those checklists are N/A; run the quick
  scoring check anyway for safety.
- Manual: open `/bracket` with a partly-filled bracket (some R32 results entered,
  R16+ still TBD) and confirm in **both EN and ES**:
  - matches within each round are ordered 1…16 (not lexicographic),
  - each match is vertically centered against its feeding pair,
  - elbow connectors join each pair to the match it feeds, through to the Final,
  - empty downstream slots show `Winner <Rnd>-<n>` (muted); `r32` empties show `TBD`,
  - the standalone third-place card shows `Loser SF-1 / Loser SF-2`,
  - champion 🏆 line still appears when the final has an `advanced_team`.

## Out of scope

- Auto-propagating advancing teams into next-round slots (feed labels only; admin
  still confirms teams).
- Any change to seeding, scoring tiers, predictions, or the dashboard/admin views.
