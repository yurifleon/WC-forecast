# Shareable Simulation Link Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a "Save & share" action to `/simulator` that freezes the user's bracket into a token-addressed snapshot, viewable by anyone at `/s/<token>` without login, auto-expiring 7 days after creation, with an owner-facing list of active links and a revoke button.

**Architecture:** Snapshots live under a new top-level `data["shared_sims"]` key in the existing JSON flat file, keyed by a random `secrets.token_urlsafe(8)` token. Snapshots are deep-copied and frozen (never pruned). Expiry is lazy: `_purge_expired_shares()` runs on the two routes that already write (`/simulator` load and the `/s/` route when it hits an expired token). The read-only view reuses `_sim_view()` over the frozen sim and the existing bracket-tree CSS.

**Tech Stack:** Python 3.12 / Flask, Jinja2 + Bootstrap 5.3 (no custom JS), `data.json` flat file. Spec: `docs/superpowers/specs/2026-06-04-shareable-simulation-link-design.md`.

**Testing note:** This repo has no pytest suite (CLAUDE.md). We drive helper development with a **scratch** assertion file `test_share.py` run via `python test_share.py` (exit non-zero on failure), and verify routes with `py_compile` + a manual `curl` round-trip. The scratch file is **not committed** and is deleted in the final task — matching the project's "no test suite" convention.

**Environment:** Activate the venv first in every shell: `source .venv/bin/activate`. Use `python` (not `python3`).

---

### Task 1: Data model — `shared_sims` key, `timedelta` import, constants

**Files:**
- Modify: `app.py` (import line ~19; constants near `MAX_USERS`; `migrate_data` setdefault block ~line 395)

- [ ] **Step 1: Add `timedelta` to the datetime import**

Find:
```python
from datetime import datetime, timezone
```
Replace with:
```python
from datetime import datetime, timedelta, timezone
```

- [ ] **Step 2: Add share constants**

Find the `MAX_USERS` definition (search `MAX_USERS`). Immediately after that line, add:
```python
SHARE_TTL_DAYS = 7            # a shared simulation snapshot lives this long
MAX_SHARES_PER_USER = 10      # cap active shared links per user
```

- [ ] **Step 3: Seed `shared_sims` in `migrate_data`**

Find:
```python
    data.setdefault("simulations", {})
```
Add directly below it:
```python
    data.setdefault("shared_sims", {})
```

- [ ] **Step 4: Verify it compiles and the key seeds**

Run:
```bash
source .venv/bin/activate && python -m py_compile app.py && \
python -c "from app import migrate_data; d=migrate_data({}); print('shared_sims' in d, d['shared_sims'])"
```
Expected: `True {}`

- [ ] **Step 5: Commit**

```bash
git add app.py
git commit -m "Simulator share: seed shared_sims key + TTL/cap constants"
```

---

### Task 2: Share helpers (`_share_days_left`, `_purge_expired_shares`, `_create_share`, `_user_shares`)

**Files:**
- Modify: `app.py` (add the four helpers next to the other `_sim_*` helpers, e.g. just after `_prune_sim`)
- Test (scratch, not committed): `test_share.py`

- [ ] **Step 1: Write the failing scratch test**

Create `test_share.py`:
```python
"""Scratch tests for shared-simulation helpers. Run: python test_share.py"""
from datetime import datetime, timedelta, timezone
import app

NOW = datetime(2026, 6, 4, 18, 0, tzinfo=timezone.utc)


def test_days_left_ceil_and_expiry():
    plus3 = (NOW + timedelta(days=2, hours=1)).isoformat()
    assert app._share_days_left(plus3, NOW) == 3, "2d1h left rounds up to 3"
    assert app._share_days_left((NOW - timedelta(hours=1)).isoformat(), NOW) == 0
    assert app._share_days_left("not-a-date", NOW) == 0
    assert app._share_days_left(None, NOW) == 0


def test_create_share_freezes_a_deep_copy():
    data = {"shared_sims": {}}
    sim = {"r32": {"r32-1": {"home": "Brazil", "away": "Mexico"}}, "winners": {"r32-1": "Brazil"}}
    token = app._create_share(data, "yuri", sim, NOW)
    snap = data["shared_sims"][token]
    assert snap["owner"] == "yuri"
    assert snap["sim"]["winners"]["r32-1"] == "Brazil"
    # mutating the live sim must NOT change the frozen snapshot
    sim["winners"]["r32-1"] = "Mexico"
    sim["r32"]["r32-1"]["home"] = "Spain"
    assert snap["sim"]["winners"]["r32-1"] == "Brazil"
    assert snap["sim"]["r32"]["r32-1"]["home"] == "Brazil"
    # expiry is created + 7 days
    assert snap["expires_utc"] == (NOW + timedelta(days=7)).isoformat()


def test_user_shares_lists_only_own_active_newest_first():
    data = {"shared_sims": {}}
    sim = {"r32": {"r32-1": {"home": "Brazil", "away": "Mexico"}}, "winners": {}}
    t_old = app._create_share(data, "yuri", sim, NOW - timedelta(days=1))
    t_new = app._create_share(data, "yuri", sim, NOW)
    app._create_share(data, "ana", sim, NOW)                      # other owner
    # an expired one for yuri:
    expired = app._create_share(data, "yuri", sim, NOW - timedelta(days=8))
    rows = app._user_shares(data, "yuri", NOW)
    tokens = [r["token"] for r in rows]
    assert tokens == [t_new, t_old], f"newest first, own+active only: {tokens}"
    assert all(r["days_left"] >= 1 for r in rows)
    assert expired not in tokens


def test_purge_expired_removes_only_dead():
    data = {"shared_sims": {}}
    sim = {"r32": {}, "winners": {}}
    live = app._create_share(data, "yuri", sim, NOW)
    dead = app._create_share(data, "yuri", sim, NOW - timedelta(days=8))
    changed = app._purge_expired_shares(data, NOW)
    assert changed is True
    assert live in data["shared_sims"] and dead not in data["shared_sims"]
    assert app._purge_expired_shares(data, NOW) is False, "no-op second pass"


if __name__ == "__main__":
    fails = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn(); print(f"PASS {name}")
            except Exception as e:
                fails += 1; print(f"FAIL {name}: {type(e).__name__}: {e}")
    raise SystemExit(fails)
```

- [ ] **Step 2: Run it to confirm it fails**

Run: `source .venv/bin/activate && python test_share.py`
Expected: FAILs with `AttributeError: module 'app' has no attribute '_share_days_left'` (helpers not defined yet).

- [ ] **Step 3: Implement the four helpers**

In `app.py`, directly after the `_prune_sim` function, add:
```python
def _share_days_left(expires_utc, now):
    """Whole days until a snapshot expires, rounded UP (6d2h -> 7). Returns 0 when
    already expired or the timestamp is unparseable (fail-closed, so callers treat
    0 as 'expired')."""
    try:
        exp = datetime.fromisoformat(expires_utc)
    except (TypeError, ValueError):
        return 0
    if exp.tzinfo is None:
        exp = exp.replace(tzinfo=timezone.utc)
    secs = (exp - now).total_seconds()
    if secs <= 0:
        return 0
    return int((secs + 86399) // 86400)  # ceil to whole days


def _purge_expired_shares(data, now):
    """Delete every shared snapshot whose TTL has elapsed. Returns True if anything
    was removed (so the caller can decide whether to save_data)."""
    shares = data.setdefault("shared_sims", {})
    dead = [t for t, s in shares.items() if _share_days_left(s.get("expires_utc"), now) == 0]
    for t in dead:
        del shares[t]
    return bool(dead)


def _create_share(data, username, sim, now):
    """Freeze `sim` into a new token-addressed snapshot owned by `username`, valid for
    SHARE_TTL_DAYS. The sim is deep-copied so later edits to the live sim never leak
    into the snapshot. Returns the new token."""
    shares = data.setdefault("shared_sims", {})
    token = secrets.token_urlsafe(8)
    while token in shares:
        token = secrets.token_urlsafe(8)
    shares[token] = {
        "owner": username,
        "created_utc": now.isoformat(),
        "expires_utc": (now + timedelta(days=SHARE_TTL_DAYS)).isoformat(),
        "sim": {
            "r32": {mid: dict(slot) for mid, slot in sim.get("r32", {}).items()},
            "winners": dict(sim.get("winners", {})),
        },
    }
    return token


def _user_shares(data, username, now):
    """Active (non-expired) snapshots owned by `username`, newest first. Each row is
    {token, days_left, created_utc} for the template (which builds the URL)."""
    rows = []
    for token, s in data.get("shared_sims", {}).items():
        if s.get("owner") != username:
            continue
        days = _share_days_left(s.get("expires_utc"), now)
        if days == 0:
            continue
        rows.append({"token": token, "days_left": days, "created_utc": s.get("created_utc", "")})
    rows.sort(key=lambda r: r["created_utc"], reverse=True)
    return rows
```

- [ ] **Step 4: Run the scratch test to confirm it passes**

Run: `source .venv/bin/activate && python test_share.py`
Expected: all four `PASS`, exit 0.

- [ ] **Step 5: Commit (impl only — not the scratch test)**

```bash
git add app.py
git commit -m "Simulator share: add snapshot helpers (create/list/purge/days-left)"
```

---

### Task 3: Public read-only route `GET /s/<token>` + templates

**Files:**
- Modify: `app.py` (new route; place after the `simulator` route)
- Create: `templates/shared.html`
- Create: `templates/shared_missing.html`

- [ ] **Step 1: Create the read-only template `templates/shared.html`**

```jinja
{% extends "base.html" %}

{% macro ro_slot(m, side) %}
  {% set team = m.sim_home if side == 'home' else m.sim_away %}
  {% set label = m.home_display if side == 'home' else m.away_display %}
  {% if team %}
  <div class="bracket-slot px-1 {{ 'fw-bold accent' if m.winner == team else 'team-pick' }}">
    {{ team }}{% if m.winner == team %} ✓{% endif %}
  </div>
  {% else %}
  <div class="bracket-slot text-muted fst-italic px-1">{{ label }}</div>
  {% endif %}
{% endmacro %}

{% macro ro_card(m, show_champion=false) %}
<div class="card">
  <div class="card-body p-2 small">
    <div class="accent fw-bold">{% if match_number(m) is not none %}M{{ match_number(m) }}{% endif %}{% if m.venue %}{% if match_number(m) is not none %} · {% endif %}{{ m.venue }}{% endif %}</div>
    {% if m.kickoff_utc %}<div class="small text-muted">{{ m.kickoff_utc | deadline_tz }}</div>{% endif %}
    {{ ro_slot(m, 'home') }}
    {{ ro_slot(m, 'away') }}
    {% if show_champion and m.winner %}
    <div class="text-center mt-1">🏆 <span class="accent">{{ _("Champion") }}: {{ m.winner }}</span></div>
    {% endif %}
  </div>
</div>
{% endmacro %}

{% block content %}
<div class="mb-3">
  <h3 class="mb-0">{{ _("Bracket Simulator") }}</h3>
  <div class="text-muted small">{{ _("Shared by {user}", user=owner) }} · {{ _("Expires in {n} days", n=days_left) }}</div>
</div>

<div class="bracket">
  {% for col in columns %}
  {% set is_feeder = col.round in ['r32', 'r16', 'qf', 'sf'] %}
  <div class="round round-{{ col.round }}">
    <h6 class="accent text-center mb-3">{{ round_label(col.round) }}</h6>
    {% for m in col.matches %}
    <div class="bracket-match{% if is_feeder %}{{ ' feeder-top' if loop.index is odd else ' feeder-bottom' }}{% endif %}">
      {{ ro_card(m, show_champion=(col.round == 'final')) }}
    </div>
    {% endfor %}
  </div>
  {% endfor %}
</div>

{% if third %}
<div class="third-place mt-4">
  <h6 class="accent">{{ round_label('third') }}</h6>
  <div style="max-width:210px">{{ ro_card(third) }}</div>
</div>
{% endif %}
{% endblock %}
```

- [ ] **Step 2: Create the not-found/expired template `templates/shared_missing.html`**

```jinja
{% extends "base.html" %}
{% block content %}
<div class="text-center my-5">
  <h4>{{ _("This shared bracket has expired or doesn't exist.") }}</h4>
  <a class="btn btn-sm btn-outline-light mt-3" href="{{ url_for('home') }}">{{ _("WC Forecast") }}</a>
</div>
{% endblock %}
```

- [ ] **Step 3: Add the `shared_view` route in `app.py`**

Directly after the `simulator()` route function, add:
```python
@app.route("/s/<token>")
def shared_view(token):
    data = load_data()
    now = get_cached_time()
    share = data.get("shared_sims", {}).get(token)
    expired = share is not None and _share_days_left(share.get("expires_utc"), now) == 0
    if share is None or expired:
        if expired:
            data["shared_sims"].pop(token, None)
            save_data(data)
        return render_template("shared_missing.html"), 404

    sim = share["sim"]
    by_id = {m["id"]: m for m in data["matches"]}
    tree_order = ["r32", "r16", "qf", "sf", "final"]
    columns = []
    for rnd in tree_order:
        rnd_matches = sorted_matches([m for m in data["matches"] if m.get("round") == rnd])
        columns.append({"round": rnd, "matches": [_sim_view(sim, m, by_id) for m in rnd_matches]})
    third_match = next((m for m in data["matches"] if m.get("round") == "third"), None)
    third = _sim_view(sim, third_match, by_id) if third_match else None
    return render_template(
        "shared.html",
        columns=columns,
        third=third,
        owner=share["owner"],
        days_left=_share_days_left(share["expires_utc"], now),
    )
```

- [ ] **Step 4: Verify compile + missing-token returns 404**

Run:
```bash
source .venv/bin/activate && python -m py_compile app.py && \
python -c "
import app
app.app.config['TESTING']=True
c=app.app.test_client()
r=c.get('/s/does-not-exist')
print('status', r.status_code)
assert r.status_code==404
assert b'expired or' in r.data
print('OK 404 page')
"
```
Expected: `status 404` then `OK 404 page`.

- [ ] **Step 5: Commit**

```bash
git add app.py templates/shared.html templates/shared_missing.html
git commit -m "Simulator share: public read-only /s/<token> view"
```

---

### Task 4: Wire share/revoke into `/simulator` + UI

**Files:**
- Modify: `app.py` (`simulator()` — POST actions, GET purge, pass `shares`)
- Modify: `templates/simulator.html` (Save & share button + Shared links section)

- [ ] **Step 1: Add `share` and `revoke` POST actions**

In `simulator()`, find the `pick_winner` branch (ends with its `else: flash(... "warning")`), and **after** it but **before** the `save_data(data)` / `return redirect(url_for("simulator"))` lines, insert:
```python
        elif action == "share":
            if not sim.get("r32") and not sim.get("winners"):
                flash(translate("Nothing to share yet — make some picks first."), "warning")
            elif len(_user_shares(data, username, get_cached_time())) >= MAX_SHARES_PER_USER:
                flash(translate("You have too many active links. Revoke one first."), "warning")
            else:
                token = _create_share(data, username, sim, get_cached_time())
                url = url_for("shared_view", token=token, _external=True)
                flash(translate("Copy this link to share:") + " " + url, "success")
        elif action == "revoke":
            token = request.form.get("token")
            share = data.get("shared_sims", {}).get(token)
            if share and share.get("owner") == username:
                data["shared_sims"].pop(token, None)
                flash(translate("Link revoked."), "info")
```

- [ ] **Step 2: Purge expired shares on GET and pass `shares` to the template**

Find the GET self-heal block (added in the earlier simulator work):
```python
    before = json.dumps(sim, sort_keys=True)
    _prune_sim(sim)
    if json.dumps(sim, sort_keys=True) != before:
        save_data(data)
```
Replace it with:
```python
    before = json.dumps(sim, sort_keys=True)
    _prune_sim(sim)
    changed = json.dumps(sim, sort_keys=True) != before
    changed = _purge_expired_shares(data, get_cached_time()) or changed
    if changed:
        save_data(data)
    shares = _user_shares(data, username, get_cached_time())
```

Then find the final render in that route:
```python
    return render_template("simulator.html", columns=columns, third=third)
```
Replace with:
```python
    return render_template("simulator.html", columns=columns, third=third, shares=shares)
```

- [ ] **Step 3: Add the Save & share button + Shared links section to `simulator.html`**

Find the intro paragraph line:
```jinja
<p class="text-muted small">{{ _("Pick teams and winners to explore possible match-ups. This is just a sandbox — it is not scored and does not affect your predictions.") }}</p>
```
Insert directly **after** it:
```jinja
<div class="d-flex gap-2 flex-wrap mb-2">
  <form method="post">
    <input type="hidden" name="action" value="share">
    <button class="btn btn-sm btn-outline-info" type="submit">{{ _("Save & share") }}</button>
  </form>
</div>

{% if shares %}
<div class="card mb-3"><div class="card-body p-2 small">
  <div class="fw-bold mb-2">{{ _("Shared links") }}</div>
  {% for sh in shares %}
  <div class="d-flex align-items-center gap-2 mb-1 flex-wrap">
    <input class="form-control form-control-sm" style="max-width:300px" readonly
           value="{{ url_for('shared_view', token=sh.token, _external=True) }}"
           onclick="this.select()">
    <span class="text-muted">{{ _("Expires in {n} days", n=sh.days_left) }}</span>
    <form method="post">
      <input type="hidden" name="action" value="revoke">
      <input type="hidden" name="token" value="{{ sh.token }}">
      <button class="btn btn-sm btn-outline-danger py-0" type="submit">{{ _("Revoke") }}</button>
    </form>
  </div>
  {% endfor %}
</div></div>
{% endif %}
```
(The `onclick="this.select()"` is a bare inline attribute, not a script block — it keeps the no-custom-JS rule while making the link easy to copy. If you prefer strict no-JS, drop the attribute; the field is still selectable manually.)

- [ ] **Step 4: Verify compile + full share→view→revoke round-trip via test client**

Run:
```bash
source .venv/bin/activate && python -m py_compile app.py && \
python -c "
import app, re
app.app.config['TESTING']=True
app.app.config['SECRET_KEY']='t'
c=app.app.test_client()
# seed a user + login by setting session
with c.session_transaction() as s:
    s['username']='yuri'
import app as A
data=A.load_data(); data['users'].setdefault('yuri',{'password_hash':'x'})
data['simulations']['yuri']={'r32':{'r32-1':{'home':'Brazil','away':'Mexico'}},'winners':{'r32-1':'Brazil'}}
A.save_data(data)
# share
r=c.post('/simulator', data={'action':'share'}, follow_redirects=True)
m=re.search(rb'/s/([A-Za-z0-9_-]+)', r.data)
assert m, 'no share link rendered'
tok=m.group(1).decode()
print('token', tok)
# public view works without login
c2=app.app.test_client()
rv=c2.get('/s/'+tok)
assert rv.status_code==200 and b'Brazil' in rv.data and b'Shared by' in rv.data, rv.status_code
print('public view OK')
# revoke
c.post('/simulator', data={'action':'revoke','token':tok}, follow_redirects=True)
assert c2.get('/s/'+tok).status_code==404
print('revoke OK')
"
```
Expected: prints `token <…>`, `public view OK`, `revoke OK` with no assertion error. (This mutates your local `data.json`; harmless dev data.)

- [ ] **Step 5: Commit**

```bash
git add app.py templates/simulator.html
git commit -m "Simulator share: Save & share + revoke actions and links UI"
```

---

### Task 5: Drop a removed user's shared links

**Files:**
- Modify: `app.py` (admin `remove_user` action, ~line 1033)

- [ ] **Step 1: Add share cleanup to user removal**

Find:
```python
            data["users"].pop(uname, None)
            data["predictions"].pop(uname, None)   # clean orphaned predictions
```
Add directly below those two lines:
```python
            data["simulations"].pop(uname, None)   # clean orphaned simulation
            data["shared_sims"] = {t: s for t, s in data.get("shared_sims", {}).items()
                                   if s.get("owner") != uname}  # drop their shared links
```

- [ ] **Step 2: Verify compile + removal drops shares**

Run:
```bash
source .venv/bin/activate && python -m py_compile app.py && \
python -c "
import app
data={'users':{'bob':{}}, 'predictions':{'bob':{}}, 'simulations':{'bob':{}},
      'shared_sims':{'tk':{'owner':'bob'}, 'tk2':{'owner':'ana'}}}
# emulate the remove_user cleanup lines
uname='bob'
data['users'].pop(uname, None); data['predictions'].pop(uname, None)
data['simulations'].pop(uname, None)
data['shared_sims']={t:s for t,s in data['shared_sims'].items() if s.get('owner')!=uname}
assert 'tk' not in data['shared_sims'] and 'tk2' in data['shared_sims']
print('user-removal share cleanup OK')
"
```
Expected: `user-removal share cleanup OK`

- [ ] **Step 3: Commit**

```bash
git add app.py
git commit -m "Simulator share: drop a removed user's simulation + shared links"
```

---

### Task 6: Spanish translations

**Files:**
- Modify: `translations.py` (add to `SPANISH_TRANSLATIONS`)

- [ ] **Step 1: Add the new strings**

Append these entries inside the `SPANISH_TRANSLATIONS` dict (before the closing `}`):
```python
    # Shared simulation links
    "Save & share": "Guardar y compartir",
    "Shared links": "Enlaces compartidos",
    "Expires in {n} days": "Caduca en {n} días",
    "Revoke": "Revocar",
    "Link revoked.": "Enlace revocado.",
    "Shared by {user}": "Compartido por {user}",
    "Copy this link to share:": "Copia este enlace para compartir:",
    "Nothing to share yet — make some picks first.": "Nada para compartir todavía — haz algunas selecciones primero.",
    "You have too many active links. Revoke one first.": "Tienes demasiados enlaces activos. Revoca uno primero.",
    "This shared bracket has expired or doesn't exist.": "Este cuadro compartido caducó o no existe.",
```

- [ ] **Step 2: Verify compile + a key round-trips in ES**

Run:
```bash
source .venv/bin/activate && python -m py_compile translations.py && \
python -c "
from translations import SPANISH_TRANSLATIONS as S
assert S['Save & share']=='Guardar y compartir'
# templated string still formats after translation
print(S['Expires in {n} days'].format(n=7))
"
```
Expected: `Caduca en 7 días`

- [ ] **Step 3: Commit**

```bash
git add translations.py
git commit -m "Simulator share: Spanish translations for share UI"
```

---

### Task 7: End-to-end verification + cleanup

**Files:**
- Delete: `test_share.py` (scratch)
- Modify: `CLAUDE.md` (document the share feature in the Simulator section)

- [ ] **Step 1: Full compile + scratch suite green**

Run:
```bash
source .venv/bin/activate && python -m py_compile app.py translations.py && python test_share.py
```
Expected: `compile` clean; all `PASS`, exit 0.

- [ ] **Step 2: Manual browser sanity (optional but recommended)**

Run the dev server and click through: create a share on `/simulator`, open the printed `/s/<token>` link in a private window (no login) → read-only bracket renders; revoke → link 404s.
```bash
source .venv/bin/activate && python app.py   # visit http://localhost:5000/simulator
```

- [ ] **Step 3: Remove the scratch test (repo has no committed test suite)**

```bash
rm test_share.py
```

- [ ] **Step 4: Document the feature in `CLAUDE.md`**

In the **Simulator** paragraph, append a sentence describing shares. Find the end of that paragraph (`…Same winner-flow tree layout as /bracket (third rendered separately).`) and add after it:
```markdown
**Shared snapshots:** "Save & share" (`action=share`) deep-copies the user's sim into
`data["shared_sims"][token]` (`token`=`secrets.token_urlsafe(8)`) with a 7-day
`expires_utc`; the public, login-free `GET /s/<token>` (`shared_view`) renders it
read-only via `_sim_view` over the frozen sim. Snapshots are **never** pruned. Owners
see active links (`_user_shares`) with copy + `revoke`. Expiry is lazy — `_purge_expired_shares`
runs on `/simulator` load and when `/s/` hits an expired token. Missing/expired both
return the same 404 `shared_missing.html`.
```

- [ ] **Step 5: Final commit**

```bash
git add CLAUDE.md
git commit -m "Docs: document shareable simulation snapshots in CLAUDE.md"
```

- [ ] **Step 6: Push**

```bash
git push
```

---

## Self-Review

**Spec coverage** (against `2026-06-04-shareable-simulation-link-design.md`):
- Data model `shared_sims` + migrate seed → Task 1. ✓
- Deep-copy/frozen snapshot, 7-day expiry → Task 2 (`_create_share`). ✓
- Share action + empty guard + per-user cap → Task 4 step 1. ✓
- List + revoke (owner-checked) → Task 4 (helpers/UI), `revoke` action. ✓
- Public read-only `/s/<token>`, owner attribution, "expires in N days" → Task 3. ✓
- Missing/expired → single 404 page; expired purged on the way out → Task 3 route. ✓
- Lazy purge on write paths → Task 3 (`/s/` expired) + Task 4 step 2 (`/simulator` GET). ✓
- `_share_days_left` ceil + fail-closed on bad timestamp → Task 2. ✓
- Owner-removal cleanup → Task 5. ✓
- i18n EN/ES → Task 6. ✓

**Type/name consistency:** `_share_days_left`, `_purge_expired_shares`, `_create_share`, `_user_shares`, `shared_view`, `SHARE_TTL_DAYS`, `MAX_SHARES_PER_USER`, template `shares` rows `{token, days_left, created_utc}` — used identically across Tasks 2–6. ✓

**Placeholder scan:** none — every code/command step carries concrete content. ✓
