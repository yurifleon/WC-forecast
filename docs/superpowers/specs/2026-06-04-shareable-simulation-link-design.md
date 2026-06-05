# Shareable Simulation Link — Design

**Date:** 2026-06-04
**Status:** Approved

## Goal

Let a logged-in user share a **read-only snapshot** of their bracket simulator via a
link that anyone can open (no login) and that **expires 7 days** after it is created.
Sharing freezes the bracket as-is; later edits to the owner's live sim do not change
what an already-created link shows. Users can see and **revoke** their active links.

## Placement & access

- New public route `GET /s/<token>` — read-only, **no login required**.
- "Save & share" button + a "Shared links" management section added to `/simulator`
  (login required, owner-only actions).
- The read-only view reuses the existing bracket tree layout and CSS (`.bracket`,
  `.round`, `.bracket-match`, the `:is()` connector pseudo-elements from `base.html`)
  so it reads like `/bracket` and `/simulator`, but with no forms/dropdowns/buttons.

## Data model

New top-level key in `data.json`, seeded by `migrate_data()`
(`data.setdefault("shared_sims", {})`):

```jsonc
"shared_sims": {
  "<token>": {                          // token = secrets.token_urlsafe(8), unique
    "owner":       "yuri",              // username who created it
    "created_utc": "2026-06-04T18:00:00+00:00",
    "expires_utc": "2026-06-11T18:00:00+00:00",   // created + 7 days
    "sim": {                            // DEEP COPY, frozen at share time
      "r32":     { "r32-1": {"home": "Mexico", "away": "Canada"}, ... },
      "winners": { "r32-1": "Mexico", ... }
    }
  }
}
```

- The `sim` is a **deep copy** of the owner's sim at share time (built by a small
  explicit copy of the known `{"r32": {...}, "winners": {...}}` shape — no shared
  references with the live sim).
- Snapshots are **frozen**: they are **never** run through `_prune_sim()` and never
  mutated after creation. They render exactly as captured, even if `GROUPS`/teams
  later change.
- Timestamps are tz-aware **UTC** ISO strings (consistent with the rest of the app);
  rendered via `DISPLAY_TZ` only if shown, but expiry math is done in UTC.

## Interaction

All owner actions are no-JS form POSTs to `/simulator` (PRG, consistent with the
project's no-custom-JS rule).

- **Save & share** (`action=share`): deep-copies the current sim, generates a unique
  token, stamps `created_utc` / `expires_utc` (= created + 7 days), stores it,
  `save_data`, and flashes the new absolute URL
  (`url_for("shared_view", token=token, _external=True)`) for the user to copy.
  - **Guard:** refuse to share a completely empty bracket (no R32 picks and no
    winners) — `flash(..., "warning")`, create nothing.
  - **Cap:** at most **10 active** (non-expired) shares per user; over the cap, flash
    a warning telling them to revoke an old one first.
- **Shared links section:** lists the current user's active shares, newest first —
  each row shows the copyable absolute URL, "Expires in N days", and a **Revoke**
  button (`action=revoke`, `token` field). Revoke deletes the snapshot immediately
  (owner-checked: a token whose `owner` ≠ current user is ignored).

## Read-only view (`GET /s/<token>`)

- Looks up `data["shared_sims"][token]`.
- **Missing or expired → one generic response:** a friendly "This shared bracket has
  expired or doesn't exist" page returned with **HTTP 404** (same page for both cases
  so token existence isn't leaked). If the token was found-but-expired, it is purged
  and saved on the way out.
- **Valid →** renders the frozen bracket as a read-only tree: build `columns` over
  `["r32","r16","qf","sf","final"]` and `third` separately, each match resolved
  through `_sim_view(snapshot_sim, match, by_id)` where `by_id` comes from the current
  `data["matches"]` (structure only — round + feeders are stable). The template shows
  `home_display`/`away_display`/`winner` but **ignores the `*_pool` fields** (no
  dropdowns). Header reads "Shared by <owner>" and "Expires in N days".

## Expiry cleanup (no cron)

`_purge_expired_shares(data, now)` removes every snapshot whose `expires_utc` is in the
past (`now = get_cached_time()`), returning whether anything changed. It runs on the
routes that already write:

- `/simulator` GET — purge, and `save_data` if changed (also self-heals the owner's
  list so expired links never display).
- `/s/<token>` — when the requested token is found-but-expired, delete it + `save_data`
  before returning the 404 page.

No purge in `migrate_data` (keeps load read-only); the two write paths above are
sufficient for a ≤20-user game.

## Server pieces (`app.py`)

- `_create_share(data, username, sim)` → token. Deep-copies `sim`, stamps
  created/expires, ensures the token is unique against existing keys, stores it.
- `_user_shares(data, username, now)` → list of `{token, url, expires_utc, days_left}`
  for the user's **active** shares, newest first (for the template).
- `_purge_expired_shares(data, now)` → bool changed; drops expired snapshots.
- `_share_days_left(expires_utc, now)` → int, **ceil** of remaining days (so a link
  with 6 days 2 hours left shows "7 days"; ≤0 never shown because expired ones are
  filtered/purged). Returns 0 on an unparseable timestamp (treated as expired).
- `GET /s/<token>` → `shared_view` (public).
- `/simulator` POST gains `action` ∈ {`share`, `revoke`} alongside the existing
  {`set_teams`, `pick_winner`, `reset`}.
- Template `shared.html` — read-only tree (no forms). `simulator.html` gains the
  "Save & share" button and "Shared links" section.
- i18n: new UI strings go through `translate()`; Spanish added to `translations.py`
  ("Save & share", "Shared links", "Expires in {n} days", "Revoke", "Shared by {user}",
  "This shared bracket has expired or doesn't exist", "Copy this link to share:",
  "Nothing to share yet — make some picks first.", share-cap warning).

## Out of scope (YAGNI)

- No live-mirror links (snapshots are frozen by design).
- No editing, commenting, or scoring of a shared snapshot.
- No e-mail/social sharing integration — we only produce the URL to copy.
- No analytics on who/when a link was viewed.
- No custom titles/names on a snapshot.

## Edge cases

- **Empty share** blocked with a warning (nothing to look at).
- **Token collision** — regenerate until unique (probability negligible at this scale).
- **Expired link** and **never-existed link** are indistinguishable to the viewer
  (same 404 page).
- **Revoke of someone else's token** is a no-op (owner check), as is revoking an
  unknown/already-expired token.
- **Snapshot referencing a team later removed from `GROUPS`** still renders as
  captured — snapshots are deliberately not pruned.
- **Owner deleted** (admin removes the user): their shares are orphaned but still
  valid until they expire; optional — user-removal cleanup may also drop
  `data["shared_sims"]` entries owned by that user (mirrors the existing predictions
  orphan-cleanup rule). Included as a small addition to the user-removal path.
- **Clock/timestamp unparseable** on a snapshot → treated as expired (fail-closed,
  consistent with the app's lock/deadline philosophy).
