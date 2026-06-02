# Bracket Simulator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a private, per-user `/simulator` page where a logged-in player picks Round-of-32 participants from group pools and then clicks winners round-by-round to visualize hypothetical match-ups — never scored, fully separate from real predictions.

**Architecture:** Reuse the existing `/bracket` winner-flow tree (CSS in `base.html`, `feeders()` mapping). Add a `simulations` key to `data.json` storing each user's R32 slot assignments + a winners map; R16→Final participants are derived from feeder winners (third-place = SF losers). Every action is a form POST (no custom JS) that mutates the sim, runs an integrity prune, saves, and redirects (PRG).

**Tech Stack:** Flask, Jinja2, Bootstrap 5.3 dark theme, JSON flat-file storage. No JS, no pytest — verify with `py_compile`, throwaway `python` assertion scripts, and a manual browser pass.

**Spec:** `docs/superpowers/specs/2026-06-02-bracket-simulator-design.md`

---

## File structure

- **Modify `app.py`** — add helpers `_sim_pool`, `_sim_participants`, `_prune_sim`, `_sim_view`; add `data.setdefault("simulations", {})` to `migrate_data`; add the `/simulator` route. (All sim logic lives beside the existing bracket helpers; consistent with the single-file design.)
- **Create `templates/simulator.html`** — interactive variant of `bracket.html` (selects for R32, click-to-pick winner buttons everywhere, reset button).
- **Modify `templates/base.html`** — one nav link to the simulator (logged-in block).
- **Modify `translations.py`** — Spanish for the new UI strings.

Throwaway test scripts are written under `/tmp/` and run with the venv Python; they are **not** committed (matches repo convention — no `tests/` dir exists).

---

### Task 1: `simulations` migration + `_sim_pool` helper

**Files:**
- Modify: `app.py` (in `migrate_data`, near `data.setdefault("predictions", {})` ~line 309; add `_sim_pool` right after `_origin_groups`/`team_options`, ~line 188)

- [ ] **Step 1: Write the failing test**

Write `/tmp/t1.py`:

```python
import os, tempfile
os.environ["DATA_DIR"] = tempfile.mkdtemp()
from app import migrate_data, _sim_pool, _seed_matches, GROUPS

# migrate seeds the simulations bucket
d = migrate_data({})
assert d["simulations"] == {}, d.get("simulations")

by_id = {m["id"]: m for m in _seed_matches()}

# R32 single-group origin "2A" -> Group A teams, sorted, deduped
pool = _sim_pool(by_id["r32-1"], "home")  # home_origin "2A"
assert pool == sorted(GROUPS["A"]), pool

# Multi-group "3rd A/B/C/D/F" origin -> union of those groups
pool2 = _sim_pool(by_id["r32-2"], "away")  # away_origin "3rd A/B/C/D/F"
expected = sorted({t for g in "ABCDF" for t in GROUPS[g]})
assert pool2 == expected, pool2

print("T1 OK")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python /tmp/t1.py`
Expected: FAIL — `ImportError: cannot import name '_sim_pool'` (and/or `simulations` KeyError).

- [ ] **Step 3: Implement**

In `app.py`, inside `migrate_data`, next to the other `setdefault` calls (after `data.setdefault("predictions", {})`):

```python
    data.setdefault("simulations", {})
```

Add this helper immediately after the `team_options` function (just before `_MATCH_NO_BASE`):

```python
def _sim_pool(match, side):
    """Candidate teams for one Round-of-32 slot in the simulator: every nation in
    the slot's origin group(s), sorted and de-duplicated. Falls back to all 48
    teams if the origin is unparseable. R16+ slots have no pool (return [])."""
    if match.get("round") != "r32":
        return []
    origin = match.get(f"{side}_origin")
    teams = sorted({t for g in _origin_groups(origin) for t in GROUPS[g]})
    return teams or ALL_TEAMS
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python /tmp/t1.py`
Expected: `T1 OK`

- [ ] **Step 5: Compile check + commit**

```bash
python -m py_compile app.py
git add app.py
git commit -m "Simulator: seed simulations bucket + R32 slot pool helper"
```

---

### Task 2: `_sim_participants` helper

Resolves the two teams of any simulator match: R32 from stored slots, R16+ from feeder winners, third-place from SF losers.

**Files:**
- Modify: `app.py` (add after `_sim_pool`)

- [ ] **Step 1: Write the failing test**

Write `/tmp/t2.py`:

```python
import os, tempfile
os.environ["DATA_DIR"] = tempfile.mkdtemp()
from app import _sim_participants, _seed_matches

by_id = {m["id"]: m for m in _seed_matches()}

# R32: participants come straight from the stored slot
sim = {"r32": {"r32-1": {"home": "Mexico", "away": "Canada"}}, "winners": {}}
assert _sim_participants(sim, by_id["r32-1"], by_id) == ("Mexico", "Canada")

# R32 slot unset -> (None, None)
assert _sim_participants(sim, by_id["r32-3"], by_id) == (None, None)

# R16-1 is fed by r32-1 and r32-2: participants = their winners
sim["r32"]["r32-2"] = {"home": "Germany", "away": "Ecuador"}
sim["winners"] = {"r32-1": "Mexico", "r32-2": "Germany"}
assert _sim_participants(sim, by_id["r16-1"], by_id) == ("Mexico", "Germany")

# R16-1 with only one feeder winner -> that side resolved, other None
sim["winners"] = {"r32-1": "Mexico"}
assert _sim_participants(sim, by_id["r16-1"], by_id) == ("Mexico", None)

print("T2 OK")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python /tmp/t2.py`
Expected: FAIL — `ImportError: cannot import name '_sim_participants'`.

- [ ] **Step 3: Implement**

Add after `_sim_pool` in `app.py`:

```python
def _sim_participants(sim, match, by_id):
    """Return (home, away) team names for a simulator match; either may be None when
    undecided. R32: from the user's stored slot. R16+: the winner of each feeder
    match. Third-place: the LOSER of each feeding semifinal (the participant that is
    not that SF's winner). Pure-ish: reads sim + by_id, no app context needed."""
    rnd = match.get("round")
    if rnd == "r32":
        slot = sim.get("r32", {}).get(match["id"], {})
        return (slot.get("home"), slot.get("away"))
    f = feeders(match)
    if not f:
        return (None, None)
    word, top, bot = f
    winners = sim.get("winners", {})

    def resolve(feeder_id):
        feeder = by_id.get(feeder_id)
        if not feeder:
            return None
        win = winners.get(feeder_id)
        if not win:
            return None
        if word == "Loser":
            ph, pa = _sim_participants(sim, feeder, by_id)
            others = [t for t in (ph, pa) if t and t != win]
            return others[0] if others else None
        return win

    return (resolve(top), resolve(bot))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python /tmp/t2.py`
Expected: `T2 OK`

- [ ] **Step 5: Compile check + commit**

```bash
python -m py_compile app.py
git add app.py
git commit -m "Simulator: resolve match participants from slots/feeder winners"
```

---

### Task 3: `_prune_sim` integrity pass

After any mutation, drop winners that are no longer valid participants — cascading through dependent rounds.

**Files:**
- Modify: `app.py` (add after `_sim_participants`)

- [ ] **Step 1: Write the failing test**

Write `/tmp/t3.py`:

```python
import os, tempfile
os.environ["DATA_DIR"] = tempfile.mkdtemp()
from app import _prune_sim

# Valid chain: r32-1 won by Mexico, r16-1 won by Mexico (a valid r16-1 participant)
sim = {
    "r32": {"r32-1": {"home": "Mexico", "away": "Czechia"},
            "r32-2": {"home": "Germany", "away": "Ecuador"}},
    "winners": {"r32-1": "Mexico", "r32-2": "Germany", "r16-1": "Mexico"},
}
_prune_sim(sim)
assert sim["winners"] == {"r32-1": "Mexico", "r32-2": "Germany", "r16-1": "Mexico"}, sim["winners"]

# Reassign r32-1 so Mexico is no longer a participant -> r32-1 winner invalid,
# which cascades: r16-1's Mexico winner is also pruned.
sim["r32"]["r32-1"] = {"home": "Czechia", "away": "South Korea"}
_prune_sim(sim)
assert "r32-1" not in sim["winners"], sim["winners"]
assert "r16-1" not in sim["winners"], sim["winners"]
assert sim["winners"] == {"r32-2": "Germany"}, sim["winners"]

print("T3 OK")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python /tmp/t3.py`
Expected: FAIL — `ImportError: cannot import name '_prune_sim'`.

- [ ] **Step 3: Implement**

Add after `_sim_participants` in `app.py`:

```python
def _prune_sim(sim):
    """Drop any stored winner that is no longer one of its match's current
    participants, walking rounds in dependency order (r32 → final, then third) so
    invalidations cascade downstream. Mutates sim in place; returns it."""
    by_id = {m["id"]: m for m in _seed_matches()}  # structural map (round + feeders)
    winners = sim.setdefault("winners", {})
    for rnd in ("r32", "r16", "qf", "sf", "final", "third"):
        for mid, match in by_id.items():
            if match.get("round") != rnd:
                continue
            win = winners.get(mid)
            if win is None:
                continue
            home, away = _sim_participants(sim, match, by_id)
            if win not in (home, away):
                del winners[mid]
    return sim
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python /tmp/t3.py`
Expected: `T3 OK`

- [ ] **Step 5: Compile check + commit**

```bash
python -m py_compile app.py
git add app.py
git commit -m "Simulator: prune downstream winners when upstream picks change"
```

---

### Task 4: `_sim_view` display helper

Build the per-match display dict the template consumes.

**Files:**
- Modify: `app.py` (add after `_prune_sim`)

- [ ] **Step 1: Write the failing test**

Write `/tmp/t4.py`:

```python
import os, tempfile
os.environ["DATA_DIR"] = tempfile.mkdtemp()
from app import app, _sim_view, _seed_matches

by_id = {m["id"]: m for m in _seed_matches()}
sim = {"r32": {"r32-1": {"home": "Mexico", "away": "Canada"}},
       "winners": {"r32-1": "Mexico"}}

with app.test_request_context("/"):   # feed_label_pair/translate need app context
    # R32 with teams set
    v = _sim_view(sim, by_id["r32-1"], by_id)
    assert v["sim_home"] == "Mexico" and v["sim_away"] == "Canada"
    assert v["home_display"] == "Mexico" and v["away_display"] == "Canada"
    assert v["winner"] == "Mexico"
    assert v["home_pool"] and v["away_pool"]          # selectable pools present

    # R16-1 undecided away side -> placeholder feed label, no pools
    v16 = _sim_view(sim, by_id["r16-1"], by_id)
    assert v16["sim_home"] == "Mexico"
    assert v16["sim_away"] is None
    assert "R32-2" in v16["away_display"]             # "Winner R32-2"
    assert v16["home_pool"] == [] and v16["away_pool"] == []

print("T4 OK")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python /tmp/t4.py`
Expected: FAIL — `ImportError: cannot import name '_sim_view'`.

- [ ] **Step 3: Implement**

Add after `_prune_sim` in `app.py`:

```python
def _sim_view(sim, match, by_id):
    """Display fields for one simulator match: resolved participants, the label to
    show in each slot (team → R32 origin code → feed placeholder → 'TBD'), the
    current winner, and the R32 selectable pools (empty for R16+)."""
    home, away = _sim_participants(sim, match, by_id)
    top_lbl, bot_lbl = feed_label_pair(match)
    is_r32 = match.get("round") == "r32"

    def label(team, origin, feed):
        if team:
            return team
        if is_r32 and origin:
            return origin
        return feed or translate("TBD")

    return {
        **match,
        "sim_home": home,
        "sim_away": away,
        "home_display": label(home, match.get("home_origin"), top_lbl),
        "away_display": label(away, match.get("away_origin"), bot_lbl),
        "winner": sim.get("winners", {}).get(match["id"]),
        "home_pool": _sim_pool(match, "home"),
        "away_pool": _sim_pool(match, "away"),
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python /tmp/t4.py`
Expected: `T4 OK`

- [ ] **Step 5: Compile check + commit**

```bash
python -m py_compile app.py
git add app.py
git commit -m "Simulator: per-match display helper for the template"
```

---

### Task 5: `/simulator` route

GET renders the tree; POST handles `set_teams`, `pick_winner`, `reset`; PRG redirect.

**Files:**
- Modify: `app.py` (add the route right after the existing `bracket()` route, ~line 750)

- [ ] **Step 1: Write the failing test**

Write `/tmp/t5.py`:

```python
import os, tempfile
os.environ["DATA_DIR"] = tempfile.mkdtemp()
from app import app, load_data

app.config["TESTING"] = True
app.secret_key = app.secret_key or "test"
client = app.test_client()

# Logged-out -> redirect to home
assert client.get("/simulator").status_code == 302

with client.session_transaction() as s:
    s["username"] = "tester"

# GET renders
r = client.get("/simulator")
assert r.status_code == 200, r.status_code
assert b"Simulator" in r.data

# set_teams persists an R32 slot
client.post("/simulator", data={"action": "set_teams", "match_id": "r32-1",
                                "home": "Mexico", "away": "Czechia"})
sim = load_data()["simulations"]["tester"]
assert sim["r32"]["r32-1"] == {"home": "Mexico", "away": "Czechia"}, sim["r32"]

# pick_winner records a valid winner
client.post("/simulator", data={"action": "pick_winner", "match_id": "r32-1",
                                "team": "Mexico"})
assert load_data()["simulations"]["tester"]["winners"]["r32-1"] == "Mexico"

# pick_winner with a team not in the match is rejected
client.post("/simulator", data={"action": "pick_winner", "match_id": "r32-1",
                                "team": "Brazil"})
assert load_data()["simulations"]["tester"]["winners"]["r32-1"] == "Mexico"

# reset clears everything
client.post("/simulator", data={"action": "reset"})
sim = load_data()["simulations"]["tester"]
assert sim == {"r32": {}, "winners": {}}, sim

print("T5 OK")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python /tmp/t5.py`
Expected: FAIL — 404 on `/simulator` (route missing) → assertion error on first GET.

- [ ] **Step 3: Implement**

Add after the `bracket()` route in `app.py`:

```python
@app.route("/simulator", methods=["GET", "POST"])
def simulator():
    if not login_required():
        return redirect(url_for("home"))
    data = load_data()
    username = session["username"]
    sims = data.setdefault("simulations", {})
    sim = sims.setdefault(username, {"r32": {}, "winners": {}})
    sim.setdefault("r32", {})
    sim.setdefault("winners", {})
    by_id = {m["id"]: m for m in data["matches"]}

    if request.method == "POST":
        action = request.form.get("action")
        if action == "reset":
            sims[username] = {"r32": {}, "winners": {}}
            flash(translate("Simulator reset."), "info")
        elif action == "set_teams":
            match = by_id.get(request.form.get("match_id"))
            if match and match.get("round") == "r32":
                home = request.form.get("home") or None
                away = request.form.get("away") or None
                if home and home not in _sim_pool(match, "home"):
                    home = None
                if away and away not in _sim_pool(match, "away"):
                    away = None
                sim["r32"][match["id"]] = {"home": home, "away": away}
                _prune_sim(sim)
            else:
                flash(translate("Invalid match."), "danger")
        elif action == "pick_winner":
            match = by_id.get(request.form.get("match_id"))
            team = request.form.get("team")
            if match:
                home, away = _sim_participants(sim, match, by_id)
                if team and team in (home, away):
                    sim["winners"][match["id"]] = team
                    _prune_sim(sim)
                else:
                    flash(translate("Pick a valid team for that match."), "warning")
        save_data(data)
        return redirect(url_for("simulator"))

    tree_order = ["r32", "r16", "qf", "sf", "final"]
    columns = []
    for rnd in tree_order:
        rnd_matches = sorted_matches([m for m in data["matches"] if m.get("round") == rnd])
        columns.append({"round": rnd, "matches": [_sim_view(sim, m, by_id) for m in rnd_matches]})
    third_match = next((m for m in data["matches"] if m.get("round") == "third"), None)
    third = _sim_view(sim, third_match, by_id) if third_match else None
    return render_template("simulator.html", columns=columns, third=third)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python /tmp/t5.py`
Expected: `T5 OK`

(The test asserts `b"Simulator" in r.data`; that string is rendered by the template built in Task 6. Until then this specific assertion fails even though the route works — implement Task 6 before re-running Step 4, or temporarily confirm the route with the non-render assertions. The committed code for this task is the route only.)

- [ ] **Step 5: Compile check + commit**

```bash
python -m py_compile app.py
git add app.py
git commit -m "Simulator: /simulator route (set teams, pick winner, reset)"
```

---

### Task 6: `simulator.html` template

**Files:**
- Create: `templates/simulator.html`

- [ ] **Step 1: Create the template**

Create `templates/simulator.html`:

```jinja
{% extends "base.html" %}

{% macro slot_btn(m, side) %}
  {% set team = m.sim_home if side == 'home' else m.sim_away %}
  {% set label = m.home_display if side == 'home' else m.away_display %}
  {% if team %}
  <form method="post" class="d-grid">
    <input type="hidden" name="action" value="pick_winner">
    <input type="hidden" name="match_id" value="{{ m.id }}">
    <input type="hidden" name="team" value="{{ team }}">
    <button type="submit" class="btn btn-sm text-start py-0 px-1 bracket-slot
      {{ 'fw-bold accent' if m.winner == team else 'btn-link text-decoration-none p-0' }}">
      {{ team }}{% if m.winner == team %} ✓{% endif %}
    </button>
  </form>
  {% else %}
  <div class="bracket-slot text-muted fst-italic">{{ label }}</div>
  {% endif %}
{% endmacro %}

{% macro sim_card(m, show_champion=false) %}
<div class="card">
  <div class="card-body p-2 small">
    {% if match_number(m) is not none %}<div class="accent fw-bold">M{{ match_number(m) }}</div>{% endif %}
    {% if m.round == 'r32' %}
    <form method="post" class="d-flex flex-column gap-1 mb-1">
      <input type="hidden" name="action" value="set_teams">
      <input type="hidden" name="match_id" value="{{ m.id }}">
      <select name="home" class="form-select form-select-sm">
        <option value="">{{ m.home_origin or _("TBD") }}</option>
        {% for t in m.home_pool %}<option value="{{ t }}"{{ ' selected' if t == m.sim_home }}>{{ t }}</option>{% endfor %}
      </select>
      <select name="away" class="form-select form-select-sm">
        <option value="">{{ m.away_origin or _("TBD") }}</option>
        {% for t in m.away_pool %}<option value="{{ t }}"{{ ' selected' if t == m.sim_away }}>{{ t }}</option>{% endfor %}
      </select>
      <button class="btn btn-sm btn-outline-light py-0" type="submit">{{ _("Set teams") }}</button>
    </form>
    {% endif %}
    {{ slot_btn(m, 'home') }}
    {{ slot_btn(m, 'away') }}
    {% if show_champion and m.winner %}
    <div class="text-center mt-1">🏆 <span class="accent">{{ _("Champion") }}: {{ m.winner }}</span></div>
    {% endif %}
  </div>
</div>
{% endmacro %}

{% block content %}
<div class="d-flex justify-content-between align-items-center mb-3 flex-wrap gap-2">
  <h3 class="mb-0">{{ _("Bracket Simulator") }}</h3>
  <form method="post">
    <input type="hidden" name="action" value="reset">
    <button class="btn btn-sm btn-outline-danger" type="submit">{{ _("Reset simulator") }}</button>
  </form>
</div>
<p class="text-muted small">{{ _("Pick teams and winners to explore possible match-ups. This is just a sandbox — it is not scored and does not affect your predictions.") }}</p>

<div class="bracket">
  {% for col in columns %}
  {% set is_feeder = col.round in ['r32', 'r16', 'qf', 'sf'] %}
  <div class="round round-{{ col.round }}">
    <h6 class="accent text-center mb-3">{{ round_label(col.round) }}</h6>
    {% for m in col.matches %}
    <div class="bracket-match{% if is_feeder %}{{ ' feeder-top' if loop.index is odd else ' feeder-bottom' }}{% endif %}">
      {{ sim_card(m, show_champion=(col.round == 'final')) }}
    </div>
    {% endfor %}
  </div>
  {% endfor %}
</div>

{% if third %}
<div class="third-place mt-4">
  <h6 class="accent">{{ round_label('third') }}</h6>
  <div style="max-width:210px">{{ sim_card(third) }}</div>
</div>
{% endif %}
{% endblock %}
```

- [ ] **Step 2: Re-run the route test (now expects the rendered string)**

Run: `.venv/bin/python /tmp/t5.py`
Expected: `T5 OK` (the `b"Simulator" in r.data` assertion now passes — "Bracket Simulator" heading renders).

- [ ] **Step 3: Commit**

```bash
git add templates/simulator.html
git commit -m "Simulator: interactive bracket template (selects + winner buttons)"
```

---

### Task 7: Nav link

**Files:**
- Modify: `templates/base.html:63-65` (inside the logged-in `{% if session.get('username') %}` block that wraps Admin)

`/simulator` requires login, so the link must sit inside a logged-in block. The Admin item at lines 63–65 is already wrapped in `{% if session.get('username') %} … {% endif %}`; add the Simulator item just before Admin, inside that same block.

- [ ] **Step 1: Add the link**

In `templates/base.html`, change the Admin block (lines 63–65) from:

```html
          {% if session.get('username') %}
          <li class="nav-item"><a class="nav-link" href="{{ url_for('admin') }}">{{ _("Admin") }}</a></li>
          {% endif %}
```

to:

```html
          {% if session.get('username') %}
          <li class="nav-item"><a class="nav-link" href="{{ url_for('simulator') }}">{{ _("Simulator") }}</a></li>
          <li class="nav-item"><a class="nav-link" href="{{ url_for('admin') }}">{{ _("Admin") }}</a></li>
          {% endif %}
```

- [ ] **Step 2: Verify it renders for a logged-in user**

Write `/tmp/t7.py`:

```python
import os, tempfile
os.environ["DATA_DIR"] = tempfile.mkdtemp()
from app import app
app.secret_key = app.secret_key or "test"
client = app.test_client()
with client.session_transaction() as s:
    s["username"] = "tester"
r = client.get("/dashboard")
assert b'href="/simulator"' in r.data, "nav link missing"
print("T7 OK")
```

Run: `.venv/bin/python /tmp/t7.py`
Expected: `T7 OK`

- [ ] **Step 3: Commit**

```bash
git add templates/base.html
git commit -m "Simulator: add nav link"
```

---

### Task 8: Spanish translations

**Files:**
- Modify: `translations.py` (add entries to `SPANISH_TRANSLATIONS`)

- [ ] **Step 1: Add the strings**

Add to the `SPANISH_TRANSLATIONS` dict in `translations.py` (a "Simulator" comment block is fine):

```python
    # Simulator
    "Simulator": "Simulador",
    "Bracket Simulator": "Simulador de Cuadro",
    "Reset simulator": "Reiniciar simulador",
    "Simulator reset.": "Simulador reiniciado.",
    "Set teams": "Definir equipos",
    "Pick a valid team for that match.": "Elige un equipo válido para ese partido.",
    "Invalid match.": "Partido inválido.",
    "Pick teams and winners to explore possible match-ups. This is just a sandbox — it is not scored and does not affect your predictions.": "Elige equipos y ganadores para explorar posibles enfrentamientos. Es solo una zona de práctica: no cuenta para los puntos ni afecta tus pronósticos.",
```

(`Champion`, `TBD`, and `round_label` strings already exist in `translations.py` and are reused.)

- [ ] **Step 2: Verify ES renders with no missing keys**

Write `/tmp/t8.py`:

```python
import os, tempfile
os.environ["DATA_DIR"] = tempfile.mkdtemp()
from app import app
app.secret_key = app.secret_key or "test"
client = app.test_client()
with client.session_transaction() as s:
    s["username"] = "tester"
    s["lang"] = "es"
r = client.get("/simulator")
assert r.status_code == 200
assert "Simulador de Cuadro".encode() in r.data, "ES heading missing"
assert "Reiniciar simulador".encode() in r.data
print("T8 OK")
```

Run: `.venv/bin/python /tmp/t8.py`
Expected: `T8 OK`

- [ ] **Step 3: Compile check + commit**

```bash
python -m py_compile translations.py
git add translations.py
git commit -m "Simulator: Spanish translations"
```

---

### Task 9: Manual browser verification

Automated tests don't cover the full visual tree, the third-place (SF-loser) flow, or connector alignment. Verify by hand.

**Files:** none (verification only)

- [ ] **Step 1: Start the dev server**

Run: `.venv/bin/python app.py` (serves on http://localhost:5000)

- [ ] **Step 2: Register/log in, open the Simulator**

- Log in (or register a user), click **Simulator** in the nav.
- Confirm: heading "Bracket Simulator", the sandbox disclaimer, a "Reset simulator" button, and 16 R32 cards each with two dropdowns + "Set teams".

- [ ] **Step 3: Drive a full champion path**

- In several R32 matches, pick two teams from the dropdowns and "Set teams".
- Click a team in each to set the winner; confirm it shows ✓ + bold accent and **flows into the R16 slot** on reload.
- Advance one path all the way to **final-1**; confirm "🏆 Champion: <team>" renders.
- Confirm the **Third-place** card shows the two **SF losers** as its participants once both semifinals have winners, and you can pick a third-place winner.

- [ ] **Step 4: Verify auto-prune**

- After advancing a team several rounds, go back to its R32 match and reassign the dropdowns so that team is no longer a participant; "Set teams".
- Confirm every downstream winner that depended on it is cleared (slots revert to "Winner R32-x" placeholders / empty).

- [ ] **Step 5: Verify reset + isolation from predictions**

- Click "Reset simulator"; confirm all slots clear and the info flash shows.
- Open `/bracket` and `/dashboard`; confirm the real bracket and predictions are unchanged (simulator never touched them).
- Visual: connectors/tree roughly align. R32 cards are taller (they hold selects) but are equal-height to each other, so within-column spacing is even. If cross-column elbows look noticeably broken, note it — minor CSS tweaks to `.round-r32 .bracket-match` spacing are acceptable follow-up, not a blocker.

- [ ] **Step 6: Final compile check**

Run: `python -m py_compile app.py translations.py`
Expected: clean (no output).

- [ ] **Step 7: Clean up scratch tests**

```bash
rm -f /tmp/t1.py /tmp/t2.py /tmp/t3.py /tmp/t4.py /tmp/t5.py /tmp/t7.py /tmp/t8.py
```

No commit needed (scratch files were never tracked). Confirm `git status` is clean and `data.json` is not staged.

---

## Self-review notes

- **Spec coverage:** placement/nav (T5,T7) · per-user `simulations` model (T1,T5) · R32 pools from groups (T1) · derived R16+ participants + SF-loser third place (T2,T9) · winners map (T5) · click-to-advance no-JS forms (T6) · auto-prune cascade (T3,T9) · reset (T5,T9) · i18n EN+ES (T6,T8) · separate from predictions/no scoring (T9). All covered.
- **Type consistency:** sim shape `{"r32": {id: {"home","away"}}, "winners": {id: team}}` is identical across T1–T8. Helper names — `_sim_pool`, `_sim_participants`, `_prune_sim`, `_sim_view` — used consistently. View keys (`sim_home`, `sim_away`, `home_display`, `away_display`, `winner`, `home_pool`, `away_pool`) match between T4 and the T6 template.
- **No placeholders:** every code/test step contains full content.
- **Known caveat (documented, not a gap):** the same team may be selected into two R32 slots — intentional per spec (sandbox); not validated against.
