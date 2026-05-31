# Bracket Tree Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Render `/bracket` as a connected winner-flow tree (R32→Final) with CSS elbow connectors, pair-aligned spacing, and "Winner R32-1" feed labels in empty downstream slots; third-place shown as a standalone card below.

**Architecture:** No data-model change. Feeders are derived from arithmetic on the numeric id suffix. A pure helper `feeders(match)` returns the structural pairing; a display helper `feed_label_pair(match)` wraps it with i18n. The `/bracket` route builds a `columns` structure plus a separate `third` match; the template renders cards via a Jinja macro; pure-CSS pseudo-element connectors live in `base.html`.

**Tech Stack:** Flask, Jinja2, Bootstrap 5.3 (dark), pure CSS (no JS). Single-file app (`app.py`). No pytest — verify with `python -m py_compile`, a `python -c` assertion, and manual browser checks (per CLAUDE.md).

**Spec:** `docs/superpowers/specs/2026-05-31-bracket-tree-design.md`

---

### Task 1: Pure `feeders()` helper + `SHORT` map

The structural core: given a match, which two previous-round matches feed it, and do winners or losers advance. Pure — no `g`, no translation — so it's unit-testable in a bare `python -c`.

**Files:**
- Modify: `app.py` (add after `ROUND_LABELS`, around line 70)

- [ ] **Step 1: Write the implementation**

Add to `app.py` immediately after the `ROUND_LABELS` block (after line 70):

```python
# Compact round codes for bracket feed labels ("Winner R32-1"). Not translated —
# language-neutral and short enough for a narrow bracket column.
SHORT = {"r32": "R32", "r16": "R16", "qf": "QF", "sf": "SF"}

# Standard bracket pairing: match k of a round is fed by matches (2k-1, 2k) of the
# previous round; the third-place play-off and the final both draw from the two
# semifinals (losers and winners respectively).
_FEEDER_PREV = {"r16": "r32", "qf": "r16", "sf": "qf", "final": "sf", "third": "sf"}


def feeders(match):
    """Return (word, top_feeder_id, bottom_feeder_id) for a match's two slots, or
    None for Round of 32 / unknown rounds (no feeders). `word` is the untranslated
    key "Winner" or "Loser". Pure: derived from the numeric id suffix, no app
    context required."""
    rnd = match.get("round")
    prev = _FEEDER_PREV.get(rnd)
    if not prev:
        return None
    word = "Loser" if rnd == "third" else "Winner"
    if rnd in ("final", "third"):
        return (word, "sf-1", "sf-2")
    try:
        k = int(str(match["id"]).rsplit("-", 1)[-1])
    except (ValueError, KeyError):
        return None
    return (word, f"{prev}-{2 * k - 1}", f"{prev}-{2 * k}")
```

- [ ] **Step 2: Write the failing test (assertion script) and run it**

Run this one-liner (it exercises every branch):

```bash
python -c "
from app import feeders
assert feeders({'id':'r16-1','round':'r16'}) == ('Winner','r32-1','r32-2'), feeders({'id':'r16-1','round':'r16'})
assert feeders({'id':'r16-8','round':'r16'}) == ('Winner','r32-15','r32-16')
assert feeders({'id':'qf-1','round':'qf'})   == ('Winner','r16-1','r16-2')
assert feeders({'id':'sf-2','round':'sf'})   == ('Winner','qf-3','qf-4')
assert feeders({'id':'final-1','round':'final'}) == ('Winner','sf-1','sf-2')
assert feeders({'id':'third-1','round':'third'}) == ('Loser','sf-1','sf-2')
assert feeders({'id':'r32-5','round':'r32'})  is None
print('feeders OK')
"
```

Expected: `feeders OK` (if you run it BEFORE Step 1, it fails with `ImportError: cannot import name 'feeders'`).

- [ ] **Step 3: Commit**

```bash
git add app.py
git commit -m "Add pure feeders() helper + SHORT map for bracket pairing

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: Display helpers (`_short_id`, `feed_label_pair`) + translations

Wrap the pure pairing with i18n to produce the visible labels ("Winner R32-1").

**Files:**
- Modify: `app.py` (add directly after `feeders`)
- Modify: `translations.py` (add two entries)

- [ ] **Step 1: Add the display helpers**

Add to `app.py` directly after the `feeders` function:

```python
def _short_id(feeder_id):
    """'r32-1' -> 'R32-1' for display."""
    rnd, _, num = feeder_id.rpartition("-")
    return f"{SHORT.get(rnd, rnd.upper())}-{num}"


def feed_label_pair(match):
    """Translated placeholder labels for a match's two empty slots, e.g.
    ('Winner R32-1', 'Winner R32-2') — or (None, None) for Round of 32.
    Requires app context (uses translate())."""
    f = feeders(match)
    if not f:
        return (None, None)
    word, top, bot = f
    return (f"{translate(word)} {_short_id(top)}",
            f"{translate(word)} {_short_id(bot)}")
```

Note: `_short_id` and `feed_label_pair` must be defined AFTER `translate` (which lives around line 348). Placing them right after `feeders` works because `translate` is only *called* at request time, not at import — Python resolves the name when `feed_label_pair` runs, by which point `translate` is defined.

- [ ] **Step 2: Add translations**

In `translations.py`, add these two entries inside the `SPANISH_TRANSLATIONS` dict (e.g. in the "Bracket" section near `"Champion"`):

```python
    "Winner": "Ganador",
    "Loser": "Perdedor",
```

- [ ] **Step 3: Verify it compiles and the labels build**

```bash
python -m py_compile app.py translations.py
python -c "
from app import app
with app.test_request_context('/'):
    from app import feed_label_pair
    assert feed_label_pair({'id':'r16-3','round':'r16'}) == ('Winner R16-5','Winner R16-6'), feed_label_pair({'id':'r16-3','round':'r16'})
    assert feed_label_pair({'id':'third-1','round':'third'}) == ('Loser SF-1','Loser SF-2')
    assert feed_label_pair({'id':'r32-1','round':'r32'}) == (None, None)
print('feed_label_pair OK')
"
```

Expected: no compile output, then `feed_label_pair OK`. (Default lang is `en` in a bare test context, so words aren't translated here — the Spanish path is verified manually in Task 6.)

- [ ] **Step 4: Commit**

```bash
git add app.py translations.py
git commit -m "Add feed-label display helpers + Winner/Loser translations

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: Rebuild the `/bracket` route

Build a `columns` structure (tree rounds only) with per-slot display values, fix the lexicographic sort, and pass third-place separately.

**Files:**
- Modify: `app.py:519-526` (the `bracket()` route)

- [ ] **Step 1: Replace the route**

Replace the entire current `bracket()` function (lines 519-526):

```python
@app.route("/bracket")
def bracket():
    data = load_data()
    by_round = {r: [] for r in ROUND_LABELS}
    for m in sorted(data["matches"], key=lambda x: x["id"]):
        by_round.setdefault(m["round"], []).append(m)
    order = ["r32", "r16", "qf", "sf", "third", "final"]
    return render_template("bracket.html", by_round=by_round, order=order)
```

with:

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


@app.route("/bracket")
def bracket():
    data = load_data()
    tree_order = ["r32", "r16", "qf", "sf", "final"]
    columns = []
    for rnd in tree_order:
        rnd_matches = sorted_matches([m for m in data["matches"] if m.get("round") == rnd])
        columns.append({"round": rnd, "matches": [_bracket_view(m) for m in rnd_matches]})
    third_match = next((m for m in data["matches"] if m.get("round") == "third"), None)
    third = _bracket_view(third_match) if third_match else None
    return render_template("bracket.html", columns=columns, third=third)
```

- [ ] **Step 2: Verify it compiles and the structure is correct**

```bash
python -m py_compile app.py
python -c "
from app import app
client = app.test_client()
r = client.get('/bracket')
assert r.status_code == 200, r.status_code
print('bracket route OK', len(r.data), 'bytes')
"
```

Expected: `bracket route OK <N> bytes`. (The template still references the old `by_round`/`order` until Task 4 — if this step is run before Task 4 the render will error; that's expected, proceed to Task 4 and re-run the full check in Task 6.)

- [ ] **Step 3: Commit**

```bash
git add app.py
git commit -m "Rebuild /bracket route: tree columns + numeric sort + standalone third

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 4: Rewrite `bracket.html`

Render the tree columns via a DRY macro, with per-slot placeholders and the standalone third-place card.

**Files:**
- Modify: `templates/bracket.html` (full replacement)

- [ ] **Step 1: Replace the template**

Replace the entire contents of `templates/bracket.html` with:

```html
{% extends "base.html" %}

{% macro match_card(m, show_champion=false) %}
<div class="card">
  <div class="card-body p-2 small">
    <div class="bracket-slot{{ ' text-muted fst-italic' if m.home_is_placeholder }}{{ ' fw-bold accent' if m.advanced_team and m.advanced_team == m.home_team }}">
      {{ m.home_display }}{% if m.home_score is not none %}<span class="float-end">{{ m.home_score }}</span>{% endif %}
    </div>
    <div class="bracket-slot{{ ' text-muted fst-italic' if m.away_is_placeholder }}{{ ' fw-bold accent' if m.advanced_team and m.advanced_team == m.away_team }}">
      {{ m.away_display }}{% if m.away_score is not none %}<span class="float-end">{{ m.away_score }}</span>{% endif %}
    </div>
    {% if show_champion and m.advanced_team %}
    <div class="text-center mt-1">🏆 <span class="accent">{{ _("Champion") }}: {{ m.advanced_team }}</span></div>
    {% endif %}
  </div>
</div>
{% endmacro %}

{% block content %}
<h3 class="mb-3">{{ _("Tournament Bracket") }}</h3>

<div class="bracket">
  {% for col in columns %}
  {% set is_feeder = col.round in ['r32', 'r16', 'qf', 'sf'] %}
  <div class="round round-{{ col.round }}">
    <h6 class="accent text-center mb-3">{{ round_label(col.round) }}</h6>
    {% for m in col.matches %}
    <div class="bracket-match{% if is_feeder %}{{ ' feeder-top' if loop.index is odd else ' feeder-bottom' }}{% endif %}">
      {{ match_card(m, show_champion=(col.round == 'final')) }}
    </div>
    {% endfor %}
  </div>
  {% endfor %}
</div>

{% if third %}
<div class="third-place mt-4">
  <h6 class="accent">{{ round_label('third') }}</h6>
  <div style="max-width:210px">{{ match_card(third) }}</div>
</div>
{% endif %}
{% endblock %}
```

- [ ] **Step 2: Verify it renders**

```bash
python -m py_compile app.py
python -c "
from app import app
r = app.test_client().get('/bracket')
assert r.status_code == 200, r.status_code
body = r.data.decode()
assert 'bracket-match' in body and 'Tournament Bracket' in body
print('template renders OK')
"
```

Expected: `template renders OK`.

- [ ] **Step 3: Commit**

```bash
git add templates/bracket.html
git commit -m "Rewrite bracket template: DRY macro, per-slot labels, standalone third

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 5: Bracket connector CSS in `base.html`

Pure-CSS tree: flex columns for pair-aligned spacing, L-shaped pseudo-element connectors.

**Files:**
- Modify: `templates/base.html` (the `<style>` block, lines 8-22)

- [ ] **Step 1: Add `--wc-line` to `:root`**

In `base.html`, change the `:root` line (line 9) from:

```css
    :root { --wc-primary:#1a7a3c; --wc-accent:#ffd24d; --wc-bg:#0a1f12; }
```

to:

```css
    :root { --wc-primary:#1a7a3c; --wc-accent:#ffd24d; --wc-bg:#0a1f12; --wc-line:#2f6b41; }
```

- [ ] **Step 2: Append the bracket styles**

Add the following just before the closing `</style>` tag (after line 21, the `a { color:var(--wc-accent); }` line):

```css
    /* Bracket tree -------------------------------------------------------- */
    .bracket { display:flex; flex-wrap:nowrap; overflow-x:auto; min-height:54rem; padding-bottom:1rem; }
    .round { display:flex; flex-direction:column; min-width:210px; padding:0 14px; }
    .round > h6 { flex:0 0 auto; }
    .bracket-match { flex:1 1 0; display:flex; flex-direction:column; justify-content:center; position:relative; }
    .bracket-match .card { margin:0; }
    .bracket-slot { white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
    /* outgoing L-connector: vertical half drawn by every feeder match */
    .round-r32 .bracket-match::after,
    .round-r16 .bracket-match::after,
    .round-qf  .bracket-match::after,
    .round-sf  .bracket-match::after {
      content:""; position:absolute; right:-14px; width:14px; height:50%;
      border-right:2px solid var(--wc-line);
    }
    /* top feeder: horizontal stub at its centre + vertical going down */
    .round-r32 .feeder-top::after,
    .round-r16 .feeder-top::after,
    .round-qf  .feeder-top::after,
    .round-sf  .feeder-top::after { top:50%; border-top:2px solid var(--wc-line); }
    /* bottom feeder: horizontal stub at its centre + vertical going up */
    .round-r32 .feeder-bottom::after,
    .round-r16 .feeder-bottom::after,
    .round-qf  .feeder-bottom::after,
    .round-sf  .feeder-bottom::after { bottom:50%; border-bottom:2px solid var(--wc-line); }
    /* incoming stub: from mid-gutter to each receiver's centre */
    .round-r16 .bracket-match::before,
    .round-qf  .bracket-match::before,
    .round-sf  .bracket-match::before,
    .round-final .bracket-match::before {
      content:""; position:absolute; left:-14px; top:50%; width:14px;
      border-top:2px solid var(--wc-line);
    }
```

- [ ] **Step 3: Verify it still serves**

```bash
python -c "
from app import app
r = app.test_client().get('/bracket')
assert r.status_code == 200
assert '--wc-line' in r.data.decode() and 'bracket-match' in r.data.decode()
print('css served OK')
"
```

Expected: `css served OK`.

- [ ] **Step 4: Commit**

```bash
git add templates/base.html
git commit -m "Add pure-CSS bracket tree connectors

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 6: Manual verification (EN + ES) and seed-data check

No automated browser test exists; verify visually against a partly-filled bracket.

**Files:** none (verification only)

- [ ] **Step 1: Final syntax + scoring safety check**

```bash
python -m py_compile app.py translations.py
python -c "
from app import compute_points
m = {'round':'r32','home_score':2,'away_score':1,'advanced_team':'A'}
print(compute_points({'home':2,'away':1,'advance':'A'}, m))  # {'score':6,'advance':2,'total':8}
"
```

Expected: clean compile, then `{'score': 6, 'advance': 2, 'total': 8}`.

- [ ] **Step 2: Seed a partly-filled bracket for a realistic view**

Run the dev server in one terminal (`python app.py`), then in another shell seed two R32 results so feed labels, real names, and connectors all appear:

```bash
python -c "
from app import load_data, save_data
d = load_data()
by_id = {m['id']: m for m in d['matches']}
by_id['r32-1'].update(home_team='Brazil', away_team='Chile', home_score=2, away_score=1, advanced_team='Brazil')
by_id['r32-2'].update(home_team='Spain', away_team='Japan', home_score=0, away_score=3, advanced_team='Japan')
save_data(d)
print('seeded r32-1, r32-2')
"
```

- [ ] **Step 3: Visual check in the browser (English)**

Open `http://localhost:5000/bracket` (set EN via the nav) and confirm:
  - R32 column lists matches in order 1…16 (NOT `r32-1, r32-10, r32-11, … r32-2`).
  - `r32-1` shows `Brazil 2 / Chile 1` with Brazil bold-accented; `r32-2` shows Japan accented.
  - Each later match is vertically centred against its feeding pair; elbow connectors join every pair through to the Final.
  - `r16-1` (empty) shows muted italic `Winner R32-1 / Winner R32-2`; deeper empties show `Winner R16-x`, `Winner QF-x`, `Winner SF-x`.
  - R32's own empty matches show `TBD` (no feed label), muted.
  - The standalone third-place card sits below the tree showing `Loser SF-1 / Loser SF-2`, with no connectors.

- [ ] **Step 4: Visual check (Spanish)**

Switch to ES in the nav and reload `/bracket`. Confirm placeholders read `Ganador R32-1`, `Ganador SF-2`, and the third-place card reads `Perdedor SF-1 / Perdedor SF-2`; round headers use the Spanish labels (Dieciseisavos, Octavos, …).

- [ ] **Step 5: Reset the seed data (optional)**

```bash
python -c "
from app import load_data, save_data
d = load_data()
for mid in ('r32-1','r32-2'):
    m = next(x for x in d['matches'] if x['id']==mid)
    m.update(home_team=None, away_team=None, home_score=None, away_score=None, advanced_team=None)
save_data(d)
print('reset')
"
```

- [ ] **Step 6: Confirm no data/secrets staged, then done**

```bash
git status --short
```

Expected: clean (all changes already committed in Tasks 1-5; `data.json` is gitignored and must NOT appear).
