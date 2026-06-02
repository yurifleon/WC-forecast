# Team Dropdown + Match Labels Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the admin free-text team boxes with group-narrowed team dropdowns (sourced from the master guide), and show each match's FIFA number (`M73`–`M104`) on bracket, dashboard, admin, and predict.

**Architecture:** All derived, no schema change. `GROUPS`/`ALL_TEAMS` constants + a `team_options(match, side, by_id)` helper compute each slot's candidate teams (R32 by origin group; R16+ by feeder winner/loser). `match_number(match)` derives the FIFA number from position. The admin route enriches matches with `home_options`/`away_options`; templates render `<select>`s and `M<n>` labels via injected helpers.

**Tech Stack:** Flask, Jinja2. Single-file `app.py`. No pytest — verify with `python -m py_compile` + `python -c` assertions. Use `python3`.

**Spec:** `docs/superpowers/specs/2026-06-01-team-dropdown-and-match-labels-design.md`

---

### Task 1: Data + helpers (`GROUPS`, `team_options`, `match_number`) + injection

**Files:** Modify `app.py` (add constants/helpers near the other bracket helpers ~line 80-145; add to the `inject_i18n_helpers` context processor ~line 510).

- [ ] **Step 1: Add `GROUPS` / `ALL_TEAMS` constants**

In `app.py`, add immediately after the `ROUND_CODE_SHORT` / `_FEEDER_PREV` block (just before `def feeders`):

```python
# 48 participating nations by group (source: FIFA_WC_2026_Master_Guide.md). Used to
# narrow the admin team dropdown to a match's possible teams.
GROUPS = {
    "A": ["Mexico", "South Africa", "South Korea", "Czechia"],
    "B": ["Canada", "Bosnia and Herzegovina", "Qatar", "Switzerland"],
    "C": ["Brazil", "Morocco", "Costa Rica", "Sweden"],
    "D": ["United States", "Paraguay", "Australia", "Türkiye"],
    "E": ["Germany", "Ecuador", "Côte d'Ivoire", "Curaçao"],
    "F": ["Italy", "Japan", "Tunisia", "Haiti"],
    "G": ["Belgium", "Egypt", "Iran", "New Zealand"],
    "H": ["Spain", "Uruguay", "Saudi Arabia", "Cape Verde"],
    "I": ["France", "Senegal", "Norway", "Iraq"],
    "J": ["Argentina", "Austria", "Algeria", "Jordan"],
    "K": ["Portugal", "Colombia", "Uzbekistan", "DR Congo"],
    "L": ["England", "Croatia", "Ghana", "Panama"],
}
ALL_TEAMS = sorted({t for teams in GROUPS.values() for t in teams})  # 48; dropdown fallback
```

- [ ] **Step 2: Add `_origin_groups` and `team_options`**

Add directly after `feed_label_pair` (it ends ~line 130, before `def slot_label`) — `team_options` uses `feeders` (defined above) and is pure (no app context):

```python
def _origin_groups(origin):
    """Group letters an R32 origin slot can draw from. '2A' -> ['A'];
    '3rd A/B/C/D/F' -> ['A','B','C','D','F']; unknown/empty -> []."""
    if not origin:
        return []
    if origin.startswith("3rd "):
        return [g for g in origin[4:].split("/") if g in GROUPS]
    if origin[0] in "12":
        g = origin[1:]
        return [g] if g in GROUPS else []
    return []


def team_options(match, side, by_id):
    """Candidate real teams for one slot of a match, for the admin dropdown.
    R32: teams from the origin's group(s) (fallback to all 48 if unparseable).
    R16/QF/SF/Final: the winner (advanced_team) of the feeding match.
    Third place: the loser of the feeding semifinal. Empty list when undecided.
    `by_id` maps match id -> match dict. Returns a sorted, de-duplicated list."""
    origin = match.get(f"{side}_origin")
    if origin:  # Round of 32
        teams = sorted({t for g in _origin_groups(origin) for t in GROUPS[g]})
        return teams or ALL_TEAMS
    f = feeders(match)
    if not f:
        return ALL_TEAMS
    word, top, bot = f
    feeder = by_id.get(top if side == "home" else bot)
    if not feeder:
        return []
    if word == "Loser":
        return [t for t in (feeder.get("home_team"), feeder.get("away_team"))
                if t and t != feeder.get("advanced_team")]
    adv = feeder.get("advanced_team")
    return [adv] if adv else []
```

- [ ] **Step 3: Add `match_number` + base table**

Add directly after `team_options`:

```python
_MATCH_NO_BASE = {"r32": 72, "r16": 88, "qf": 96, "sf": 100, "third": 102, "final": 103}


def match_number(match):
    """FIFA match number (73–104), derived from round + numeric id suffix.
    r32-1->73 … r32-16->88, r16-1->89 … final-1->104. None for unknown rounds."""
    base = _MATCH_NO_BASE.get(match.get("round"))
    if base is None:
        return None
    try:
        return base + int(str(match["id"]).rsplit("-", 1)[-1])
    except (ValueError, KeyError):
        return None
```

- [ ] **Step 4: Inject `match_number` into templates**

In `inject_i18n_helpers` (~line 510), add `match_number` to the returned dict. After the edit it reads:

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
        "match_number": match_number,
        "compute_points": compute_points,
    }
```

(If your local copy lists the helpers in a slightly different order, just add the single `"match_number": match_number,` line — don't reorder the rest.)

- [ ] **Step 5: Run the test**

```bash
python3 -m py_compile app.py
python3 -c "
from app import GROUPS, ALL_TEAMS, _origin_groups, team_options, match_number

assert len(ALL_TEAMS) == 48 and len(set(ALL_TEAMS)) == 48
assert _origin_groups('2A') == ['A'] and _origin_groups('1F') == ['F']
assert _origin_groups('3rd A/B/C/D/F') == ['A','B','C','D','F']
assert _origin_groups('') == [] and _origin_groups(None) == []

# R32 narrowing
by_id = {}
m_r32 = {'id':'r32-1','round':'r32','home_origin':'2A','away_origin':'2B'}
assert team_options(m_r32,'home',by_id) == sorted(GROUPS['A']), team_options(m_r32,'home',by_id)
assert team_options(m_r32,'away',by_id) == sorted(GROUPS['B'])
m_3rd = {'id':'r32-2','round':'r32','home_origin':'1E','away_origin':'3rd A/B/C/D/F'}
exp = sorted(set(GROUPS['A']+GROUPS['B']+GROUPS['C']+GROUPS['D']+GROUPS['F']))
assert team_options(m_3rd,'away',by_id) == exp and len(exp) == 20

# R16+ from feeders
by_id = {
  'r32-1':{'id':'r32-1','round':'r32','advanced_team':'Brazil'},
  'r32-2':{'id':'r32-2','round':'r32','advanced_team':None},
  'sf-1':{'id':'sf-1','round':'sf','home_team':'Spain','away_team':'France','advanced_team':'France'},
  'sf-2':{'id':'sf-2','round':'sf','home_team':'Brazil','away_team':'Argentina','advanced_team':'Brazil'},
}
m_r16 = {'id':'r16-1','round':'r16','home_origin':None,'away_origin':None}
assert team_options(m_r16,'home',by_id) == ['Brazil']      # winner of r32-1
assert team_options(m_r16,'away',by_id) == []              # r32-2 undecided
m_final = {'id':'final-1','round':'final','home_origin':None,'away_origin':None}
assert team_options(m_final,'home',by_id) == ['France']    # winner of sf-1
m_third = {'id':'third-1','round':'third','home_origin':None,'away_origin':None}
assert team_options(m_third,'home',by_id) == ['Spain']     # loser of sf-1
assert team_options(m_third,'away',by_id) == ['Argentina'] # loser of sf-2

# match_number contiguous 73..104
from app import _MATCH_NO_BASE
plan = [('r32',16),('r16',8),('qf',4),('sf',2),('third',1),('final',1)]
nums = [match_number({'id':f'{r}-{k}','round':r}) for r,c in plan for k in range(1,c+1)]
assert nums == list(range(73,105)), nums
assert match_number({'id':'x-1','round':'group'}) is None
print('Task 1 OK')
"
```

Expected: `Task 1 OK`.

- [ ] **Step 6: Commit**

```bash
git add app.py
git commit -m "Add GROUPS data, team_options + match_number helpers, inject match_number

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: Admin team dropdowns + match label

**Files:** Modify `app.py` (the `admin` route GET render, ~lines 779-787) and `templates/admin.html`.

- [ ] **Step 1: Enrich matches with options in the `admin` route**

In `app.py`, replace the GET-render tail of the `admin` route:

```python
    matches = sorted_matches(data["matches"])
    return render_template(
        "admin.html",
        is_admin=session.get("is_admin", False),
        matches=matches,
        users=data["users"],
        utc_iso_to_local_input=utc_iso_to_local_input,
        tz_label=DISPLAY_TZ_LABEL,
    )
```

with:

```python
    by_id = {m["id"]: m for m in data["matches"]}
    matches = [
        {**m, "home_options": team_options(m, "home", by_id),
              "away_options": team_options(m, "away", by_id)}
        for m in sorted_matches(data["matches"])
    ]
    return render_template(
        "admin.html",
        is_admin=session.get("is_admin", False),
        matches=matches,
        users=data["users"],
        utc_iso_to_local_input=utc_iso_to_local_input,
        tz_label=DISPLAY_TZ_LABEL,
    )
```

- [ ] **Step 2: Replace the team text inputs with dropdowns in `admin.html`**

In `templates/admin.html`, replace this block:

```html
          <div class="col-md-9">
            <label class="small text-muted">{{ _("Teams") }}</label>
            <div class="d-flex align-items-center gap-2">
              <input class="form-control form-control-sm" name="home_team" placeholder="" value="{{ m.home_team or '' }}">
              <span class="fw-bold">{{ _("vs") }}</span>
              <input class="form-control form-control-sm" name="away_team" placeholder="" value="{{ m.away_team or '' }}">
            </div>
          </div>
```

with:

```html
          <div class="col-md-9">
            <label class="small text-muted">{{ _("Teams") }}</label>
            <div class="d-flex align-items-center gap-2">
              <select class="form-select form-select-sm" name="home_team">
                <option value="">—</option>
                {% for t in m.home_options %}
                <option value="{{ t }}" {{ 'selected' if t == m.home_team }}>{{ t }}</option>
                {% endfor %}
                {% if m.home_team and m.home_team not in m.home_options %}
                <option value="{{ m.home_team }}" selected>{{ m.home_team }}</option>
                {% endif %}
              </select>
              <span class="fw-bold">{{ _("vs") }}</span>
              <select class="form-select form-select-sm" name="away_team">
                <option value="">—</option>
                {% for t in m.away_options %}
                <option value="{{ t }}" {{ 'selected' if t == m.away_team }}>{{ t }}</option>
                {% endfor %}
                {% if m.away_team and m.away_team not in m.away_options %}
                <option value="{{ m.away_team }}" selected>{{ m.away_team }}</option>
                {% endif %}
              </select>
            </div>
          </div>
```

- [ ] **Step 3: Add the match number to the admin round-label line**

In `templates/admin.html`, replace:

```html
        <span class="accent small">{{ round_label(m.round) }} — {{ _("single match") }}</span>
```

with:

```html
        <span class="accent small">{{ round_label(m.round) }} · M{{ match_number(m) }} — {{ _("single match") }}</span>
```

- [ ] **Step 4: Verify admin renders dropdowns + label**

Sets `is_admin` in the session (no password needed) and checks the rendered admin page:

```bash
python3 -m py_compile app.py
python3 -c "
from app import app
c = app.test_client()
with c.session_transaction() as s:
    s['is_admin'] = True
body = c.get('/admin').data.decode()
assert '<select class=\"form-select form-select-sm\" name=\"home_team\">' in body, 'home_team not a select'
assert 'name=\"away_team\">' in body
# r32-1 home is origin 2A -> Group A teams must be options; a Group B team must NOT be in r32-1's home list
assert 'Mexico' in body and 'South Korea' in body, 'Group A teams missing'
assert 'M73' in body and 'M104' in body, 'match numbers missing'
assert 'name=\"home_team\" placeholder' not in body, 'old text input still present'
print('Task 2 OK')
"
```

Expected: `Task 2 OK`.

- [ ] **Step 5: Commit**

```bash
git add app.py templates/admin.html
git commit -m "Admin: group-narrowed team dropdowns + M-number label

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: Match number on bracket, dashboard, predict

**Files:** Modify `templates/bracket.html`, `templates/dashboard.html`, `templates/predict.html`.

- [ ] **Step 1: Bracket card — add a muted M-number**

In `templates/bracket.html`, inside the `match_card` macro's `<div class="card-body p-2 small">`, add a muted match-number line as the FIRST child (immediately after the opening `<div class="card-body p-2 small">` tag), before the home slot div:

```html
    <div class="text-muted" style="font-size:0.7rem">M{{ match_number(m) }}</div>
```

(The macro parameter is `m`, so `match_number(m)` resolves. The round is already the column header, so only the number is shown on the card.)

- [ ] **Step 2: Dashboard — append M-number to the round label**

In `templates/dashboard.html`, replace:

```html
          <span class="accent small">{{ round_label(m.round) }}</span><br>
```

with:

```html
          <span class="accent small">{{ round_label(m.round) }} · M{{ match_number(m) }}</span><br>
```

- [ ] **Step 3: Predict — insert M-number before the venue**

In `templates/predict.html`, replace the round-label span (it currently appends the venue):

```html
      <span class="accent small">{{ round_label(match.round) }}{% if match.venue %} · {{ match.venue }}{% endif %}</span>
```

with:

```html
      <span class="accent small">{{ round_label(match.round) }} · M{{ match_number(match) }}{% if match.venue %} · {{ match.venue }}{% endif %}</span>
```

(If your local `predict.html` line differs — e.g. the venue clause isn't present yet — just insert ` · M{{ match_number(match) }}` immediately after `{{ round_label(match.round) }}`, preserving whatever follows.)

- [ ] **Step 4: Verify M-numbers render across views**

```bash
python3 -c "
from app import app, load_data, save_data
c = app.test_client()
# bracket (public)
br = c.get('/bracket').data.decode()
assert 'M73' in br and 'M89' in br and 'M104' in br, 'bracket match numbers missing'
# dashboard (needs a logged-in user) + predict (needs a predictable match)
c.post('/register', data={'username':'tmp_mnum','password':'pw'})
dash = c.get('/dashboard').data.decode()
assert 'M73' in dash and 'M104' in dash, 'dashboard match numbers missing'
# make r32-1 predictable to view the predict heading
d = load_data(); m = next(x for x in d['matches'] if x['id']=='r32-1')
m['home_team']='Mexico'; m['away_team']='Canada'; save_data(d)
pred = c.get('/predict/r32-1').data.decode()
assert 'M73' in pred, 'predict match number missing'
# revert + remove throwaway user
d = load_data(); m = next(x for x in d['matches'] if x['id']=='r32-1'); m['home_team']=None; m['away_team']=None
d['users'].pop('tmp_mnum',None); d['predictions'].pop('tmp_mnum',None); save_data(d)
print('Task 3 OK')
"
```

Expected: `Task 3 OK`. Confirm `git status --short` shows only the three template files (NOT `data.json`).

- [ ] **Step 5: Commit**

```bash
git add templates/bracket.html templates/dashboard.html templates/predict.html
git commit -m "Show FIFA match number (M73–M104) on bracket, dashboard, predict

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 4: Final integration verification

**Files:** none (verification only).

- [ ] **Step 1: Compile + scoring safety**

```bash
python3 -m py_compile app.py translations.py && echo "compile OK"
python3 -c "
from app import compute_points
assert compute_points({'home':2,'away':1,'advance':'A'}, {'round':'r32','home_score':2,'away_score':1,'advanced_team':'A'}) == {'score':6,'advance':2,'total':8}
print('scoring OK')
"
```

Expected: `compile OK` then `scoring OK`.

- [ ] **Step 2: Admin dropdown narrowing is correct end-to-end**

```bash
python3 -c "
from app import app, GROUPS
c = app.test_client()
with c.session_transaction() as s:
    s['is_admin'] = True
body = c.get('/admin').data.decode()
import re
# Extract the first home_team <select>...</select> (r32-1, origin 2A) and confirm it
# contains Group A teams and excludes a clearly-other team like 'England' (Group L).
block = re.search(r'name=\"home_team\">(.*?)</select>', body, re.S).group(1)
for t in GROUPS['A']:
    assert t in block, f'missing {t} in r32-1 home options'
assert 'England' not in block, 'r32-1 home should be narrowed to Group A, not all 48'
print('admin narrowing OK')
"
```

Expected: `admin narrowing OK`.

- [ ] **Step 3: Bracket EN/ES still good; match numbers present; non-predictable holds**

```bash
python3 -c "
from app import app, load_data, is_predictable
c = app.test_client()
en = c.get('/bracket').data.decode()
assert '2A' in en and 'Winner R32-1' in en and 'M73' in en, 'bracket regressed'
c.get('/set-language/es')
es = c.get('/bracket').data.decode()
assert 'Dieciseisavos' in es and 'M89' in es, 'ES bracket regressed'
with app.test_request_context('/'):
    r16_1 = next(m for m in load_data()['matches'] if m['id']=='r16-1')
    assert is_predictable(r16_1) is False
print('integration OK')
"
```

Expected: `integration OK`.

- [ ] **Step 4: Confirm clean tree**

```bash
git status --short
```

Expected: clean (all code committed in Tasks 1-3; `data.json` gitignored — must NOT appear).
