# Real R32 matchups + correct bracket topology — design

**Date:** 2026-06-28
**Source of truth:** `knockout-round.md` (newest; user-designated authoritative).

## Problem

The group stage is over, so the Round of 32 matchups are now known
(`knockout-round.md`, M73–M88). Two things must change:

1. The app must show the real R32 teams everywhere, and the simulator must build
   on them (users pick winners, not teams).
2. `knockout-round.md` pairs the Round of 16 **non-sequentially** (M89 = W73 vs
   W75). The app's `feeders()` and the older `round_of_16_and_on_schedule.md` pair
   them **sequentially** (M89 = W73 vs W74). The user confirmed `knockout-round.md`
   is correct, so the app's R16 topology is wrong and must be fixed.

## Decisions (confirmed with user)

- R16 topology: use `knockout-round.md` (non-sequential).
- Simulator: lock R32 to the real teams; users only pick winners.
- Scope: whole app — real teams in the match data, not simulator-only.

## 1. R16 feed map (`feeders()`)

Add an explicit map and use it for `r16`; QF→Final stay sequential (verified
against the schedule docs — QF M97 ← W89/W90 = r16-1/r16-2, etc.):

```python
_R16_FEED = {
    "r16-1": ("r32-1", "r32-3"),   # M89: W73 vs W75
    "r16-2": ("r32-2", "r32-5"),   # M90: W74 vs W77
    "r16-3": ("r32-4", "r32-6"),   # M91: W76 vs W78
    "r16-4": ("r32-7", "r32-8"),   # M92: W79 vs W80
    "r16-5": ("r32-11", "r32-12"), # M93: W83 vs W84
    "r16-6": ("r32-9", "r32-10"),  # M94: W81 vs W82
    "r16-7": ("r32-14", "r32-16"), # M95: W86 vs W88
    "r16-8": ("r32-13", "r32-15"), # M96: W85 vs W87
}
```

`feeders()`: when `rnd == "r16"`, return `("Winner", *_R16_FEED[match["id"]])`.
Single source of truth — propagates to `feed_label_pair()` (bracket placeholders),
`_sim_participants()`, `_prune_sim()`, and `/bracket`.

## 2. Tree display order for R32

The bracket connectors are pure-flex with alternating `.feeder-top`/`.feeder-bottom`
classes (no hardcoded ids), so the visual tree lines up iff each R16's two feeders
sit adjacent in the R32 column. Derive:

```python
_BRACKET_R32_ORDER = [fid for k in range(1, 9) for fid in _R16_FEED[f"r16-{k}"]]
# -> r32-1, r32-3, r32-2, r32-5, r32-4, r32-6, r32-7, r32-8,
#    r32-11, r32-12, r32-9, r32-10, r32-14, r32-16, r32-13, r32-15
```

Helper `_tree_order(rnd, matches)`: for `r32`, sort by index in
`_BRACKET_R32_ORDER`; else `sorted_matches`. Use in `/bracket`, `/simulator`,
`/s/<token>`. Dashboard/admin/predict keep numeric `sorted_matches`.

## 3. Real R32 teams in `MATCH_SCHEDULE`

Add `home_team`/`away_team` to each r32 entry (M73→r32-1 … M88→r32-16), normalizing
`"Ivory Coast"` → `"Côte d'Ivoire"` (the GROUPS canonical name; all other 31 names
already match). `_seed_matches()` reads them; the fill-if-empty migrate backfill
sets them on load without clobbering admin edits. Kickoffs already match the file,
so only teams are added.

R32→team mapping (from `knockout-round.md`):

| id | M | home | away |
|----|---|------|------|
| r32-1 | 73 | South Africa | Canada |
| r32-2 | 74 | Germany | Paraguay |
| r32-3 | 75 | Netherlands | Morocco |
| r32-4 | 76 | Brazil | Japan |
| r32-5 | 77 | France | Sweden |
| r32-6 | 78 | Côte d'Ivoire | Norway |
| r32-7 | 79 | Mexico | Ecuador |
| r32-8 | 80 | England | DR Congo |
| r32-9 | 81 | United States | Bosnia and Herzegovina |
| r32-10 | 82 | Belgium | Senegal |
| r32-11 | 83 | Portugal | Croatia |
| r32-12 | 84 | Spain | Austria |
| r32-13 | 85 | Switzerland | Algeria |
| r32-14 | 86 | Argentina | Cape Verde |
| r32-15 | 87 | Colombia | Ghana |
| r32-16 | 88 | Australia | Egypt |

## 4. Simulator locks R32 to real teams

- `_sim_participants()` R32 branch: return `(match["home_team"], match["away_team"])`
  (from the real match dict via `by_id`) instead of a stored slot.
- Remove the `set_teams` action and the R32 `<select>` pickers in `simulator.html`;
  users only pick winners and cascade forward.
- Sim model simplifies to `{"winners": {match_id: team}}`. Retire `_sim_pool` and
  `_sim_used_teams`; drop the R32-slot pruning. `_prune_sim(sim, by_id)` now takes
  the real match map so it resolves R32 participants from real teams and cascades
  winner invalidation (r32→final, then third). Update all call sites and
  `shared_view`.
- Legacy sims with an old `r32` key self-heal — the key is ignored. `reset` →
  `{"winners": {}}`. The "nothing to share" guard checks `sim.get("winners")`.
- `_sim_view()` drops `home_pool`/`away_pool` (picker gone); R32 slots display the
  real team via the existing team→origin→TBD precedence.

## 5. Docs

Update CLAUDE.md simulator + bracket sections: non-sequential `_R16_FEED`, R32-locked
simulator, removed `_sim_pool`/`set_teams`, R32 tree display order.

## Verification

1. `python -m py_compile app.py translations.py`.
2. `feeders({"id":"r16-1","round":"r16"})` → `("Winner","r32-1","r32-3")`.
3. `/bracket`: R16 empty slots read "Winner R32-1 / Winner R32-3"; R32 column in
   tree order; real R32 team names shown.
4. `/simulator`: R32 shows real teams (no team picker); pick winner of r32-1 and
   r32-3 → r16-1 participants are exactly those two winners.
5. Legacy sim (old `r32` slots + a now-invalid winner) self-heals on view.
6. A shared snapshot still renders read-only.
