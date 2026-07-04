# FIFA World Cup 2026 Knockout Stage Schedule

> ⚠️ **THE MATCHUP FEEDS BELOW ARE WRONG — do not use them for topology.** This doc
> shows the knockout feed as fully *sequential* (e.g. M89 = W73 v W74, M101 = W97 v W98).
> The real FIFA WC2026 bracket is **non-sequential** at R16 **and** QF. Authoritative
> sources: `knockout-round.md` (R16, M89–M96: M89 = W73 v **W75**) and Wikipedia
> "2026 FIFA World Cup knockout stage" (QF, M97–M100: **M98 = W93 v W94, M99 = W91 v
> W92**). SF onward *are* sequential. The app encodes the correct feed in `_R16_FEED` /
> `_QF_FEED` (app.py) — see commit 752e05a. Dates/venues here may still be useful; the
> matchup **feeds** are not.

## Round of 16

| Match | Date         | Time (Local) | City                    | Teams                    |
| ----- | ------------ | ------------ | ----------------------- | ------------------------ |
| M89   | July 5, 2026 | 12:00 PM ET  | Philadelphia, USA       | Winner M73 vs Winner M74 |
| M90   | July 5, 2026 | 5:00 PM ET   | Houston, USA            | Winner M75 vs Winner M76 |
| M91   | July 6, 2026 | 3:00 PM CT   | Mexico City, Mexico     | Winner M77 vs Winner M78 |
| M92   | July 6, 2026 | 2:00 PM CT   | Arlington (Dallas), USA | Winner M79 vs Winner M80 |
| M93   | July 7, 2026 | 12:00 PM ET  | Atlanta, USA            | Winner M81 vs Winner M82 |
| M94   | July 7, 2026 | 7:30 PM PT   | Seattle, USA            | Winner M83 vs Winner M84 |
| M95   | July 8, 2026 | 3:00 PM ET   | Miami, USA              | Winner M85 vs Winner M86 |
| M96   | July 8, 2026 | 6:00 PM CT   | Guadalajara, Mexico     | Winner M87 vs Winner M88 |

---

## Quarterfinals

| Match | Date          | Time (Local) | City             | Teams                    |
| ----- | ------------- | ------------ | ---------------- | ------------------------ |
| M97   | July 9, 2026  | 5:00 PM ET   | Boston, USA      | Winner M89 vs Winner M90 |
| M98   | July 10, 2026 | 6:00 PM PT   | Los Angeles, USA | Winner M91 vs Winner M92 |
| M99   | July 11, 2026 | 4:00 PM CT   | Kansas City, USA | Winner M93 vs Winner M94 |
| M100  | July 11, 2026 | 4:00 PM ET   | Miami, USA       | Winner M95 vs Winner M96 |

---

## Semifinals

| Match | Date          | Time (Local) | City                    | Teams                     |
| ----- | ------------- | ------------ | ----------------------- | ------------------------- |
| M101  | July 14, 2026 | 8:00 PM CT   | Arlington (Dallas), USA | Winner M97 vs Winner M98  |
| M102  | July 15, 2026 | 8:00 PM ET   | Atlanta, USA            | Winner M99 vs Winner M100 |

---

## Third-Place Match

| Match | Date          | Time (Local) | City       | Teams                    |
| ----- | ------------- | ------------ | ---------- | ------------------------ |
| M103  | July 18, 2026 | 3:00 PM ET   | Miami, USA | Loser M101 vs Loser M102 |

---

## Final

| Match | Date          | Time (Local) | City                                   | Teams                      |
| ----- | ------------- | ------------ | -------------------------------------- | -------------------------- |
| M104  | July 19, 2026 | 3:00 PM ET   | East Rutherford (MetLife Stadium), USA | Winner M101 vs Winner M102 |

---

## Knockout Bracket Flow

```text
ROUND OF 16

M89  Winner M73 vs Winner M74
M90  Winner M75 vs Winner M76
M91  Winner M77 vs Winner M78
M92  Winner M79 vs Winner M80
M93  Winner M81 vs Winner M82
M94  Winner M83 vs Winner M84
M95  Winner M85 vs Winner M86
M96  Winner M87 vs Winner M88

QUARTERFINALS

M97  Winner M89 vs Winner M90
M98  Winner M91 vs Winner M92
M99  Winner M93 vs Winner M94
M100 Winner M95 vs Winner M96

SEMIFINALS

M101 Winner M97 vs Winner M98
M102 Winner M99 vs Winner M100

THIRD PLACE

M103 Loser M101 vs Loser M102

FINAL

M104 Winner M101 vs Winner M102
```

---

## Tournament Timeline

| Round             | Dates                   |
| ----------------- | ----------------------- |
| Round of 32       | June 28 – July 3, 2026  |
| Round of 16       | July 5 – July 8, 2026   |
| Quarterfinals     | July 9 – July 11, 2026  |
| Semifinals        | July 14 – July 15, 2026 |
| Third-Place Match | July 18, 2026           |
| Final             | July 19, 2026           |
|                   |                         |

