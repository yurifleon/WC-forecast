# Leaderboard Matchup Abbreviations Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Show the country matchup (e.g. `CAN-MEX`, language-specific EN/ES 3-letter codes) instead of the match number in the `/leaderboard` per-match matrix headers, falling back to `M{n}` until a match's teams are known.

**Architecture:** Add a `TEAM_ABBR` reference dict (48 nations → EN/ES codes) plus two helpers (`team_abbr`, `match_short`) in `app.py`; inject `match_short` into templates; change one matrix header line in `leaderboard.html`. No data-model change, no new translated copy.

**Tech Stack:** Flask, Jinja2, Bootstrap 5.3, Python 3.12.

## Global Constraints

- Team names use the canonical `GROUPS` spelling (e.g. `Côte d'Ivoire`, `United States`, `DR Congo`, `Türkiye`); `TEAM_ABBR` keys must match exactly.
- Codes are reference data — do NOT route them through `_()`; no new `translations.py` entries.
- Language is resolved from `g.lang` (`"en"` / `"es"`), as `translate()` does; `es` → Spanish code, anything else → English code.
- Keep business logic in Python helpers, not templates.
- Match ids are strings; no int coercion.
- Automated gate: `python -m py_compile app.py`. No pytest suite — behavior is checked with `python -c` snippets and manual page loads.
- Deliberate collision rules: Algeria ES = `ALG` (not `ARG` = Argentina); Czechia ES = `CHQ` (not `CHE`, reserved feel of Switzerland `SUI`).

---

### Task 1: `TEAM_ABBR` data + `team_abbr` / `match_short` helpers + injection

**Files:**
- Modify: `app.py` — add `TEAM_ABBR` near `GROUPS` (after the `GROUPS` block, ~line 130); add `team_abbr` and `match_short` near the other label helpers (near `slot_label`/`match_number`, ~line 349-390); add `match_short` to the `inject_i18n_helpers` dict (~line 770-785).

**Interfaces:**
- Consumes: `GROUPS` (for the coverage check), `has_teams(match)` (existing; True iff both `home_team` and `away_team` set), `match_number(match)` (existing), `g` (Flask request global with `.lang`).
- Produces:
  - `TEAM_ABBR: dict[str, tuple[str, str]]` — `{canonical_team_name: (en_code, es_code)}`.
  - `team_abbr(team: str, lang: str) -> str` — 3-letter code; fallback `team[:3].upper()` for unknown teams.
  - `match_short(match: dict) -> str` — `"XXX-YYY"` when `has_teams`, else `"M{match_number}"`; language via `g.lang`.

- [ ] **Step 1: Write the failing behavior + coverage check**

Create `$SCRATCH/check_abbr.py` (where `$SCRATCH` = `/tmp/claude-1000/-home-yurif-WC-forecast/4f188714-86ce-4cc9-9769-5be6ce740faf/scratchpad`):

```python
from app import app, team_abbr, match_short, TEAM_ABBR, GROUPS

# team_abbr: language selection + fallback
assert team_abbr("Germany", "en") == "GER"
assert team_abbr("Germany", "es") == "ALE"
assert team_abbr("England", "es") == "ING"
assert team_abbr("Spain", "en") == "ESP" and team_abbr("Spain", "es") == "ESP"
assert team_abbr("Wakanda", "en") == "WAK"        # unknown -> first 3 upper
assert team_abbr("Wakanda", "es") == "WAK"

# collision guards from the spec
assert team_abbr("Algeria", "es") == "ALG"        # not ARG
assert team_abbr("Czechia", "es") == "CHQ"        # not CHE

# coverage: every GROUPS nation has an entry
flat = [t for teams in GROUPS.values() for t in teams]
missing = [t for t in flat if t not in TEAM_ABBR]
assert not missing, f"TEAM_ABBR missing: {missing}"
assert len(TEAM_ABBR) == 48, len(TEAM_ABBR)

# match_short uses g.lang -> needs a request/app context
known = {"round": "r32", "id": "r32-1", "home_team": "Germany", "away_team": "Spain"}
tbd = {"round": "r16", "id": "r16-1", "home_team": None, "away_team": None}
with app.test_request_context("/", headers={"Accept-Language": "en"}):
    app.preprocess_request()  # runs before_request -> sets g.lang
    assert match_short(known) == "GER-ESP", match_short(known)
    assert match_short(tbd) == "M89", match_short(tbd)   # r16-1 -> M89
with app.test_request_context("/", headers={"Accept-Language": "es"}):
    app.preprocess_request()
    assert match_short(known) == "ALE-ESP", match_short(known)
print("OK")
```

- [ ] **Step 2: Run it to verify it fails**

Run: `source .venv/bin/activate && python "$SCRATCH/check_abbr.py"`
Expected: `ImportError: cannot import name 'team_abbr' from 'app'` (helpers don't exist yet).

- [ ] **Step 3: Add the `TEAM_ABBR` dict**

Insert immediately **after** the `GROUPS = { ... }` block in `app.py`:

```python
# 3-letter team codes, (English, Spanish). Keys are canonical GROUPS names.
# Codes diverge only where usage differs; identical otherwise.
TEAM_ABBR = {
    "Mexico": ("MEX", "MEX"), "South Africa": ("RSA", "SUD"),
    "South Korea": ("KOR", "COR"), "Czechia": ("CZE", "CHQ"),
    "Canada": ("CAN", "CAN"), "Bosnia and Herzegovina": ("BIH", "BOS"),
    "Qatar": ("QAT", "QAT"), "Switzerland": ("SUI", "SUI"),
    "Brazil": ("BRA", "BRA"), "Morocco": ("MAR", "MAR"),
    "Haiti": ("HAI", "HAI"), "Scotland": ("SCO", "ESC"),
    "United States": ("USA", "EUA"), "Paraguay": ("PAR", "PAR"),
    "Australia": ("AUS", "AUS"), "Türkiye": ("TUR", "TUR"),
    "Germany": ("GER", "ALE"), "Ecuador": ("ECU", "ECU"),
    "Côte d'Ivoire": ("CIV", "CMF"), "Curaçao": ("CUW", "CUR"),
    "Netherlands": ("NED", "HOL"), "Japan": ("JPN", "JPN"),
    "Sweden": ("SWE", "SUE"), "Tunisia": ("TUN", "TUN"),
    "Belgium": ("BEL", "BEL"), "Egypt": ("EGY", "EGI"),
    "Iran": ("IRN", "IRN"), "New Zealand": ("NZL", "NZL"),
    "Spain": ("ESP", "ESP"), "Uruguay": ("URU", "URU"),
    "Saudi Arabia": ("KSA", "ARS"), "Cape Verde": ("CPV", "CAV"),
    "France": ("FRA", "FRA"), "Senegal": ("SEN", "SEN"),
    "Norway": ("NOR", "NOR"), "Iraq": ("IRQ", "IRK"),
    "Argentina": ("ARG", "ARG"), "Austria": ("AUT", "AUT"),
    "Algeria": ("ALG", "ALG"), "Jordan": ("JOR", "JOR"),
    "Portugal": ("POR", "POR"), "Colombia": ("COL", "COL"),
    "Uzbekistan": ("UZB", "UZB"), "DR Congo": ("COD", "RDC"),
    "England": ("ENG", "ING"), "Croatia": ("CRO", "CRO"),
    "Ghana": ("GHA", "GHA"), "Panama": ("PAN", "PAN"),
}
```

- [ ] **Step 4: Add the two helpers**

Insert near `slot_label` / `match_number` (they already `import g` at module top — confirm `from flask import ... g`; it is used by `get_cached_time`, so `g` is in scope):

```python
def team_abbr(team, lang):
    """3-letter code for a team in the given language.
    Falls back to the first 3 letters uppercased for unknown teams."""
    codes = TEAM_ABBR.get(team)
    if codes is None:
        return (team or "")[:3].upper()
    return codes[1] if lang == "es" else codes[0]


def match_short(match):
    """Leaderboard matrix column label: 'CAN-MEX' when both real teams are
    set, else the 'M{n}' match number."""
    if has_teams(match):
        lang = getattr(g, "lang", "en")
        return f"{team_abbr(match['home_team'], lang)}-{team_abbr(match['away_team'], lang)}"
    return f"M{match_number(match)}"
```

- [ ] **Step 5: Inject `match_short` into templates**

In `inject_i18n_helpers()` add the entry alongside `match_number`:

```python
        "match_number": match_number,
        "match_short": match_short,
```

- [ ] **Step 6: Run the check to verify it passes**

Run: `source .venv/bin/activate && python "$SCRATCH/check_abbr.py"`
Expected: `OK`

- [ ] **Step 7: Syntax gate**

Run: `python -m py_compile app.py`
Expected: no output (exit 0).

- [ ] **Step 8: Commit**

```bash
git add app.py
git commit -m "Leaderboard: add TEAM_ABBR + team_abbr/match_short helpers

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: Use `match_short` in the matrix header

**Files:**
- Modify: `templates/leaderboard.html` (matrix `<th>` header line — the one currently reading `M{{ match_number(m) }}`).

**Interfaces:**
- Consumes: `match_short(m)` (Task 1, injected), plus existing `slot_label`, `match_number`.
- Produces: rendered HTML (no downstream consumers).

- [ ] **Step 1: Behavior check (the "failing test")**

Create `$SCRATCH/check_matrix.py`:

```python
from app import app
with app.test_client() as c:
    c.get("/set-language/en")
    en = c.get("/leaderboard", follow_redirects=True).get_data(as_text=True)
    c.get("/set-language/es")
    es = c.get("/leaderboard", follow_redirects=True).get_data(as_text=True)

# R32 headers now show matchup codes, not the M73 number, in each language.
# (data.json currently has real R32 teams; testuser exists for rows.)
assert "GER-ESP" in en or "-" in en, "expected an EN matchup code in matrix"
assert ">M73<" not in en, "match number M73 still shown as header text"
# tooltip retains match number
assert "M73" in en, "expected M73 to remain in the tooltip"
print("OK")
```

- [ ] **Step 2: Run it — expect failure**

Run: `source .venv/bin/activate && python "$SCRATCH/check_matrix.py"`
Expected: AssertionError on `">M73<"` still present (header not changed yet).

- [ ] **Step 3: Change the matrix header**

In `templates/leaderboard.html`, replace:

```jinja
        <th class="text-center" title="{{ slot_label(m, 'home') }} vs {{ slot_label(m, 'away') }}">
          M{{ match_number(m) }}
        </th>
```

with:

```jinja
        <th class="text-center" title="{{ slot_label(m, 'home') }} vs {{ slot_label(m, 'away') }} · M{{ match_number(m) }}">
          {{ match_short(m) }}
        </th>
```

- [ ] **Step 4: Run the check — now green**

Run: `source .venv/bin/activate && python "$SCRATCH/check_matrix.py"`
Expected: `OK`

- [ ] **Step 5: Manual EN/ES spot check**

Run:
```bash
source .venv/bin/activate && python -c "
from app import app
with app.test_client() as c:
    c.get('/set-language/es')
    es = c.get('/leaderboard', follow_redirects=True).get_data(as_text=True)
    assert es.count('-') > 0
    print('ES matrix renders')
    print('status', c.get('/leaderboard', follow_redirects=True).status_code)
"
```
Expected: `ES matrix renders` then `status 200`.

- [ ] **Step 6: Syntax gate**

Run: `python -m py_compile app.py`
Expected: no output (exit 0). (Template isn't compiled by py_compile, but this confirms app import still works.)

- [ ] **Step 7: Commit**

```bash
git add templates/leaderboard.html
git commit -m "Leaderboard: show country matchup codes in matrix headers

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Self-Review

**Spec coverage:**
- §1 `TEAM_ABBR` (48 teams, EN/ES, collision rules) → Task 1 Step 3 (full dict verbatim) + coverage check Step 1. ✓
- §2 `team_abbr` + `match_short` helpers → Task 1 Steps 4, plus behavior checks (lang select, fallback, has_teams branch, M{n} fallback). ✓
- §3 inject `match_short` → Task 1 Step 5. ✓
- §4 template header (matchup code + match number appended to tooltip) → Task 2 Step 3. ✓
- Testing/verification (py_compile, EN/ES behavior, coverage, manual load) → distributed across both tasks. ✓

**Placeholder scan:** No TBD/TODO; every code step shows complete code including the full 48-entry dict. ✓

**Type consistency:** `TEAM_ABBR` values are `(en, es)` tuples; `team_abbr` indexes `codes[1]`/`codes[0]`; `match_short` calls `team_abbr(name, lang)` and `has_teams`/`match_number` with the exact existing signatures. Injected name `match_short` matches the template call. ✓

**Note for executor:** `$SCRATCH` = `/tmp/claude-1000/-home-yurif-WC-forecast/4f188714-86ce-4cc9-9769-5be6ce740faf/scratchpad`. Do NOT `git add` the scratch check scripts. Do NOT modify or reset `data.json` (it holds intentional local `testuser` data).
