# Cities + Full Knockout Schedule + Central Display — Design

**Date:** 2026-05-31
**Scope:** Extend the R32 schedule work to (a) add a `venue` (host city) field to every match, (b) seed kickoffs + venues for the whole knockout (R16 → Final) from `round_of_16_and_on_schedule.md`, and (c) switch the app's display timezone to US Central. Touches `app.py`, `render.yaml`, `README.md`, `templates/dashboard.html`, `templates/predict.html`. No scoring/locking-logic change.

**Sources (already committed reference data):** `round_of_32_schedule.md`, `schedule_bracket.md`, and the newly added `round_of_16_and_on_schedule.md` (M89–M104: date, local time, city). R16+ "Teams" are `Winner M…`, already rendered by the app's feed labels — so R16+ need kickoff + venue only, no origins.

## 1. New field: `venue`

Add `venue` (host-city string, stored verbatim as the source lists it, e.g. `"Philadelphia, USA"`, `"Arlington (Dallas), USA"`, `"East Rutherford (MetLife Stadium), USA"`) to every match; `None` when unknown.

## 2. Unify `R32_SCHEDULE` → `MATCH_SCHEDULE`

Rename the existing R32-only constant to `MATCH_SCHEDULE`, keyed by all 31 match ids. Each entry has `venue` + `kickoff_utc`; R32 entries additionally keep `home_origin`/`away_origin` (R16+ omit them). Full table (UTC values `zoneinfo`-verified from each venue's IANA zone; R32 kickoffs unchanged from the shipped feature):

```python
MATCH_SCHEDULE = {
    # Round of 32 (origins + kickoff + venue)
    "r32-1":  {"home_origin": "2A", "away_origin": "2B",            "kickoff_utc": "2026-06-28T19:00:00+00:00", "venue": "Los Angeles, USA"},
    "r32-2":  {"home_origin": "1E", "away_origin": "3rd A/B/C/D/F", "kickoff_utc": "2026-06-29T20:30:00+00:00", "venue": "Boston, USA"},
    "r32-3":  {"home_origin": "1F", "away_origin": "2C",            "kickoff_utc": "2026-06-30T01:00:00+00:00", "venue": "Monterrey, Mexico"},
    "r32-4":  {"home_origin": "1C", "away_origin": "2F",            "kickoff_utc": "2026-06-29T17:00:00+00:00", "venue": "Houston, USA"},
    "r32-5":  {"home_origin": "1I", "away_origin": "3rd C/D/F/G/H", "kickoff_utc": "2026-06-29T21:00:00+00:00", "venue": "New York/New Jersey, USA"},
    "r32-6":  {"home_origin": "2E", "away_origin": "2I",            "kickoff_utc": "2026-06-30T17:00:00+00:00", "venue": "Dallas, USA"},
    "r32-7":  {"home_origin": "1A", "away_origin": "3rd C/E/F/H/I", "kickoff_utc": "2026-07-01T01:00:00+00:00", "venue": "Mexico City, Mexico"},
    "r32-8":  {"home_origin": "1L", "away_origin": "3rd E/H/I/J/K", "kickoff_utc": "2026-06-30T16:00:00+00:00", "venue": "Atlanta, USA"},
    "r32-9":  {"home_origin": "1D", "away_origin": "3rd B/E/F/I/J", "kickoff_utc": "2026-07-01T00:00:00+00:00", "venue": "San Francisco Bay Area, USA"},
    "r32-10": {"home_origin": "1G", "away_origin": "3rd A/E/H/I/J", "kickoff_utc": "2026-07-01T20:00:00+00:00", "venue": "Seattle, USA"},
    "r32-11": {"home_origin": "2K", "away_origin": "2L",            "kickoff_utc": "2026-07-02T23:00:00+00:00", "venue": "Toronto, Canada"},
    "r32-12": {"home_origin": "1H", "away_origin": "2J",            "kickoff_utc": "2026-07-02T19:00:00+00:00", "venue": "Los Angeles, USA"},
    "r32-13": {"home_origin": "1B", "away_origin": "3rd E/F/G/I/J", "kickoff_utc": "2026-07-03T03:00:00+00:00", "venue": "Vancouver, Canada"},
    "r32-14": {"home_origin": "1J", "away_origin": "2H",            "kickoff_utc": "2026-07-03T22:00:00+00:00", "venue": "Miami, USA"},
    "r32-15": {"home_origin": "1K", "away_origin": "3rd D/E/I/J/L", "kickoff_utc": "2026-07-04T01:30:00+00:00", "venue": "Kansas City, USA"},
    "r32-16": {"home_origin": "2D", "away_origin": "2G",            "kickoff_utc": "2026-07-03T18:00:00+00:00", "venue": "Dallas, USA"},
    # Round of 16 → Final (kickoff + venue; origins omitted — feed labels render "Winner M…")
    "r16-1":  {"kickoff_utc": "2026-07-05T16:00:00+00:00", "venue": "Philadelphia, USA"},
    "r16-2":  {"kickoff_utc": "2026-07-05T22:00:00+00:00", "venue": "Houston, USA"},
    "r16-3":  {"kickoff_utc": "2026-07-06T21:00:00+00:00", "venue": "Mexico City, Mexico"},
    "r16-4":  {"kickoff_utc": "2026-07-06T19:00:00+00:00", "venue": "Arlington (Dallas), USA"},
    "r16-5":  {"kickoff_utc": "2026-07-07T16:00:00+00:00", "venue": "Atlanta, USA"},
    "r16-6":  {"kickoff_utc": "2026-07-08T02:30:00+00:00", "venue": "Seattle, USA"},
    "r16-7":  {"kickoff_utc": "2026-07-08T19:00:00+00:00", "venue": "Miami, USA"},
    "r16-8":  {"kickoff_utc": "2026-07-09T00:00:00+00:00", "venue": "Guadalajara, Mexico"},
    "qf-1":   {"kickoff_utc": "2026-07-09T21:00:00+00:00", "venue": "Boston, USA"},
    "qf-2":   {"kickoff_utc": "2026-07-11T01:00:00+00:00", "venue": "Los Angeles, USA"},
    "qf-3":   {"kickoff_utc": "2026-07-11T21:00:00+00:00", "venue": "Kansas City, USA"},
    "qf-4":   {"kickoff_utc": "2026-07-11T20:00:00+00:00", "venue": "Miami, USA"},
    "sf-1":   {"kickoff_utc": "2026-07-15T01:00:00+00:00", "venue": "Arlington (Dallas), USA"},
    "sf-2":   {"kickoff_utc": "2026-07-16T00:00:00+00:00", "venue": "Atlanta, USA"},
    "third-1":{"kickoff_utc": "2026-07-18T19:00:00+00:00", "venue": "Miami, USA"},
    "final-1":{"kickoff_utc": "2026-07-19T19:00:00+00:00", "venue": "East Rutherford (MetLife Stadium), USA"},
}
```

**Timezone rule (unchanged from R32):** the listed clock is the venue's local wall-clock; convert via the city's IANA zone, ignoring mismatched printed tags (Houston M90 tagged "ET" but is `America/Chicago`; Mexico City M91 / Guadalajara M96 tagged "CT" but are `America/Mexico_City`, UTC-6). DST handled by `zoneinfo`.

## 3. Seed + self-healing migration

- `_seed_matches()` — for every match, pull `venue`/`kickoff_utc`/`home_origin`/`away_origin` from `MATCH_SCHEDULE.get(id, {})` via `.get(...)` (absent keys → `None`).
- `migrate_data()`:
  - Add `"venue"` to the generic match-field-backfill tuple (default `None`).
  - **Broaden** the existing R32 backfill block to iterate **all** `MATCH_SCHEDULE` entries and fill **each key present in the entry** (`venue`, `kickoff_utc`, and origins where present) only when the match's current value `is None`:
    ```python
    for m in data["matches"]:
        sched = MATCH_SCHEDULE.get(m["id"])
        if not sched:
            continue
        for field, value in sched.items():
            if m.get(field) is None:
                m[field] = value
                changed = True
    ```
  - Idempotent + no-clobber (per-field `is None`): admin-entered teams/scores/kickoffs are never overwritten. On next load, the live `data.json` gains R16+ kickoffs and all 31 venues.

## 4. Display timezone → US Central

So all deadlines render in Central:
- `app.py` defaults: `DISPLAY_TZ` `America/Lima` → `America/Chicago`; `DISPLAY_TZ_LABEL` `LIM` → `CT`.
- `render.yaml`: update the `DISPLAY_TZ` (→ `America/Chicago`) and `DISPLAY_TZ_LABEL` (→ `CT`) env values (production overrides the code default, so both must change).
- `README.md`: update the env-table default cells for `DISPLAY_TZ`/`DISPLAY_TZ_LABEL`.

**Ripples (intended):** `deadline_tz` now renders Central + `CT` label; `parse_admin_kickoff()` now interprets admin `datetime-local` input as Central (the admin works in Central). Stored UTC of existing data is unchanged — only display + future admin-input interpretation move. The label is static `"CT"` (not CDT/CST) to avoid DST-label logic; `zoneinfo` still applies the correct offset for the actual instant.

## 5. Display venue (dashboard + predict only)

- **`templates/dashboard.html`:** append `{% if m.venue %} · {{ m.venue }}{% endif %}` to the existing deadline line (`{{ m.kickoff_utc | deadline_tz }}`).
- **`templates/predict.html`:** append `{% if match.venue %} · {{ match.venue }}{% endif %}` to the round-label line.
- **Bracket:** unchanged — `_bracket_view` already spreads `venue` into its dict (unused there); the tree stays clean.
- No new i18n strings (city names are data; `vs`, round labels, `TBD` already translated).

## 6. Predictability / locking (unchanged)

`is_predictable()` still requires real `home_team` AND `away_team`, so all team-less matches (now carrying venue + kickoff) remain non-predictable. Seeded R16+ kickoffs flow through `is_locked`/`deadline_tz` like any kickoff; all are future-dated (July 2026), so nothing is locked yet.

## 7. Testing (no pytest — `python -c` idiom; `python3` binary)

- `python -m py_compile app.py translations.py`.
- **Timezone regen:** recompute all 31 `MATCH_SCHEDULE` kickoffs from venue IANA zones + local times; assert equality (guards drift across R32 + R16+).
- **Migration:** load the existing `data.json`; assert every match has a non-null `venue`; all R16+ matches have non-null `kickoff_utc`; R16+ `home_origin`/`away_origin` are `None`; idempotent (second migrate → no write); no-clobber (a set `home_team`/custom `kickoff` survives; only `None` fields fill). Monkeypatch `app._write` in tests to avoid touching the real file where appropriate.
- **Display:** logged-in `/dashboard` and `/predict/<an r32 id>` show the city; `deadline_tz` of an R16 kickoff renders a Central time + `CT` label (e.g. `r16-1` → `Jul 5 2026, 11:00 AM CT`).
- **Predictability:** an origin-only match is not `is_predictable`.
- Reset/clean test data afterward (`data.json` gitignored).

## Out of scope (unchanged)

FIFA match-number field, venue on the bracket tree, R16+ origin labels, opening predictions on team-less matches, per-DST display label.
