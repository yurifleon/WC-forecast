# Leaderboard matchup abbreviations — design

**Date:** 2026-06-30
**Status:** Approved (pending spec review)

## Goal

In the `/leaderboard` per-match matrix, replace the match-number column headers
(`M73`…`M104`) with the **country matchup** as short codes (e.g. `CAN-MEX`),
using language-specific 3-letter abbreviations (English vs Spanish). Matches
whose teams aren't set yet keep the match number as a fallback.

## Non-goals

- No change to scoring, the per-round summary table, or the data model.
- No new translated `_()` copy — the codes are reference data, not UI strings.
- No change to any page other than the leaderboard matrix header.

## Decisions (from brainstorming)

1. **Separate EN + ES codes**, chosen by the current request language.
2. **Fallback = match number** (`M{n}`) until both teams of a match are known.

## Changes

### 1. Data — `TEAM_ABBR` (app.py, near `GROUPS`)

A dict keyed by the **canonical team name** (exact `GROUPS` spelling, e.g.
`"Côte d'Ivoire"`, `"United States"`, `"DR Congo"`, `"Türkiye"`) →
`(en_code, es_code)` tuple of 3-letter uppercase codes. All 48 nations covered.

Codes diverge only where usage differs; most are identical in both languages.
The full table (authoritative — implement exactly these):

| Team | EN | ES | | Team | EN | ES |
|------|----|----|-|------|----|----|
| Mexico | MEX | MEX | | Belgium | BEL | BEL |
| South Africa | RSA | SUD | | Egypt | EGY | EGI |
| South Korea | KOR | COR | | Iran | IRN | IRN |
| Czechia | CZE | CHQ | | New Zealand | NZL | NZL |
| Canada | CAN | CAN | | Spain | ESP | ESP |
| Bosnia and Herzegovina | BIH | BOS | | Uruguay | URU | URU |
| Qatar | QAT | QAT | | Saudi Arabia | KSA | ARS |
| Switzerland | SUI | SUI | | Cape Verde | CPV | CAV |
| Brazil | BRA | BRA | | France | FRA | FRA |
| Morocco | MAR | MAR | | Senegal | SEN | SEN |
| Haiti | HAI | HAI | | Norway | NOR | NOR |
| Scotland | SCO | ESC | | Iraq | IRQ | IRK |
| United States | USA | EUA | | Argentina | ARG | ARG |
| Paraguay | PAR | PAR | | Austria | AUT | AUT |
| Australia | AUS | AUS | | Algeria | ALG | ALG |
| Türkiye | TUR | TUR | | Jordan | JOR | JOR |
| Germany | GER | ALE | | Portugal | POR | POR |
| Ecuador | ECU | ECU | | Colombia | COL | COL |
| Côte d'Ivoire | CIV | CMF | | Uzbekistan | UZB | UZB |
| Curaçao | CUW | CUR | | DR Congo | COD | RDC |
| Netherlands | NED | HOL | | England | ENG | ING |
| Japan | JPN | JPN | | Croatia | CRO | CRO |
| Sweden | SWE | SUE | | Ghana | GHA | GHA |
| Tunisia | TUN | TUN | | Panama | PAN | PAN |

Deliberate collision avoidance: **Algeria = ALG in ES** (not `ARG`, which is
Argentina); **Czechia = CHQ** (not `CHE`, to stay clear of Switzerland `SUI`).

### 2. Helpers — app.py

```python
def team_abbr(team, lang):
    """3-letter code for a team in the given language.
    Falls back to the first 3 letters uppercased for unknown teams."""
    codes = TEAM_ABBR.get(team)
    if codes is None:
        return (team or "")[:3].upper()
    return codes[1] if lang == "es" else codes[0]


def match_short(match):
    """Column label for the leaderboard matrix header.
    'CAN-MEX' when both real teams are set, else the 'M{n}' match number."""
    if has_teams(match):
        lang = getattr(g, "lang", "en")
        return f"{team_abbr(match['home_team'], lang)}-{team_abbr(match['away_team'], lang)}"
    return f"M{match_number(match)}"
```

Notes:
- `has_teams(match)` already returns True only when both `home_team` and
  `away_team` are set, so `match_short` reads them directly (not via
  `slot_label`, which could return an origin/placeholder code).
- `match_short` resolves language from `g.lang` (set per request in
  `before_request`), matching how `translate()` / the injected `lang` value
  work. No `lang` parameter needed at the call site.
- Both helpers live near the other team/label helpers (`team_options`,
  `slot_label`, `match_number`).

### 3. Template injection — `inject_i18n_helpers` (app.py)

Add `match_short` to the context processor dict (alongside `slot_label`,
`match_number`, etc.) so templates can call it. `team_abbr` need not be
injected (only used by `match_short`).

### 4. Template — `templates/leaderboard.html` (matrix header only)

Current:
```jinja
<th class="text-center" title="{{ slot_label(m, 'home') }} vs {{ slot_label(m, 'away') }}">
  M{{ match_number(m) }}
</th>
```
New:
```jinja
<th class="text-center" title="{{ slot_label(m, 'home') }} vs {{ slot_label(m, 'away') }} · M{{ match_number(m) }}">
  {{ match_short(m) }}
</th>
```
The tooltip keeps the full country names and now appends the match number so
that information is not lost when the header switches to the matchup code.

## Testing / verification

- `python -m py_compile app.py`.
- Behavior check for `match_short` / `team_abbr`:
  - EN: a match with `home_team="Germany"`, `away_team="Spain"` → `GER-ESP`;
    ES → `ALE-ESP`.
  - EN: `England` vs `Croatia` → `ENG-CRO`; ES → `ING-CRO`.
  - A match with `home_team=None` → `M{match_number}` (e.g. `M89`) in both langs.
  - Unknown team `"Wakanda"` → `WAK` (fallback).
- Coverage check: every team in `GROUPS` (all 48) has a `TEAM_ABBR` entry.
- Manual: load `/leaderboard` in EN and ES — R32 columns show matchup codes,
  R16+ columns show `M89`…`M104`; hover shows full names + match number.

## Risks

- **Missing team in `TEAM_ABBR`** → the fallback (`team[:3].upper()`) prevents a
  crash; the coverage check catches gaps at build time.
- **Abbreviation collisions within a single matchup** are cosmetic only (two
  different teams can't share the same canonical name, so the two codes in a
  matchup are independently looked up; identical codes across *different*
  matches are harmless).
