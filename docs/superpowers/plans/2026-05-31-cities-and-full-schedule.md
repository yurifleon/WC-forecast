# Cities + Full Knockout Schedule + Central Display Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `venue` (host city) field to every match, seed kickoffs + venues for the whole knockout (R16→Final) from `round_of_16_and_on_schedule.md`, and switch the app's display timezone to US Central.

**Architecture:** Rename the R32-only `R32_SCHEDULE` constant to a unified `MATCH_SCHEDULE` (all 32 matches, each with `venue` + `kickoff_utc`; R32 also keeps origins). `_seed_matches`/`migrate_data` are updated to wire in `venue` and to backfill every key present in each schedule entry (idempotent, no-clobber). The display timezone default flips Lima→US Central in code, `render.yaml`, and README. Venue shows on the dashboard + predict pages (bracket stays clean).

**Tech Stack:** Flask, Jinja2, `zoneinfo` (stdlib). Single-file `app.py`. No pytest — verify with `python -m py_compile` + `python -c` assertions. Use `python3`.

**Spec:** `docs/superpowers/specs/2026-05-31-cities-and-full-schedule-design.md`

---

### Task 1: `MATCH_SCHEDULE` (all 32) + venue wired into seed & migration

This is one cohesive data-layer task (rename + expand + the two call-site updates must land together so no commit leaves a dangling `R32_SCHEDULE` reference).

**Files:** Modify `app.py`.

- [ ] **Step 1: Replace the `R32_SCHEDULE` constant with `MATCH_SCHEDULE`**

In `app.py`, replace the entire existing constant block — the banner comment plus `R32_SCHEDULE = { … }` (currently the comment above line 146 through the closing `}` at line 163) — with:

```python
# Real FIFA World Cup 2026 knockout schedule (sources: round_of_32_schedule.md,
# round_of_16_and_on_schedule.md, schedule_bracket.md). FIFA's match numbering is
# bracket-positional, so M73->r32-1 … M104->final-1 maps onto the app's positional
# pairing. kickoff_utc is converted from each host city's IANA zone (the listed clock
# is venue-local; mismatched tz tags like Houston "ET" / Mexico City "CT" are ignored)
# and re-derived + asserted in this task's test. R32 entries carry group-stage origin
# slots; R16+ rely on the bracket feed labels ("Winner R32-1") instead.
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
    # Round of 16 -> Final (kickoff + venue; origins omitted — feed labels render "Winner M…")
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

- [ ] **Step 2: Update `_seed_matches()` (rename + add venue)**

In `_seed_matches`, replace the match-building block:

```python
            mid = f"{rnd}-{i}"
            sched = R32_SCHEDULE.get(mid, {})
            matches.append({
                "id": mid,
                "round": rnd,
                "home_team": None,
                "away_team": None,
                "home_origin": sched.get("home_origin"),  # R32 slot code; None for R16+
                "away_origin": sched.get("away_origin"),
                "kickoff_utc": sched.get("kickoff_utc"),   # tz-aware UTC ISO, or None
                "home_score": None,
                "away_score": None,
                "advanced_team": None,                     # who went through (covers penalties)
            })
```

with (rename `R32_SCHEDULE`→`MATCH_SCHEDULE`, add the `venue` field):

```python
            mid = f"{rnd}-{i}"
            sched = MATCH_SCHEDULE.get(mid, {})
            matches.append({
                "id": mid,
                "round": rnd,
                "home_team": None,
                "away_team": None,
                "home_origin": sched.get("home_origin"),  # R32 slot code; None for R16+
                "away_origin": sched.get("away_origin"),
                "venue": sched.get("venue"),               # host city, or None
                "kickoff_utc": sched.get("kickoff_utc"),   # tz-aware UTC ISO, or None
                "home_score": None,
                "away_score": None,
                "advanced_team": None,                     # who went through (covers penalties)
            })
```

- [ ] **Step 3: Add `venue` to the migration field-backfill tuple**

In `migrate_data`, replace:

```python
        for field in ("home_team", "away_team", "home_origin", "away_origin",
                      "kickoff_utc", "home_score", "away_score", "advanced_team"):
```

with:

```python
        for field in ("home_team", "away_team", "home_origin", "away_origin",
                      "venue", "kickoff_utc", "home_score", "away_score", "advanced_team"):
```

- [ ] **Step 4: Broaden the schedule backfill block (rename + fill every entry key)**

In `migrate_data`, replace the existing backfill block:

```python
    # Backfill the real R32 schedule (origins + kickoff) where still empty.
    # Fill-if-empty + idempotent: never clobber admin-entered teams/scores or a
    # manually-set kickoff. Real home_team/away_team are never touched here.
    for m in data["matches"]:
        sched = R32_SCHEDULE.get(m["id"])
        if not sched:
            continue
        for field in ("home_origin", "away_origin", "kickoff_utc"):
            if m.get(field) is None:
                m[field] = sched[field]
                changed = True
```

with:

```python
    # Backfill the real knockout schedule (origins/kickoff/venue) where still empty.
    # Fill-if-empty + idempotent: never clobber admin-entered teams/scores or a
    # manually-set kickoff. Real home_team/away_team are never touched here.
    for m in data["matches"]:
        sched = MATCH_SCHEDULE.get(m["id"])
        if not sched:
            continue
        for field, value in sched.items():
            if m.get(field) is None:
                m[field] = value
                changed = True
```

- [ ] **Step 5: Run the regen + seed + migration test**

This re-derives all 32 kickoffs from venue zones, checks the seed wires venue in, and checks migration backfill/idempotency/no-clobber (monkeypatching `app._write` so the real `data.json` is untouched):

```bash
python3 -c "
import copy
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import app
from app import MATCH_SCHEDULE, _seed_matches

# (id, IANA zone, date, local 24h, venue) — all 32 matches
rows = [
 ('r32-1','America/Los_Angeles','2026-06-28','12:00','Los Angeles, USA'),
 ('r32-2','America/New_York','2026-06-29','16:30','Boston, USA'),
 ('r32-3','America/Monterrey','2026-06-29','19:00','Monterrey, Mexico'),
 ('r32-4','America/Chicago','2026-06-29','12:00','Houston, USA'),
 ('r32-5','America/New_York','2026-06-29','17:00','New York/New Jersey, USA'),
 ('r32-6','America/Chicago','2026-06-30','12:00','Dallas, USA'),
 ('r32-7','America/Mexico_City','2026-06-30','19:00','Mexico City, Mexico'),
 ('r32-8','America/New_York','2026-06-30','12:00','Atlanta, USA'),
 ('r32-9','America/Los_Angeles','2026-06-30','17:00','San Francisco Bay Area, USA'),
 ('r32-10','America/Los_Angeles','2026-07-01','13:00','Seattle, USA'),
 ('r32-11','America/Toronto','2026-07-02','19:00','Toronto, Canada'),
 ('r32-12','America/Los_Angeles','2026-07-02','12:00','Los Angeles, USA'),
 ('r32-13','America/Vancouver','2026-07-02','20:00','Vancouver, Canada'),
 ('r32-14','America/New_York','2026-07-03','18:00','Miami, USA'),
 ('r32-15','America/Chicago','2026-07-03','20:30','Kansas City, USA'),
 ('r32-16','America/Chicago','2026-07-03','13:00','Dallas, USA'),
 ('r16-1','America/New_York','2026-07-05','12:00','Philadelphia, USA'),
 ('r16-2','America/Chicago','2026-07-05','17:00','Houston, USA'),
 ('r16-3','America/Mexico_City','2026-07-06','15:00','Mexico City, Mexico'),
 ('r16-4','America/Chicago','2026-07-06','14:00','Arlington (Dallas), USA'),
 ('r16-5','America/New_York','2026-07-07','12:00','Atlanta, USA'),
 ('r16-6','America/Los_Angeles','2026-07-07','19:30','Seattle, USA'),
 ('r16-7','America/New_York','2026-07-08','15:00','Miami, USA'),
 ('r16-8','America/Mexico_City','2026-07-08','18:00','Guadalajara, Mexico'),
 ('qf-1','America/New_York','2026-07-09','17:00','Boston, USA'),
 ('qf-2','America/Los_Angeles','2026-07-10','18:00','Los Angeles, USA'),
 ('qf-3','America/Chicago','2026-07-11','16:00','Kansas City, USA'),
 ('qf-4','America/New_York','2026-07-11','16:00','Miami, USA'),
 ('sf-1','America/Chicago','2026-07-14','20:00','Arlington (Dallas), USA'),
 ('sf-2','America/New_York','2026-07-15','20:00','Atlanta, USA'),
 ('third-1','America/New_York','2026-07-18','15:00','Miami, USA'),
 ('final-1','America/New_York','2026-07-19','15:00','East Rutherford (MetLife Stadium), USA'),
]
assert len(MATCH_SCHEDULE) == 32 and len(rows) == 32
for rid, zone, d, t, venue in rows:
    exp = datetime.fromisoformat(f'{d}T{t}:00').replace(tzinfo=ZoneInfo(zone)).astimezone(timezone.utc).isoformat()
    s = MATCH_SCHEDULE[rid]
    assert s['kickoff_utc'] == exp, (rid, s['kickoff_utc'], 'expected', exp)
    assert s['venue'] == venue, (rid, s['venue'])

# seed wires venue + (r32) origins; r16+ have venue+kickoff but no origins
ms = {m['id']: m for m in _seed_matches()}
assert ms['r32-1']['venue'] == 'Los Angeles, USA' and ms['r32-1']['home_origin'] == '2A'
assert ms['final-1']['venue'] == 'East Rutherford (MetLife Stadium), USA'
assert ms['r16-1']['venue'] == 'Philadelphia, USA' and ms['r16-1']['home_origin'] is None
assert ms['r16-1']['kickoff_utc'] == '2026-07-05T16:00:00+00:00'

# migration backfill (no real data.json writes)
app._write = lambda data: None
oldstyle = {'users':{}, 'predictions':{}, 'matches':[
    {'id':'r16-3','round':'r16','home_team':None,'away_team':None,'kickoff_utc':None,'home_score':None,'away_score':None,'advanced_team':None},
    {'id':'r32-1','round':'r32','home_team':'Brazil','away_team':'Chile','home_origin':None,'away_origin':None,'kickoff_utc':'2026-06-28T12:00:00+00:00','home_score':2,'away_score':1,'advanced_team':'Brazil'},
]}
out = app.migrate_data(oldstyle)
b = {x['id']: x for x in out['matches']}
assert b['r16-3']['venue'] == 'Mexico City, Mexico' and b['r16-3']['kickoff_utc'] == '2026-07-06T21:00:00+00:00'
assert b['r16-3']['home_origin'] is None   # R16 gets no origin
assert b['r32-1']['home_team'] == 'Brazil' and b['r32-1']['kickoff_utc'] == '2026-06-28T12:00:00+00:00'  # no-clobber
assert b['r32-1']['venue'] == 'Los Angeles, USA' and b['r32-1']['home_origin'] == '2A'  # empty fields fill
# idempotency
calls = []; app._write = lambda data: calls.append(1)
app.migrate_data(copy.deepcopy(out)); assert calls == [], 'second migrate must be a no-op'
print('Task 1 OK')
"
```

Expected: `Task 1 OK`. Also `python3 -m py_compile app.py` (clean). Confirm `git status` shows `data.json` NOT modified (the monkeypatch protected it).

- [ ] **Step 6: Commit**

```bash
git add app.py
git commit -m "Unify schedule into MATCH_SCHEDULE (all 32) + venue; backfill R16+ kickoffs/venues

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: Switch display timezone to US Central

**Files:** Modify `app.py`, `render.yaml`, `README.md`.

- [ ] **Step 1: Change the `app.py` defaults**

In `app.py`, replace:

```python
DISPLAY_TZ = ZoneInfo(os.environ.get("DISPLAY_TZ", "America/Lima"))
DISPLAY_TZ_LABEL = os.environ.get("DISPLAY_TZ_LABEL", "LIM")
```

with:

```python
DISPLAY_TZ = ZoneInfo(os.environ.get("DISPLAY_TZ", "America/Chicago"))
DISPLAY_TZ_LABEL = os.environ.get("DISPLAY_TZ_LABEL", "CT")
```

- [ ] **Step 2: Update `render.yaml`**

In `render.yaml`, replace:

```yaml
      - key: DISPLAY_TZ
        value: America/Lima
      - key: DISPLAY_TZ_LABEL
        value: LIM
```

with:

```yaml
      - key: DISPLAY_TZ
        value: America/Chicago
      - key: DISPLAY_TZ_LABEL
        value: CT
```

- [ ] **Step 3: Update the `README.md` env table**

In `README.md`, replace these two table rows:

```
| `DISPLAY_TZ` | `America/Lima` | Timezone deadlines are shown in and admin input is interpreted as. |
| `DISPLAY_TZ_LABEL` | `LIM` | Label shown next to times. |
```

with:

```
| `DISPLAY_TZ` | `America/Chicago` | Timezone deadlines are shown in and admin input is interpreted as. |
| `DISPLAY_TZ_LABEL` | `CT` | Label shown next to times. |
```

- [ ] **Step 4: Verify the display timezone changed**

```bash
python3 -m py_compile app.py
python3 -c "
from app import app, deadline_tz_filter, DISPLAY_TZ_LABEL
assert DISPLAY_TZ_LABEL == 'CT', DISPLAY_TZ_LABEL
with app.test_request_context('/'):
    # r16-1 kickoff 2026-07-05T16:00Z -> America/Chicago (CDT, UTC-5) = 11:00 AM Jul 5
    out = deadline_tz_filter('2026-07-05T16:00:00+00:00')
    assert out == 'Jul 05 2026, 11:00 AM CT', out
    # r32-1 kickoff 2026-06-28T19:00Z -> 02:00 PM Jul 5... (Jun 28) Central
    out2 = deadline_tz_filter('2026-06-28T19:00:00+00:00')
    assert out2 == 'Jun 28 2026, 02:00 PM CT', out2
print('Task 2 OK')
"
echo '--- render.yaml + README sanity ---'
grep -q 'America/Chicago' render.yaml && grep -q 'America/Chicago' README.md && echo 'config files updated'
```

Expected: `Task 2 OK` then `config files updated`. (Note: `%I` produces a zero-padded hour, hence `Jul 05` / `11:00 AM` / `02:00 PM` — match the exact strings above.)

- [ ] **Step 5: Commit**

```bash
git add app.py render.yaml README.md
git commit -m "Switch display timezone default Lima -> US Central (CT)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: Show venue on dashboard + predict

**Files:** Modify `templates/dashboard.html`, `templates/predict.html`.

- [ ] **Step 1: Dashboard deadline line**

In `templates/dashboard.html`, replace:

```html
          <div class="small text-muted">{{ _("Deadline") }}: {{ m.kickoff_utc | deadline_tz }}</div>
```

with:

```html
          <div class="small text-muted">{{ _("Deadline") }}: {{ m.kickoff_utc | deadline_tz }}{% if m.venue %} · {{ m.venue }}{% endif %}</div>
```

- [ ] **Step 2: Predict heading**

In `templates/predict.html`, replace:

```html
      <span class="accent small">{{ round_label(match.round) }}</span>
```

with:

```html
      <span class="accent small">{{ round_label(match.round) }}{% if match.venue %} · {{ match.venue }}{% endif %}</span>
```

- [ ] **Step 3: Verify venue renders on dashboard**

Registers a throwaway user (writes the gitignored `data.json`), checks `/dashboard`, removes the user. The schedule backfill in `data.json` is the intended end state.

```bash
python3 -c "
from app import app, load_data, save_data
c = app.test_client()
c.post('/register', data={'username':'tmp_venue','password':'pw'})  # logs in
body = c.get('/dashboard').data.decode()
assert 'Philadelphia, USA' in body, 'R16 venue missing on dashboard'
assert 'Los Angeles, USA' in body, 'R32 venue missing on dashboard'
assert 'CT' in body, 'Central label missing'
d = load_data(); d['users'].pop('tmp_venue', None); d['predictions'].pop('tmp_venue', None); save_data(d)
print('Task 3 OK')
"
```

Expected: `Task 3 OK`. Confirm `git status` shows only the two template files (not `data.json`).

- [ ] **Step 4: Commit**

```bash
git add templates/dashboard.html templates/predict.html
git commit -m "Show host city on dashboard + predict pages

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 4: Final integration verification

**Files:** none (verification only).

- [ ] **Step 1: Compile**

```bash
python3 -m py_compile app.py translations.py && echo "compile OK"
```

Expected: `compile OK`.

- [ ] **Step 2: Live data.json backfilled with venues + R16+ kickoffs**

```bash
python3 -c "
from app import load_data
ms = load_data()['matches']
b = {m['id']: m for m in ms}
assert len(ms) == 32, len(ms)
assert all(m['venue'] for m in ms), 'every match must have a venue'
later = ['r16-1','r16-8','qf-1','sf-1','third-1','final-1']
assert all(b[i]['kickoff_utc'] for i in later), 'R16+ kickoffs must be backfilled'
assert b['r16-1']['home_origin'] is None and b['final-1']['venue'].startswith('East Rutherford')
print('data.json fully backfilled: 32 venues, R16+ kickoffs present')
"
```

Expected: `data.json fully backfilled: 32 venues, R16+ kickoffs present`.

- [ ] **Step 3: Bracket EN/ES still fine; predict heading shows venue; non-predictable holds**

```bash
python3 -c "
from app import app, load_data, is_predictable
c = app.test_client()
en = c.get('/bracket').data.decode()
assert '2A' in en and 'Winner R32-1' in en, 'bracket origins/feed labels regressed'
# bracket intentionally does NOT show venue
assert 'Philadelphia' not in en, 'venue should not appear on the bracket'
c.get('/set-language/es')
es = c.get('/bracket').data.decode()
assert 'Dieciseisavos' in es, 'ES labels regressed'
with app.test_request_context('/'):
    r16_1 = next(m for m in load_data()['matches'] if m['id']=='r16-1')
    assert is_predictable(r16_1) is False, 'team-less match must stay non-predictable'
print('bracket + predictability OK')
"
```

Expected: `bracket + predictability OK`.

- [ ] **Step 4: Confirm clean working tree**

```bash
git status --short
```

Expected: clean (all code committed in Tasks 1-3; `data.json` gitignored — must NOT appear).
