# Reveal Player Forecasts in the Classification Table — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Show each player's predicted scoreline + advancing-team pick in the leaderboard's "Points by match" matrix, revealing another player's forecast for a match only after that match kicks off (a player's own forecast is always visible).

**Architecture:** Purely additive display. `build_leaderboard` gains a `pred_by_id` field per row (the user's raw predictions map); the `/leaderboard` route passes the current viewer's username; `leaderboard.html` renders the forecast inside each existing matrix cell, gated by `row.user == viewer or is_locked(m)`. `team_abbr` is added to the template context processor so the advance pick can render as a 3-letter code. No data-model or scoring change.

**Tech Stack:** Flask, Jinja2, single-file `app.py`. No test framework — tests are standalone Python scripts run with `python`, using `app.test_client()`, exactly as verification has been done in this repo.

## Global Constraints

- Match ids are strings (e.g. `"r32-1"`); never coerce to int.
- Never store naive local datetimes; `is_locked` is the single lock authority and fails **locked** on a bad/missing deadline — do not reimplement lock logic.
- No scoring change: `compute_points`, `TIERS`, and all existing leaderboard aggregates (`total`, `round_points`, `points_by_id`, `score_points`, `advance_points`) stay byte-for-byte the same.
- Spanish strings live in `translations.py` (never inline in templates).
- Keep business logic in Python helpers, not templates.
- Syntax check before every commit: `python -m py_compile app.py translations.py`.
- Run test scripts from the project dir with the repo on the path: `PYTHONPATH=/home/yurif/WC-forecast python <script>`.
- Scratchpad dir for test scripts: `/tmp/claude-1000/-home-yurif-WC-forecast/5be926ee-63a3-42a6-b800-9a93e825047d/scratchpad`. Never `git add` scratchpad files.

---

### Task 1: Backend — expose per-user predictions + viewer + `team_abbr`

**Files:**
- Modify: `app.py` — `build_leaderboard` (adds `pred_by_id` to each row), `inject_i18n_helpers` (adds `team_abbr`), `leaderboard` route (passes `viewer`).
- Test: `<scratchpad>/test_leaderboard_backend.py`

**Interfaces:**
- Consumes: `build_leaderboard(data)` existing behavior; `data["predictions"]` shape `{user: {match_id: {"home", "away", "advance"}}}`; `team_abbr(team, lang)` (already defined in `app.py`).
- Produces: each `build_leaderboard` row gains `"pred_by_id": {match_id: {"home","away","advance"}}` (== `data["predictions"].get(user, {})`, `{}` when the user has none). Template context gains `team_abbr` (callable `team_abbr(team, lang)`). The `leaderboard` route passes template var `viewer` (`str | None`).

- [ ] **Step 1: Write the failing test**

Create `<scratchpad>/test_leaderboard_backend.py`:

```python
from app import build_leaderboard, app as flask_app

data = {
    "users": {"ana": {}, "ben": {}},
    "predictions": {"ana": {"r32-1": {"home": 2, "away": 1, "advance": "Canada"}}},
    "matches": [
        {"id": "r32-1", "round": "r32", "home_team": "South Africa", "away_team": "Canada",
         "home_score": None, "away_score": None, "advanced_team": None},
    ],
    "simulations": {}, "shared_sims": {},
}

rows = build_leaderboard(data)
ana = next(r for r in rows if r["user"] == "ana")
ben = next(r for r in rows if r["user"] == "ben")

# pred_by_id present and correct
assert ana["pred_by_id"] == {"r32-1": {"home": 2, "away": 1, "advance": "Canada"}}, ana["pred_by_id"]
assert ben["pred_by_id"] == {}, ben["pred_by_id"]
# existing aggregates untouched
assert set(ana) >= {"user", "total", "round_points", "points_by_id",
                    "score_points", "advance_points", "pred_by_id"}

# team_abbr injected into template context
with flask_app.test_request_context():
    procs = flask_app.jinja_env.globals  # not where context processors live; check via processor
ctx = {}
for func in flask_app.template_context_processors[None]:
    with flask_app.test_request_context():
        ctx.update(func())
assert "team_abbr" in ctx and callable(ctx["team_abbr"]), "team_abbr not injected"
assert ctx["team_abbr"]("Brazil", "en") == "BRA", ctx["team_abbr"]("Brazil", "en")

print("PASS: backend exposes pred_by_id + team_abbr")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=/home/yurif/WC-forecast python <scratchpad>/test_leaderboard_backend.py`
Expected: FAIL — `AssertionError` on `ana["pred_by_id"]` (KeyError first: `pred_by_id` missing), and `team_abbr` not in context.

- [ ] **Step 3: Add `pred_by_id` to `build_leaderboard` rows**

In `app.py`, in `build_leaderboard`, the row dict currently is:

```python
        rows.append({
            "user": user,
            "total": total,
            "round_points": round_points,
            "points_by_id": points_by_id,
            "score_points": score_points,
            "advance_points": advance_points,
        })
```

Change to add one line (`user_preds` is already defined at the top of the loop):

```python
        rows.append({
            "user": user,
            "total": total,
            "round_points": round_points,
            "points_by_id": points_by_id,
            "score_points": score_points,
            "advance_points": advance_points,
            "pred_by_id": user_preds,
        })
```

- [ ] **Step 4: Inject `team_abbr` into the template context**

In `app.py`, in `inject_i18n_helpers`, add `team_abbr` to the returned dict (next to `match_short`):

```python
        "match_short": match_short,
        "team_abbr": team_abbr,
        "compute_points": compute_points,
```

- [ ] **Step 5: Pass `viewer` from the `leaderboard` route**

In `app.py`, the `leaderboard` route currently ends:

```python
    return render_template("leaderboard.html", rows=rows, matches=matches, rounds=rounds)
```

Change to:

```python
    return render_template("leaderboard.html", rows=rows, matches=matches, rounds=rounds,
                           viewer=session.get("username"))
```

(`session` is already imported in `app.py`.)

- [ ] **Step 6: Run test to verify it passes**

Run: `PYTHONPATH=/home/yurif/WC-forecast python <scratchpad>/test_leaderboard_backend.py`
Expected: `PASS: backend exposes pred_by_id + team_abbr`

- [ ] **Step 7: Syntax check + commit**

```bash
python -m py_compile app.py
git add app.py
git commit -m "Leaderboard: expose pred_by_id + viewer + inject team_abbr"
```

---

### Task 2: Template + i18n — render the gated forecast in each cell

**Files:**
- Modify: `templates/leaderboard.html` — the "Points by match" matrix body cell.
- Modify: `translations.py` — add the "Hidden until kickoff" string.
- Test: `<scratchpad>/test_leaderboard_reveal.py`

**Interfaces:**
- Consumes: `row.pred_by_id`, `row.points_by_id`, template var `viewer`, and injected `is_locked`, `team_abbr`, `lang`, `_` (all from Task 1 + existing context processor).
- Produces: user-visible behavior only (no new symbols).

- [ ] **Step 1: Write the failing test**

Create `<scratchpad>/test_leaderboard_reveal.py`. It seeds an isolated `DATA_FILE` with one **open** match (future kickoff) and one **locked** match (past kickoff), two players with distinct scorelines, and asserts the reveal rule via the rendered HTML:

```python
import app, tempfile, os

app.DATA_FILE = os.path.join(tempfile.mkdtemp(), "d.json")
data = {
    "users": {"ana": {"email": None, "password_hash": "x", "reset_token": None,
                      "reset_expires": None, "preferred_lang": "en"},
              "ben": {"email": None, "password_hash": "x", "reset_token": None,
                      "reset_expires": None, "preferred_lang": "en"},
              "cat": {"email": None, "password_hash": "x", "reset_token": None,
                      "reset_expires": None, "preferred_lang": "en"}},
    "admin_password": "x",
    "matches": [
        {"id": "r32-1", "round": "r32", "home_team": "South Africa", "away_team": "Canada",
         "home_origin": None, "away_origin": None, "venue": None,
         "kickoff_utc": "2099-01-01T00:00:00+00:00",   # OPEN (far future)
         "home_score": None, "away_score": None, "advanced_team": None},
        {"id": "r32-2", "round": "r32", "home_team": "Germany", "away_team": "Paraguay",
         "home_origin": None, "away_origin": None, "venue": None,
         "kickoff_utc": "2020-01-01T00:00:00+00:00",   # LOCKED (past)
         "home_score": None, "away_score": None, "advanced_team": None},
    ],
    "predictions": {
        "ana": {"r32-1": {"home": 2, "away": 1, "advance": "Canada"},
                "r32-2": {"home": 3, "away": 0, "advance": "Germany"}},
        "ben": {"r32-1": {"home": 4, "away": 5, "advance": "Canada"},
                "r32-2": {"home": 6, "away": 1, "advance": "Paraguay"}},
        # cat: no predictions
    },
    "simulations": {}, "shared_sims": {},
}
app._write(data)

app.app.config["TESTING"] = True
c = app.app.test_client()

# Viewer = ana
with c.session_transaction() as s:
    s["username"] = "ana"
html = c.get("/leaderboard").get_data(as_text=True)

assert "2-1" in html,  "ana's own forecast on OPEN match must be visible"        # own, open
assert "4-5" not in html, "ben's forecast on OPEN match must be hidden from ana" # other, open
assert "6-1" in html,  "ben's forecast on LOCKED match must be revealed"         # other, locked
assert "3-0" in html,  "ana's own forecast on LOCKED match visible"
assert "—" in html, "cat (no prediction) must show em-dash on the locked match"
assert "CAN" in html or "GER" in html, "advance pick 3-letter code should render"

# Anonymous viewer: open-match forecasts all hidden, locked shown
c2 = app.app.test_client()
anon = c2.get("/leaderboard").get_data(as_text=True)
assert "2-1" not in anon, "anon must not see any OPEN-match forecast"
assert "4-5" not in anon, "anon must not see any OPEN-match forecast"
assert "6-1" in anon,     "anon still sees LOCKED-match forecasts"

print("PASS: forecast reveal rule holds")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=/home/yurif/WC-forecast python <scratchpad>/test_leaderboard_reveal.py`
Expected: FAIL on `assert "2-1" in html` — the template does not render forecasts yet.

- [ ] **Step 3: Add the i18n string**

In `translations.py`, inside `SPANISH_TRANSLATIONS`, add (next to the other Predictions entries, e.g. after `"Deadline": "Cierre",`):

```python
    "Hidden until kickoff": "Oculto hasta el inicio",
```

- [ ] **Step 4: Render the gated forecast in the matrix cell**

In `templates/leaderboard.html`, the matrix body loop currently is:

```html
        {% for m in matches %}
        {% set pts = row.points_by_id[m.id].total %}
        <td class="text-center">
          {% if pts > 0 %}<span class="badge bg-success">{{ pts }}</span>
          {% else %}<span class="text-muted">0</span>{% endif %}
        </td>
        {% endfor %}
```

Replace that block with:

```html
        {% for m in matches %}
        {% set pts = row.points_by_id[m.id].total %}
        {% set pred = row.pred_by_id.get(m.id) %}
        {% set revealed = (row.user == viewer) or is_locked(m) %}
        <td class="text-center">
          {% if pts > 0 %}<span class="badge bg-success">{{ pts }}</span>
          {% else %}<span class="text-muted">0</span>{% endif %}
          <div class="small text-muted">
            {% if not revealed %}
              <span title="{{ _('Hidden until kickoff') }}">·</span>
            {% elif pred %}
              {{ pred.home }}-{{ pred.away }}{% if pred.advance %} ·{{ team_abbr(pred.advance, lang) }}{% endif %}
            {% else %}
              —
            {% endif %}
          </div>
        </td>
        {% endfor %}
```

- [ ] **Step 5: Run test to verify it passes**

Run: `PYTHONPATH=/home/yurif/WC-forecast python <scratchpad>/test_leaderboard_reveal.py`
Expected: `PASS: forecast reveal rule holds`

- [ ] **Step 6: Syntax check + manual render sanity**

```bash
python -m py_compile app.py translations.py
```

Then confirm the real page still renders (uses the live `data.json`):

Run:
```bash
python -c "
import app
app.app.config['TESTING']=True
c=app.app.test_client()
with c.session_transaction() as s: s['username']='testuser'
r=c.get('/leaderboard'); print('status', r.status_code)
assert r.status_code==200
"
```
Expected: `status 200`

- [ ] **Step 7: Commit**

```bash
git add templates/leaderboard.html translations.py
git commit -m "Leaderboard: reveal forecasts in matrix (own always, others at kickoff)"
```

---

### Task 3: Docs — record the new behavior + injected helper

**Files:**
- Modify: `CLAUDE.md` — leaderboard section (note the revealed forecast + gating) and the injected-helpers list (add `team_abbr`).

- [ ] **Step 1: Update the leaderboard description**

In `CLAUDE.md`, in the `build_leaderboard` / `/leaderboard` paragraph, append a sentence after the matrix description:

```
The matrix also shows each player's **forecast** (`pred_by_id`: predicted scoreline +
advance code via `team_abbr`) beneath the points badge, gated per cell by
`row.user == viewer or is_locked(match)` — your own is always visible, others' reveal
at kickoff. `/leaderboard` is public, so `viewer` is `session.get("username")` or None.
```

- [ ] **Step 2: Update the injected-helpers list**

In `CLAUDE.md`, in the Templates section, the `inject_i18n_helpers` list currently ends `… match_short`, `compute_points`. Add `team_abbr`:

```
`match_number`, `match_short`, `team_abbr`, `compute_points`).
```

- [ ] **Step 3: Commit**

```bash
git add CLAUDE.md
git commit -m "Docs: leaderboard reveals forecasts; team_abbr injected"
```

---

## Self-Review

**Spec coverage:**
- Placement in Points-by-match matrix → Task 2 Step 4. ✓
- Visibility rule (own OR is_locked; viewer from session; public page) → Task 1 Step 5 (viewer), Task 2 Step 4 (`revealed`). ✓
- Content: `2-1 ·BRA` / `—` / hidden `·` → Task 2 Step 4. ✓
- Data flow: `pred_by_id`, viewer, `team_abbr` injection → Task 1. ✓
- i18n "Hidden until kickoff" EN/ES → Task 2 Step 3. ✓
- No scoring/data-model change → asserted in Task 1 test (aggregates intact); template-only display. ✓
- Testing scenarios (own pre-lock, others pre-lock, others post-lock, no-pred `—`, anonymous) → Task 2 Step 1 test covers all five. ✓

**Placeholder scan:** No TBD/TODO; every code step shows full code. ✓

**Type consistency:** `pred_by_id` shape (`{match_id: {"home","away","advance"}}`) consistent across Task 1 producer and Task 2 consumer; `team_abbr(team, lang)` signature matches `app.py` and both usages; `viewer` is `str | None` in route and template. ✓
