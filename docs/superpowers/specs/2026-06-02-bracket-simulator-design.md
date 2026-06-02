# Bracket Simulator — Design

**Date:** 2026-06-02
**Status:** Approved

## Goal

A private, per-user "what-if" bracket where a player picks the participants and
winners at each knockout round (no scores) purely to **visualize possible
match-ups**. Completely separate from the real prediction game: never scored, never
touches `predictions`, no deadline/lock logic.

## Placement & access

- New route `/simulator` (login required).
- Reachable from the nav alongside "Bracket".
- Reuses the existing bracket tree layout and CSS (`.bracket`, `.round`,
  `.bracket-match`, `feeder-top`/`feeder-bottom` from `base.html`) so it reads like
  `/bracket`, but with interactive forms.

## Data model

New top-level key in `data.json`, seeded by `migrate_data()`
(`data.setdefault("simulations", {})`):

```jsonc
"simulations": {
  "yuri": {
    "r32":     { "r32-1": {"home": "Mexico", "away": "Canada"}, ... },  // user-assigned R32 participants
    "winners": { "r32-1": "Mexico", "r16-1": "Mexico", ... }            // chosen winner per match id
  }
}
```

- **R32 participants** are user-picked from each slot's group pool — reusing
  `_origin_groups()` + `GROUPS` (e.g. slot `2A` → any Group A nation;
  `3rd A/B/C/D/F` → the union of those groups). Stored per slot under `r32`.
- **R16 → Final participants** are *derived, not stored*: each slot is the winner of
  its feeder match, resolved through the existing `feeders()` mapping. Third-place is
  the two SF **losers**.
- **Winners** are stored per match id. A winner must be one of that match's two
  current participants (enforced on write and by the prune pass).

## Interaction (no-JS, click-to-advance)

Single page rendering the full tree. Every action is a form POST that reloads the
page (consistent with the project's no-custom-JS rule).

- **R32 matches:** two `<select>` dropdowns (the slot's group pool) + a small "Set"
  submit (`action=set_teams`). Once both teams are set, each team renders as a
  click-to-pick **winner button** (`action=pick_winner`).
- **R16+ matches:** show derived participants, or `Winner R32-1`-style placeholders
  (via `feed_label_pair()`) until the upstream match has a winner. Clicking a real
  participant sets it the winner; it flows forward on reload.
- The chosen winner is highlighted with the same bold-accent styling the real
  bracket uses for `advanced_team`. The Final shows 🏆 Champion.
- A **Reset simulator** button (`action=reset`) clears the user's whole sim.

## Cascade integrity (auto-prune)

When an upstream pick changes — an R32 slot reassigned, or a winner switched — any
downstream winner that is no longer one of its match's valid participants is
**auto-pruned**. A `_prune_sim(sim)` helper runs after every mutation: it walks
rounds in order (`r32 → r16 → qf → sf → final`, then `third`), recomputes each
match's participants, and drops any stored winner not among them. This keeps the
tree internally consistent with no orphaned picks. Pruning cascades naturally
because later rounds depend on earlier-round winners that may themselves have just
been pruned.

## Server pieces (`app.py`)

- `_sim_participants(sim, match, by_id)` — resolve the `(home, away)` teams for any
  match: R32 from stored `sim["r32"]` slots; R16+ from the feeder matches' winners
  (third-place from SF losers). Returns `None` for a slot whose upstream is undecided.
- `_prune_sim(sim)` — integrity pass described above; mutates `sim` in place.
- `_sim_view(sim, match, by_id)` — display fields for the template (participant
  labels, placeholders, current winner) analogous to `_bracket_view`.
- `GET/POST /simulator` — GET renders the tree; POST handles `action` in
  {`set_teams`, `pick_winner`, `reset`}, runs `_prune_sim`, `save_data`, redirects
  (PRG). Validation uses `flash(..., "danger"|"warning")` for bad input.
- Template `simulator.html` — variant of `bracket.html` with the forms/selects.
- i18n: new UI strings go through `translate()`; Spanish added to `translations.py`.

## Out of scope (YAGNI)

- No scoring, no leaderboard impact, no deadlines/locking.
- No multiple saved scenarios per user (one sim per user).
- No sharing/visibility of other users' sims.
- No mirroring of the real bracket's admin-set teams (sim is fully hypothetical).

## Edge cases

- R32 slot pool can be the union of several groups (`3rd …` origins) — pool dedups
  and sorts.
- A team could be picked into two different R32 slots; we do **not** prevent this
  (it's a hypothetical sandbox) — but document it so it isn't treated as a bug.
- Changing an R32 team that had advanced several rounds prunes its whole downstream
  path on the next render.
- A user with no sim yet gets an empty bracket (all R32 slots unset) on first visit.
