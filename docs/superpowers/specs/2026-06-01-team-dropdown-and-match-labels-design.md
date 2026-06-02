# Team Dropdown + Match Labels — Design

**Date:** 2026-06-01
**Scope:** (a) Replace the admin free-text team boxes with **group-narrowed dropdowns** sourced from `FIFA_WC_2026_Master_Guide.md`, and (b) show each match's **FIFA match number** (`M73`–`M104`) across bracket, dashboard, admin, and predict. Touches `app.py`, `templates/admin.html`, `templates/dashboard.html`, `templates/predict.html`, `templates/bracket.html`. No scoring/locking/data-model change (both features are derived, not stored).

**Source (committed as reference):** `FIFA_WC_2026_Master_Guide.md` — 12 groups × 4 teams (48 nations) + the knockout structure.

**Cities note:** not a bug — venues render server-side (verified live). The user's missing cities were a stale browser cache; a hard refresh resolves it. No code change.

## 1. Data constants (`app.py`)

```python
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
ALL_TEAMS = sorted({t for teams in GROUPS.values() for t in teams})  # 48, fallback
```

UTF-8 names kept verbatim (`Türkiye`, `Côte d'Ivoire`, `Curaçao`); `_write` already uses `ensure_ascii=False`.

## 2. Team-candidate helper (`app.py`)

```python
def _origin_groups(origin):
    """Group letters an R32 origin slot can draw from. '2A' -> ['A'];
    '3rd A/B/C/D/F' -> ['A','B','C','D','F']; unknown -> []."""
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
    Third place: the loser of the feeding semifinal. Empty when undecided.
    `by_id` maps match id -> match dict. Sorted, de-duplicated."""
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

`feeders()` already returns `(word, top_id, bot_id)` with `top`→home slot, `bot`→away slot (same convention as `feed_label_pair`), so home/away map correctly, including the third-place losers.

## 3. Match-number helper (`app.py`) + injection

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

Add `"match_number": match_number` to `inject_i18n_helpers` so all templates can call it. (Verified: this maps the 32 ids onto 73–104 contiguously.)

## 4. Admin dropdowns (`app.py` route + `templates/admin.html`)

- **Route (`admin`, the GET render):** build `by_id = {m["id"]: m for m in data["matches"]}` and pass matches enriched with options:
  ```python
  matches = [
      {**m, "home_options": team_options(m, "home", by_id),
            "away_options": team_options(m, "away", by_id)}
      for m in sorted_matches(data["matches"])
  ]
  ```
- **Template:** replace the two `<input name="home_team">` / `<input name="away_team">` text boxes with `<select>`s:
  ```html
  <select class="form-select form-select-sm" name="home_team">
    <option value="">—</option>
    {% for t in m.home_options %}
    <option value="{{ t }}" {{ 'selected' if t == m.home_team }}>{{ t }}</option>
    {% endfor %}
    {% if m.home_team and m.home_team not in m.home_options %}
    <option value="{{ m.home_team }}" selected>{{ m.home_team }}</option>
    {% endif %}
  </select>
  ```
  (same for `away_team` with `m.away_options`). The trailing `{% if %}` preserves any already-saved team that isn't in the narrowed list, so nothing is lost.
- **Save logic unchanged:** `save_match` still does `(request.form.get("home_team") or "").strip() or None` — works identically for a `<select>`. The blank `—` option clears the slot. The `advanced_team` select (lists the two set teams) is unchanged and now always gets clean names.

## 5. Match number "M73" display

Show a muted `· M<n>` next to the round label (compact `M73` form), on all four views:
- **`admin.html`** round-label line: `{{ round_label(m.round) }} · M{{ match_number(m) }} — {{ _("single match") }}`.
- **`dashboard.html`** round-label line: append ` · M{{ match_number(m) }}`.
- **`predict.html`** round-label line: insert ` · M{{ match_number(match) }}` (before the existing `· venue`).
- **`bracket.html`** match card: a small muted `M{{ match_number(m) }}` line (the round is already the column header, so just the number on each card). `_bracket_view` spreads `id`/`round`, so `match_number(m)` works in the bracket context.

`M` + number is language-neutral — no new i18n strings.

## 6. Testing (no pytest — `python -c` idiom, `python3`)

- `python -m py_compile app.py`.
- `_origin_groups`: `"2A"`→`["A"]`, `"1F"`→`["F"]`, `"3rd A/B/C/D/F"`→`["A","B","C","D","F"]`, `""`→`[]`.
- `team_options` (build a `by_id` from fixtures): R32 `2A`→Group A's 4 teams sorted; `3rd A/B/C/D/F`→union of those 5 groups (20 teams); R16 home→`[r32-1.advanced_team]` (and `[]` when unset); third home→loser of sf-1; final home→winner of sf-1.
- `match_number`: all 32 seeded ids map to 73–104 (contiguous); unknown round→None.
- Admin (logged in via the existing admin-login POST, or by setting `session['is_admin']`): `/admin` renders `<select name="home_team">` with narrowed `<option>`s (e.g. Group A teams for r32-1) and `M73` labels.
- `M73`/`M89`/`M104` appear on `/bracket`; `M…` on dashboard (logged in).
- Reset any test data; `data.json` gitignored.

## 7. Out of scope (YAGNI)

Auto-filling R16+ teams (admin still selects from the narrowed list), roster validation in the save route beyond the dropdown, group narrowing anywhere but the admin team boxes, the predict page's existing advance dropdown, and any stored match-number/teams field.
