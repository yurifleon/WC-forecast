# R32 Schedule → Bracket Mapping Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Seed the 16 Round-of-32 matches with their real FIFA 2026 kickoff times (UTC) and team-origin slot labels (`2A`, `1E`, `3rd A/B/C/D/F`, …), and display those origins until real teams are known.

**Architecture:** Add `home_origin`/`away_origin` fields. A `R32_SCHEDULE` constant (sequential M73→r32-1 … M88→r32-16, which is bracket-faithful because FIFA's numbering is positional) drives both `_seed_matches()` (fresh deploys) and an idempotent fill-if-empty backfill in `migrate_data()` (existing data.json on the Render disk). A single `slot_label(match, side)` helper resolves a slot to `team → origin → feed-label → TBD`, used by `_bracket_view` and injected into templates. Origins are display-only; matches stay non-predictable until real teams are set.

**Tech Stack:** Flask, Jinja2, `zoneinfo` (stdlib) for UTC conversion. Single-file `app.py`. No pytest — verify with `python -m py_compile` and `python -c` assertions (the repo's idiom). Use `python3` (the binary on this machine).

**Spec:** `docs/superpowers/specs/2026-05-31-r32-schedule-mapping-design.md`

---

### Task 1: `R32_SCHEDULE` constant + origin fields in `_seed_matches()`

**Files:**
- Modify: `app.py` — add `R32_SCHEDULE` just before `_seed_matches` (currently ~line 127, after `DEFAULT_DATA`); extend `_seed_matches`.

- [ ] **Step 1: Add the `R32_SCHEDULE` constant**

In `app.py`, immediately after the `DEFAULT_DATA = {...}` block (ends ~line 124) and before `def _seed_matches`, add:

```python
# Real FIFA World Cup 2026 Round-of-32 schedule (source: round_of_32_schedule.md +
# schedule_bracket.md). FIFA's match numbering is bracket-positional, so M73→r32-1 …
# M88→r32-16 makes the bracket tree show true future matchups. kickoff_utc values are
# converted from each host city's IANA zone (DST-correct for late-June/early-July 2026;
# Mexico observes no DST) and are re-derived + asserted in this task's test.
R32_SCHEDULE = {
    "r32-1":  {"home_origin": "2A", "away_origin": "2B",            "kickoff_utc": "2026-06-28T19:00:00+00:00"},
    "r32-2":  {"home_origin": "1E", "away_origin": "3rd A/B/C/D/F", "kickoff_utc": "2026-06-29T20:30:00+00:00"},
    "r32-3":  {"home_origin": "1F", "away_origin": "2C",            "kickoff_utc": "2026-06-30T01:00:00+00:00"},
    "r32-4":  {"home_origin": "1C", "away_origin": "2F",            "kickoff_utc": "2026-06-29T17:00:00+00:00"},
    "r32-5":  {"home_origin": "1I", "away_origin": "3rd C/D/F/G/H", "kickoff_utc": "2026-06-29T21:00:00+00:00"},
    "r32-6":  {"home_origin": "2E", "away_origin": "2I",            "kickoff_utc": "2026-06-30T17:00:00+00:00"},
    "r32-7":  {"home_origin": "1A", "away_origin": "3rd C/E/F/H/I", "kickoff_utc": "2026-07-01T01:00:00+00:00"},
    "r32-8":  {"home_origin": "1L", "away_origin": "3rd E/H/I/J/K", "kickoff_utc": "2026-06-30T16:00:00+00:00"},
    "r32-9":  {"home_origin": "1D", "away_origin": "3rd B/E/F/I/J", "kickoff_utc": "2026-07-01T00:00:00+00:00"},
    "r32-10": {"home_origin": "1G", "away_origin": "3rd A/E/H/I/J", "kickoff_utc": "2026-07-01T20:00:00+00:00"},
    "r32-11": {"home_origin": "2K", "away_origin": "2L",            "kickoff_utc": "2026-07-02T23:00:00+00:00"},
    "r32-12": {"home_origin": "1H", "away_origin": "2J",            "kickoff_utc": "2026-07-02T19:00:00+00:00"},
    "r32-13": {"home_origin": "1B", "away_origin": "3rd E/F/G/I/J", "kickoff_utc": "2026-07-03T03:00:00+00:00"},
    "r32-14": {"home_origin": "1J", "away_origin": "2H",            "kickoff_utc": "2026-07-03T22:00:00+00:00"},
    "r32-15": {"home_origin": "1K", "away_origin": "3rd D/E/I/J/L", "kickoff_utc": "2026-07-04T01:30:00+00:00"},
    "r32-16": {"home_origin": "2D", "away_origin": "2G",            "kickoff_utc": "2026-07-03T18:00:00+00:00"},
}
```

- [ ] **Step 2: Extend `_seed_matches()` to wire in the schedule**

Replace the body of `_seed_matches` (currently builds the match dict at ~lines 134-148) with:

```python
    matches = []
    plan = [("r32", 16), ("r16", 8), ("qf", 4), ("sf", 2), ("third", 1), ("final", 1)]
    for rnd, count in plan:
        for i in range(1, count + 1):
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
    return matches
```

- [ ] **Step 3: Run the timezone-regeneration + seed test**

Run (this re-derives all 16 UTC values from venue zones and asserts they equal the table — guarding against drift — then checks the seed wires them in):

```bash
python3 -c "
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from app import R32_SCHEDULE, _seed_matches

# (id, IANA venue zone, local date, local 24h time, home_origin, away_origin)
rows = [
 ('r32-1','America/Los_Angeles','2026-06-28','12:00','2A','2B'),
 ('r32-2','America/New_York',   '2026-06-29','16:30','1E','3rd A/B/C/D/F'),
 ('r32-3','America/Monterrey',  '2026-06-29','19:00','1F','2C'),
 ('r32-4','America/Chicago',    '2026-06-29','12:00','1C','2F'),
 ('r32-5','America/New_York',   '2026-06-29','17:00','1I','3rd C/D/F/G/H'),
 ('r32-6','America/Chicago',    '2026-06-30','12:00','2E','2I'),
 ('r32-7','America/Mexico_City','2026-06-30','19:00','1A','3rd C/E/F/H/I'),
 ('r32-8','America/New_York',   '2026-06-30','12:00','1L','3rd E/H/I/J/K'),
 ('r32-9','America/Los_Angeles','2026-06-30','17:00','1D','3rd B/E/F/I/J'),
 ('r32-10','America/Los_Angeles','2026-07-01','13:00','1G','3rd A/E/H/I/J'),
 ('r32-11','America/Toronto',   '2026-07-02','19:00','2K','2L'),
 ('r32-12','America/Los_Angeles','2026-07-02','12:00','1H','2J'),
 ('r32-13','America/Vancouver', '2026-07-02','20:00','1B','3rd E/F/G/I/J'),
 ('r32-14','America/New_York',  '2026-07-03','18:00','1J','2H'),
 ('r32-15','America/Chicago',   '2026-07-03','20:30','1K','3rd D/E/I/J/L'),
 ('r32-16','America/Chicago',   '2026-07-03','13:00','2D','2G'),
]
assert len(R32_SCHEDULE) == 16 and len(rows) == 16
for rid, zone, d, t, ho, ao in rows:
    local = datetime.fromisoformat(f'{d}T{t}:00').replace(tzinfo=ZoneInfo(zone))
    exp = local.astimezone(timezone.utc).isoformat()
    s = R32_SCHEDULE[rid]
    assert s['kickoff_utc'] == exp, (rid, s['kickoff_utc'], 'expected', exp)
    assert s['home_origin'] == ho and s['away_origin'] == ao, rid

ms = {m['id']: m for m in _seed_matches()}
assert ms['r32-1']['home_origin'] == '2A' and ms['r32-1']['away_origin'] == '2B'
assert ms['r32-1']['kickoff_utc'] == '2026-06-28T19:00:00+00:00'
assert ms['r16-1']['home_origin'] is None and ms['r16-1']['away_origin'] is None
assert ms['r16-1']['kickoff_utc'] is None
print('Task 1 OK')
"
```

Expected: `Task 1 OK`.

- [ ] **Step 4: Commit**

```bash
git add app.py
git commit -m "Add R32_SCHEDULE constant + seed origins/kickoffs

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: `migrate_data()` backfill (idempotent, no-clobber)

Upgrade the existing on-disk `data.json` (16 R32 matches currently all-null) without overwriting any admin-entered values.

**Files:**
- Modify: `app.py` — `migrate_data` (the match-field backfill loop ~lines 187-196).

- [ ] **Step 1: Add origin keys to the generic field-backfill loop**

In `migrate_data`, the loop currently reads:

```python
    # Backfill missing match fields.
    for m in data["matches"]:
        for field in ("home_team", "away_team", "kickoff_utc",
                      "home_score", "away_score", "advanced_team"):
            if field not in m:
                m[field] = None
                changed = True
        if "round" not in m:
            m["round"] = "r32"
            changed = True
```

Add `"home_origin", "away_origin"` to the field tuple:

```python
    # Backfill missing match fields.
    for m in data["matches"]:
        for field in ("home_team", "away_team", "home_origin", "away_origin",
                      "kickoff_utc", "home_score", "away_score", "advanced_team"):
            if field not in m:
                m[field] = None
                changed = True
        if "round" not in m:
            m["round"] = "r32"
            changed = True
```

- [ ] **Step 2: Add the R32 fill-if-empty backfill block**

Directly after that loop (and before `if changed: _write(data)`), insert:

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

- [ ] **Step 3: Run the backfill / no-clobber / idempotency test**

This test monkeypatches `app._write` to a no-op so it **never touches the real `data.json`**:

```bash
python3 -c "
import copy, app

# Guard: never write the real data.json during this test.
app._write = lambda data: None

# (a) backfill: all-null existing matches gain origins + kickoff; R16+ stay None
data = {'users': {}, 'predictions': {}, 'matches': [
    {'id':'r32-1','round':'r32','home_team':None,'away_team':None,'kickoff_utc':None,'home_score':None,'away_score':None,'advanced_team':None},
    {'id':'r16-1','round':'r16','home_team':None,'away_team':None,'kickoff_utc':None,'home_score':None,'away_score':None,'advanced_team':None},
]}
out = app.migrate_data(data)
b = {x['id']: x for x in out['matches']}
assert b['r32-1']['home_origin'] == '2A' and b['r32-1']['away_origin'] == '2B'
assert b['r32-1']['kickoff_utc'] == '2026-06-28T19:00:00+00:00'
assert b['r16-1']['home_origin'] is None and b['r16-1']['kickoff_utc'] is None

# (b) no-clobber: real team + custom kickoff are preserved; only empty origin fills
data2 = {'users': {}, 'predictions': {}, 'matches': [
    {'id':'r32-1','round':'r32','home_team':'Brazil','away_team':'Chile','home_origin':None,'away_origin':None,'kickoff_utc':'2026-06-28T12:00:00+00:00','home_score':None,'away_score':None,'advanced_team':None},
]}
b2 = {x['id']: x for x in app.migrate_data(data2)['matches']}
assert b2['r32-1']['home_team'] == 'Brazil', 'real team clobbered!'
assert b2['r32-1']['kickoff_utc'] == '2026-06-28T12:00:00+00:00', 'custom kickoff clobbered!'
assert b2['r32-1']['home_origin'] == '2A', 'empty origin should fill'

# (c) idempotency: re-migrating already-migrated data triggers no write
calls = []
app._write = lambda data: calls.append(1)
app.migrate_data(copy.deepcopy(out))
assert calls == [], 'second migrate should be a no-op (no write)'
print('Task 2 OK')
"
```

Expected: `Task 2 OK`.

- [ ] **Step 4: Commit**

```bash
git add app.py
git commit -m "Backfill R32 origins + kickoffs in migrate_data (idempotent, no-clobber)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: `slot_label()` helper + `_bracket_view` + context injection

**Files:**
- Modify: `app.py` — add `slot_label` after `feed_label_pair` (~line 117); refactor `_bracket_view` (~line 566); add to `inject_i18n_helpers` (~line 421).

- [ ] **Step 1: Add the `slot_label` helper**

In `app.py`, directly after the `feed_label_pair` function (ends ~line 116), add:

```python
def slot_label(match, side):
    """Display label for one slot of a match. Precedence:
    real team → origin slot code (R32) → feed-label placeholder (R16+) → 'TBD'.
    `side` is 'home' or 'away'. Requires app context (uses translate())."""
    team = match.get(f"{side}_team")
    if team:
        return team
    origin = match.get(f"{side}_origin")
    if origin:
        return origin
    top_lbl, bot_lbl = feed_label_pair(match)
    feed = top_lbl if side == "home" else bot_lbl
    return feed or translate("TBD")
```

- [ ] **Step 2: Refactor `_bracket_view` to use it (single source of truth)**

Replace the current `_bracket_view` (~lines 566-577):

```python
def _bracket_view(match):
    """Resolve a match into display fields for the bracket: real team names when
    set, else feed-label placeholders."""
    top_lbl, bot_lbl = feed_label_pair(match)
    home, away = match.get("home_team"), match.get("away_team")
    return {
        **match,
        "home_display": home or top_lbl or translate("TBD"),
        "away_display": away or bot_lbl or translate("TBD"),
        "home_is_placeholder": not home,
        "away_is_placeholder": not away,
    }
```

with:

```python
def _bracket_view(match):
    """Resolve a match into display fields for the bracket: real team names when
    set, else origin slot codes (R32), else feed-label placeholders."""
    return {
        **match,
        "home_display": slot_label(match, "home"),
        "away_display": slot_label(match, "away"),
        "home_is_placeholder": not match.get("home_team"),
        "away_is_placeholder": not match.get("away_team"),
    }
```

- [ ] **Step 3: Inject `slot_label` into templates**

In `inject_i18n_helpers` (~line 421), add `slot_label` to the returned dict. It becomes:

```python
@app.context_processor
def inject_i18n_helpers():
    return {
        "_": translate,
        "lang": getattr(g, "lang", "en"),
        "round_label": lambda r: translate(ROUND_LABELS.get(r, r)),
        "is_locked": is_locked,
        "is_predictable": is_predictable,
        "has_teams": has_teams,
        "slot_label": slot_label,
        "compute_points": compute_points,
    }
```

- [ ] **Step 4: Run the slot_label / bracket-view test**

```bash
python3 -c "
from app import app, slot_label, _bracket_view
with app.test_request_context('/'):
    # origin fallback (no real team, has origin)
    m = {'id':'r32-1','round':'r32','home_team':None,'away_team':None,'home_origin':'2A','away_origin':'2B'}
    assert slot_label(m,'home') == '2A' and slot_label(m,'away') == '2B'
    # real team wins over origin
    assert slot_label(dict(m, home_team='Brazil'),'home') == 'Brazil'
    # R16 (no origin) -> feed label
    m16 = {'id':'r16-1','round':'r16','home_team':None,'away_team':None,'home_origin':None,'away_origin':None}
    assert slot_label(m16,'home') == 'Winner R32-1' and slot_label(m16,'away') == 'Winner R32-2'
    # truly empty R32 (no origin) -> TBD
    m0 = {'id':'r32-1','round':'r32','home_team':None,'away_team':None,'home_origin':None,'away_origin':None}
    assert slot_label(m0,'home') == 'TBD'
    # _bracket_view uses it; origin slot is still a placeholder (muted)
    v = _bracket_view(m)
    assert v['home_display'] == '2A' and v['home_is_placeholder'] is True
print('Task 3 OK')
"
```

Expected: `Task 3 OK`.

- [ ] **Step 5: Commit**

```bash
git add app.py
git commit -m "Add slot_label helper (team->origin->feed->TBD); use in bracket + templates

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 4: Show origins on the dashboard

The bracket already shows origins (via `_bracket_view` from Task 3). The dashboard's match list still prints a bare "TBD" for team-less matches — update its `else` branch to show origins. `predict.html` and `bracket.html` need **no change** (predict is only reachable for predictable/real-team matches; bracket flows through `_bracket_view`).

**Files:**
- Modify: `templates/dashboard.html` (lines 12-16).

- [ ] **Step 1: Update the team-display branch**

In `templates/dashboard.html`, replace:

```html
          {% if has_teams(m) %}
            <strong>{{ m.home_team }}</strong> vs <strong>{{ m.away_team }}</strong>
          {% else %}
            <span class="text-muted">{{ _("TBD") }}</span>
          {% endif %}
```

with:

```html
          {% if has_teams(m) %}
            <strong>{{ m.home_team }}</strong> vs <strong>{{ m.away_team }}</strong>
          {% else %}
            <span class="text-muted">{{ slot_label(m, 'home') }} vs {{ slot_label(m, 'away') }}</span>
          {% endif %}
```

- [ ] **Step 2: Verify the dashboard renders origins**

Registers a throwaway user (writes to the gitignored `data.json`), checks `/dashboard`, then removes that user. The schedule backfill in `data.json` is the intended end state and is left in place.

```bash
python3 -c "
from app import app, load_data, save_data
c = app.test_client()
c.post('/register', data={'username':'tmp_verify','password':'pw'})   # logs in
r = c.get('/dashboard')
assert r.status_code == 200, r.status_code
body = r.data.decode()
assert '2A' in body and '2B' in body and '2G' in body, 'origins missing on dashboard'
# clean up the throwaway user (and any predictions)
d = load_data()
d['users'].pop('tmp_verify', None)
d['predictions'].pop('tmp_verify', None)
save_data(d)
print('Task 4 OK')
"
```

Expected: `Task 4 OK`.

- [ ] **Step 3: Commit**

```bash
git add templates/dashboard.html
git commit -m "Dashboard: show R32 origin slots instead of bare TBD

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 5: Final integration verification (EN + ES)

**Files:** none (verification only).

- [ ] **Step 1: Compile check**

```bash
python3 -m py_compile app.py translations.py && echo "compile OK"
```

Expected: `compile OK`.

- [ ] **Step 2: Confirm data.json was backfilled by the live migration**

```bash
python3 -c "
from app import load_data
b = {m['id']: m for m in load_data()['matches']}
filled = [i for i in b if i.startswith('r32-') and b[i]['home_origin'] and b[i]['kickoff_utc']]
assert len(filled) == 16, f'expected 16 backfilled R32 matches, got {len(filled)}'
assert b['r16-1']['home_origin'] is None, 'R16 should have no origin'
print('data.json backfilled: 16 R32 matches have origins + kickoffs')
"
```

Expected: `data.json backfilled: 16 R32 matches have origins + kickoffs`.

- [ ] **Step 3: Bracket renders origins + kickoff dates (EN) and origin-only stays non-predictable**

```bash
python3 -c "
from app import app, load_data, is_predictable, deadline_tz_filter
c = app.test_client()
en = c.get('/bracket').data.decode()
assert '2A' in en and '2B' in en and '2G' in en and '1E' in en, 'R32 origins missing on bracket'
assert '3rd A/B/C/D/F' in en, 'multi-group origin missing'
assert 'Winner R32-1' in en, 'R16 feed labels should remain'
# kickoff conversion renders via the deadline_tz filter (shown on the dashboard, not
# the bracket): 2026-06-28T19:00Z -> America/Lima (UTC-5) = 02:00 PM Jun 28 2026.
with app.test_request_context('/'):
    out = deadline_tz_filter('2026-06-28T19:00:00+00:00')
    assert 'Jun 28' in out and '2026' in out, out
    r32_1 = next(m for m in load_data()['matches'] if m['id'] == 'r32-1')
    assert is_predictable(r32_1) is False, 'origin-only match must NOT be predictable'
print('EN + kickoff + predictability OK')
"
```

Expected: `EN + kickoff + predictability OK`.

- [ ] **Step 4: Bracket renders in Spanish (origins language-neutral, round labels translated)**

```bash
python3 -c "
from app import app
c = app.test_client()
c.get('/set-language/es')
es = c.get('/bracket').data.decode()
assert '2A' in es and '3rd A/B/C/D/F' in es, 'origins should be language-neutral'
assert 'Dieciseisavos' in es and 'Cuadro del Torneo' in es, 'ES round labels missing'
print('ES OK')
"
```

Expected: `ES OK`.

- [ ] **Step 5: Confirm no stray test users / secrets staged**

```bash
git status --short
```

Expected: clean working tree (all code committed in Tasks 1-4; `data.json` is gitignored and must NOT appear — its schedule backfill is the intended state and lives only on disk / the Render volume).
