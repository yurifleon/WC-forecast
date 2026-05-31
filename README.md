# WC Forecast ⚽

A private **FIFA World Cup 2026 knockout-stage** prediction game for a group of
friends. Predict full-time scorelines (and who advances on penalties) across the
Round of 32 → Final; a live leaderboard ranks everyone.

Built on the lessons from **UCL Forecast** — see `FIFA_WC_LESSONS_LEARNED.md` in
the sibling `UCL-forecast` repo for the full design rationale.

## Quick start

```bash
python3 -m venv .venv
source .venv/bin/activate          # .venv\Scripts\activate on Windows
pip install -r requirements.txt
python3 app.py                     # http://localhost:5000  (PORT env var overrides)
```

First run seeds the full 32-match knockout bracket (Round of 32 → Final) with
**TBD** teams. Log in to `/admin` (default password `change-me-admin`) to fill in
team names, kickoff times, and results as the tournament unfolds.

## How it works

- **Register / log in** with a username + password (max 20 players, configurable).
- **Predict** any match that has both teams set and hasn't kicked off: enter the
  full-time score, and pick who advances (covers penalty shootouts).
- **Admin** sets each match's teams + kickoff, then enters the result and the
  advancing team. Matches lock automatically at kickoff.
- **Scoring** (per match, by round):

  | Outcome | R32 | R16 | QF | SF | Final/3rd |
  |---|---|---|---|---|---|
  | Exact score | 6 | 7 | 8 | 9 | 10 |
  | Result + goal difference | 4 | 5 | 5 | 6 | 7 |
  | Result only | 2 | 3 | 3 | 4 | 5 |
  | Correct advancing team (added) | +2 | +2 | +3 | +3 | +4 |

  The advance pick is scored **separately** so a penalty shootout can't zero a
  correct scoreline.

## Configuration (env vars)

| Var | Default | Purpose |
|-----|---------|---------|
| `DATA_DIR` | project dir | Where `data.json` lives. **Set to a Render persistent disk (e.g. `/data`) before the first signup** or data is wiped on each deploy. |
| `SECRET_KEY` | dev fallback | Flask session secret. **Set in production.** |
| `ADMIN_PASSWORD` | value in `data.json` | Admin panel password; set in Render to avoid editing data. |
| `DISPLAY_TZ` | `America/Lima` | Timezone deadlines are shown in and admin input is interpreted as. |
| `DISPLAY_TZ_LABEL` | `LIM` | Label shown next to times. |
| `MAX_USERS` | `20` | Registration cap. |
| `PORT` | `5000` | HTTP port (Render sets this). |

> **Timezones:** deadlines are stored as timezone-aware **UTC** and converted to
> `DISPLAY_TZ` only for display. This is the deliberate fix for the bug that broke
> UCL locking five times — don't reintroduce naive local datetimes.

## Deploy (Render)

`Procfile` runs gunicorn. Push to the branch Render watches:

```bash
git push origin master
```

Mount a persistent disk at `/data` and set `DATA_DIR=/data`. Back up by copying
`data.json` periodically (no automated backups).

## Project layout

```
app.py              # entire backend: routes, scoring, data layer, auth, i18n wiring
translations.py     # Spanish translation dictionary
templates/          # Jinja2 templates (Bootstrap 5.3 dark theme, no custom JS)
data.json           # gitignored; all state (created on first run)
```

## Status & roadmap

- ✅ **Knockout stage** (this build): R32 → Final, predictions, scoring, leaderboard,
  bracket, admin, EN/ES.
- ⬜ Group stage + standings (not built — this group plays knockout only).
- ⬜ Email-based self-service password reset (admin can reset passwords today).
- ⬜ Champion / top-scorer pre-tournament bonus.

There is no test suite; syntax-check with `python -m py_compile app.py`.
