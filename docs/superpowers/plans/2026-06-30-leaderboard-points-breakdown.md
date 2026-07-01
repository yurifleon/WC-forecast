# Leaderboard Points Breakdown Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a per-round points summary and a full per-match points matrix to the `/leaderboard` page, while keeping the existing Score/Advance split.

**Architecture:** All aggregation is derived at render time inside `build_leaderboard(data)` (no data-model changes). The `leaderboard()` route passes an ordered round list to the template. `templates/leaderboard.html` is rewritten into three stacked sections (per-round summary, per-match matrix, scoring card). No custom JS.

**Tech Stack:** Flask, Jinja2, Bootstrap 5.3 dark theme, Python 3.12.

## Global Constraints

- Match ids are strings (e.g. `"r32-1"`); never coerce to int.
- Keep business logic in Python helpers, not templates (CLAUDE.md).
- No custom JS; Bootstrap classes only.
- Valid rounds (lowercase): `r32`, `r16`, `qf`, `sf`, `third`, `final`.
- No linter is configured; the automated gate is `python -m py_compile app.py translations.py`. There is no pytest suite — behavior is checked with `python -c` snippets and manual page loads.
- New user-facing strings go through `_()` and get a Spanish entry in `translations.py`.
- Neutral-venue framing: no home/away (local/visitor) wording in templates.

---

### Task 1: Derive per-round, score/advance, and by-id aggregates in `build_leaderboard`

**Files:**
- Modify: `app.py:700-714` (`build_leaderboard`)

**Interfaces:**
- Consumes: `compute_points(pred, match)` → `{"score","advance","total"}` (unchanged); `ROUND_ORDER` (module constant).
- Produces: each row dict gains four keys in addition to `user`, `total`, `breakdown`:
  - `round_points`: `dict[str, int]` — total points per round key, seeded to `0` for all six rounds.
  - `score_points`: `int` — sum of `points["score"]` across breakdown.
  - `advance_points`: `int` — sum of `points["advance"]` across breakdown.
  - `points_by_id`: `dict[str, dict]` — `{match_id: points}` for matrix cell lookup by id.

- [ ] **Step 1: Add a behavior check script (the "failing test")**

Create `/tmp/claude-1000/-home-yurif-WC-forecast/4f188714-86ce-4cc9-9769-5be6ce740faf/scratchpad/check_leaderboard.py`:

```python
from app import build_leaderboard, ROUND_ORDER

data = {
    "users": {"alice": {}, "bob": {}},
    "predictions": {
        "alice": {
            "r32-1": {"home": 2, "away": 1, "advance": "Canada"},  # exact + advance
            "r16-1": {"home": 0, "away": 0, "advance": "Canada"},  # wrong
        },
        "bob": {},
    },
    "matches": [
        {"id": "r32-1", "round": "r32", "home_score": 2, "away_score": 1, "advanced_team": "Canada"},
        {"id": "r16-1", "round": "r16", "home_score": 3, "away_score": 1, "advanced_team": "Mexico"},
        {"id": "final-1", "round": "final", "home_score": None, "away_score": None, "advanced_team": None},
    ],
}

rows = build_leaderboard(data)
alice = next(r for r in rows if r["user"] == "alice")

# per-round: r32-1 exact(6)+advance(2)=8; r16-1 wrong=0; final untouched=0
assert alice["round_points"] == {"r32": 8, "r16": 0, "qf": 0, "sf": 0, "third": 0, "final": 0}, alice["round_points"]
# score/advance split
assert alice["score_points"] == 6, alice["score_points"]
assert alice["advance_points"] == 2, alice["advance_points"]
# by-id lookup
assert alice["points_by_id"]["r32-1"]["total"] == 8, alice["points_by_id"]["r32-1"]
assert alice["points_by_id"]["r16-1"]["total"] == 0
# round_points keys always cover all six rounds even for empty bob
bob = next(r for r in rows if r["user"] == "bob")
assert set(bob["round_points"]) == set(ROUND_ORDER), bob["round_points"]
assert bob["total"] == 0 and bob["score_points"] == 0
print("OK")
```

- [ ] **Step 2: Run it to verify it fails**

Run: `source .venv/bin/activate && python "$SCRATCH/check_leaderboard.py"` (where `$SCRATCH` is the scratchpad dir).
Expected: `KeyError: 'round_points'` (the key does not exist yet).

- [ ] **Step 3: Implement the aggregates**

Replace the body of `build_leaderboard` (`app.py:700-714`) with:

```python
def build_leaderboard(data):
    rows = []
    for user in data["users"].keys():
        user_preds = data["predictions"].get(user, {})
        total = 0
        score_points = 0
        advance_points = 0
        breakdown = []
        points_by_id = {}
        round_points = {rnd: 0 for rnd in ROUND_ORDER}
        for match in data["matches"]:
            pred = user_preds.get(match["id"])
            pts = compute_points(pred, match)
            breakdown.append({"match": match, "points": pts})
            points_by_id[match["id"]] = pts
            round_points[match["round"]] = round_points.get(match["round"], 0) + pts["total"]
            score_points += pts["score"]
            advance_points += pts["advance"]
            total += pts["total"]
        rows.append({
            "user": user,
            "total": total,
            "breakdown": breakdown,
            "round_points": round_points,
            "points_by_id": points_by_id,
            "score_points": score_points,
            "advance_points": advance_points,
        })
    rows.sort(key=lambda r: r["total"], reverse=True)
    return rows
```

Note: `round_points` is seeded from `ROUND_ORDER` (all six rounds → 0) and uses `.get(..., 0)` so an unexpected round key can't `KeyError`.

- [ ] **Step 4: Run the check to verify it passes**

Run: `source .venv/bin/activate && python "$SCRATCH/check_leaderboard.py"`
Expected: `OK`

- [ ] **Step 5: Syntax gate**

Run: `python -m py_compile app.py`
Expected: no output (exit 0).

- [ ] **Step 6: Commit**

```bash
git add app.py
git commit -m "Leaderboard: derive per-round, score/advance, and by-id point aggregates

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: Pass the ordered round list from the route

**Files:**
- Modify: `app.py:910-916` (`leaderboard` route)

**Interfaces:**
- Consumes: `build_leaderboard(data)`, `sorted_matches(...)` (unchanged).
- Produces: template context gains `rounds`: `list[tuple[str, str]]` — ordered `(round_key, short_label)` pairs: `[("r32","R32"),("r16","R16"),("qf","QF"),("sf","SF"),("third","3rd"),("final","F")]`.

- [ ] **Step 1: Behavior check (the "failing test")**

Append to the scratchpad check (new file `$SCRATCH/check_route.py`):

```python
from app import app

with app.test_client() as c:
    resp = c.get("/leaderboard", follow_redirects=True)
    assert resp.status_code == 200, resp.status_code
    body = resp.get_data(as_text=True)
    # per-round short headers must be present in the rendered page
    for label in ["R32", "R16", "QF", "SF", "3rd"]:
        assert label in body, f"missing header {label}"
print("OK")
```

- [ ] **Step 2: Run it — expect failure**

Run: `source .venv/bin/activate && python "$SCRATCH/check_route.py"`
Expected: AssertionError on a missing header (template not updated yet) — this also fails until Task 3, so it's acceptable for this check to stay red until Task 3 Step 4. Proceed to implement the route change now; this check goes green after Task 3.

- [ ] **Step 3: Update the route**

Replace `leaderboard()` (`app.py:910-916`) with:

```python
@app.route("/leaderboard")
def leaderboard():
    data = load_data()
    rows = build_leaderboard(data)
    matches = sorted_matches(data["matches"])
    rounds = [
        ("r32", "R32"), ("r16", "R16"), ("qf", "QF"),
        ("sf", "SF"), ("third", "3rd"), ("final", "F"),
    ]
    return render_template("leaderboard.html", rows=rows, matches=matches, rounds=rounds)
```

- [ ] **Step 4: Syntax gate**

Run: `python -m py_compile app.py`
Expected: no output (exit 0).

- [ ] **Step 5: Commit**

```bash
git add app.py
git commit -m "Leaderboard: pass ordered per-round column list to template

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: Rewrite `leaderboard.html` with per-round summary + per-match matrix

**Files:**
- Modify: `templates/leaderboard.html` (full rewrite)

**Interfaces:**
- Consumes: `rows` (each with `user`, `total`, `round_points`, `points_by_id`, `score_points`, `advance_points`), `matches` (from `sorted_matches`), `rounds` (from Task 2), and injected helpers `_`, `match_number`, `slot_label`.
- Produces: rendered HTML (no downstream consumers).

- [ ] **Step 1: Rewrite the template**

Replace the entire contents of `templates/leaderboard.html` with:

```jinja
{% extends "base.html" %}
{% block content %}
<h3 class="mb-3">{{ _("Leaderboard") }}</h3>

<div class="table-responsive mb-4">
  <table class="table">
    <thead>
      <tr>
        <th>{{ _("Rank") }}</th><th>{{ _("Player") }}</th>
        {% for key, label in rounds %}
        <th class="text-end" title="{{ round_label(key) }}">{{ label }}</th>
        {% endfor %}
        <th class="text-end">{{ _("Score points") }}</th>
        <th class="text-end">{{ _("Advance points") }}</th>
        <th class="text-end">{{ _("Total") }}</th>
      </tr>
    </thead>
    <tbody>
      {% for row in rows %}
      <tr>
        <td>{{ loop.index }}</td>
        <td>{{ row.user }}</td>
        {% for key, label in rounds %}
        {% set rp = row.round_points[key] %}
        <td class="text-end {% if rp == 0 %}text-muted{% endif %}">{{ rp }}</td>
        {% endfor %}
        <td class="text-end">{{ row.score_points }}</td>
        <td class="text-end">{{ row.advance_points }}</td>
        <td class="text-end accent fw-bold">{{ row.total }}</td>
      </tr>
      {% else %}
      <tr><td colspan="{{ rounds|length + 5 }}" class="text-muted">{{ _("No players yet.") }}</td></tr>
      {% endfor %}
    </tbody>
  </table>
</div>

{% if rows %}
<h5 class="mb-2">{{ _("Points by match") }}</h5>
<div class="table-responsive mb-4">
  <table class="table table-sm">
    <thead>
      <tr>
        <th>{{ _("Player") }}</th>
        {% for m in matches %}
        <th class="text-center" title="{{ slot_label(m, 'home') }} vs {{ slot_label(m, 'away') }}">
          M{{ match_number(m) }}
        </th>
        {% endfor %}
        <th class="text-center">{{ _("Total") }}</th>
      </tr>
    </thead>
    <tbody>
      {% for row in rows %}
      <tr>
        <td>{{ row.user }}</td>
        {% for m in matches %}
        {% set pts = row.points_by_id[m.id].total %}
        <td class="text-center">
          {% if pts > 0 %}<span class="badge bg-success">{{ pts }}</span>
          {% else %}<span class="text-muted">0</span>{% endif %}
        </td>
        {% endfor %}
        <td class="text-center accent fw-bold">{{ row.total }}</td>
      </tr>
      {% endfor %}
    </tbody>
  </table>
</div>
{% endif %}

<div class="card p-3" style="max-width: 32rem;">
  <h5>{{ _("Scoring") }}</h5>
  <table class="table table-sm mb-0">
    <thead>
      <tr><th></th><th class="text-end">R32</th><th class="text-end">R16</th>
          <th class="text-end">QF</th><th class="text-end">SF</th><th class="text-end">F</th></tr>
    </thead>
    <tbody>
      <tr><td>{{ _("Exact score") }}</td><td class="text-end">6</td><td class="text-end">7</td><td class="text-end">8</td><td class="text-end">9</td><td class="text-end">10</td></tr>
      <tr><td>{{ _("Result + goal difference") }}</td><td class="text-end">4</td><td class="text-end">5</td><td class="text-end">5</td><td class="text-end">6</td><td class="text-end">7</td></tr>
      <tr><td>{{ _("Result only") }}</td><td class="text-end">2</td><td class="text-end">3</td><td class="text-end">3</td><td class="text-end">4</td><td class="text-end">5</td></tr>
      <tr><td>{{ _("Correct advancing team") }}</td><td class="text-end">+2</td><td class="text-end">+2</td><td class="text-end">+3</td><td class="text-end">+3</td><td class="text-end">+4</td></tr>
    </tbody>
  </table>
</div>
{% endblock %}
```

Notes:
- Matrix cells read `row.points_by_id[m.id].total` (id lookup), so column headers from `sorted_matches` stay aligned with the right cell even though `breakdown` is built in unsorted `data["matches"]` order.
- The `Scoring` card is unchanged from the previous template except for a `max-width` wrapper (it previously sat in a `col-lg-5`; the layout is now stacked full-width).
- `match_number(m)` may return `None` for an unknown round; all seeded matches use known rounds so it returns M73–M104. The `title` uses `slot_label` which already resolves real team → origin code → placeholder → TBD.

- [ ] **Step 2: Run the route check (now green)**

Run: `source .venv/bin/activate && python "$SCRATCH/check_route.py"`
Expected: `OK`

- [ ] **Step 3: Manual load with real data**

Run: `source .venv/bin/activate && python -c "
from app import app
with app.test_client() as c:
    r = c.get('/leaderboard', follow_redirects=True)
    print(r.status_code)
    assert r.status_code == 200
    assert 'Points by match' in r.get_data(as_text=True)
    print('page OK')
"`
Expected: `200` then `page OK`.

- [ ] **Step 4: Commit**

```bash
git add templates/leaderboard.html
git commit -m "Leaderboard: per-round summary + full per-match points matrix

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 4: Spanish translation for the new string

**Files:**
- Modify: `translations.py` (add one entry to `SPANISH_TRANSLATIONS`)

**Interfaces:**
- Consumes: `translate()` lookup by English key.
- Produces: `"Points by match"` → Spanish. (All other strings on the page — `Leaderboard`, `Rank`, `Player`, `Score points`, `Advance points`, `Total`, `Scoring`, the tier rows, `No players yet.` — already exist in `SPANISH_TRANSLATIONS`.)

- [ ] **Step 1: Confirm which strings are missing (the check)**

Run:
```bash
source .venv/bin/activate && python -c "
from translations import SPANISH_TRANSLATIONS as S
needed = ['Leaderboard','Rank','Player','Total','Scoring','Score points','Advance points','No players yet.','Points by match']
missing = [k for k in needed if k not in S]
print('missing:', missing)
"
```
Expected: `missing: ['Points by match']`

- [ ] **Step 2: Add the entry**

In `translations.py`, locate the Spanish dict block near the leaderboard/scoring strings and add (place it beside the existing `"Score points"` / `"Advance points"` entries):

```python
    "Points by match": "Puntos por partido",
```

- [ ] **Step 3: Verify nothing is missing now**

Run the same command from Step 1.
Expected: `missing: []`

- [ ] **Step 4: Syntax gate**

Run: `python -m py_compile app.py translations.py`
Expected: no output (exit 0).

- [ ] **Step 5: Spanish render smoke check**

Run:
```bash
source .venv/bin/activate && python -c "
from app import app
with app.test_client() as c:
    c.get('/set-language/es')
    r = c.get('/leaderboard', follow_redirects=True)
    assert 'Puntos por partido' in r.get_data(as_text=True)
    print('ES OK')
"
```
Expected: `ES OK`

- [ ] **Step 6: Commit**

```bash
git add translations.py
git commit -m "i18n: Spanish for 'Points by match' leaderboard heading

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Self-Review

**Spec coverage:**
- §1 data-layer aggregates (`round_points`, `score_points`, `advance_points`, `points_by_id`) → Task 1. ✓
- §2 route passes `rounds` → Task 2. ✓
- §3a per-round summary table with kept Score/Advance columns → Task 3. ✓
- §3b full per-match matrix keyed by match id → Task 3 (`points_by_id[m.id]`). ✓
- §3c scoring card unchanged → Task 3. ✓
- i18n new string `Points by match` → Task 4; reuse of existing strings verified in Task 4 Step 1. ✓
- Testing/verification (py_compile + manual load + empty state) → covered across tasks; empty state via `{% else %}` colspan row and `{% if rows %}` guard on the matrix. ✓

**Placeholder scan:** No TBD/TODO; every code step shows complete code. ✓

**Type consistency:** `round_points` keyed by round string, `points_by_id` keyed by match id string, `score_points`/`advance_points` ints — used consistently in Task 3 template (`row.round_points[key]`, `row.points_by_id[m.id].total`, `row.score_points`, `row.advance_points`). Route `rounds` is `(key, label)` tuples, unpacked as `{% for key, label in rounds %}`. ✓

**Note for executor:** `$SCRATCH` = `/tmp/claude-1000/-home-yurif-WC-forecast/4f188714-86ce-4cc9-9769-5be6ce740faf/scratchpad`. The scratchpad check scripts are throwaway — do not `git add` them.
