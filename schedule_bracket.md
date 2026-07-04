# FIFA World Cup 2026 Knockout Bracket

> ⚠️ **THE BRACKET FEED BELOW IS WRONG — do not use it for topology.** This doc shows
> the knockout feed as fully *sequential* (e.g. M89 = W73 v W74, M101 = W97 v W98). The
> real FIFA WC2026 bracket is **non-sequential** at R16 **and** QF. Authoritative
> sources: `knockout-round.md` (R16, M89–M96: M89 = W73 v **W75**) and Wikipedia
> "2026 FIFA World Cup knockout stage" (QF, M97–M100: **M98 = W93 v W94, M99 = W91 v
> W92**). SF onward *are* sequential. The app encodes the correct feed in `_R16_FEED` /
> `_QF_FEED` (app.py) — see commit 752e05a. Dates/venues here may still be useful; the
> matchup **feeds** are not.

## From Round of 32 to the Final

```
ROUND OF 32                          ROUND OF 16               QUARTERFINALS          SEMIFINALS           FINAL

M73: 2A vs 2B ───────┐
                      ├─ W89 ───────┐
M74: 1E vs 3rd ABCDF ┘              │
                                     ├─ W97 ───────┐
M75: 1F vs 2C ───────┐              │              │
                      ├─ W90 ───────┘              │
M76: 1C vs 2F ───────┘                             │
                                                    ├─ W101 ──────┐
M77: 1I vs 3rd CDFGH ┐                             │              │
                      ├─ W91 ───────┐              │              │
M78: 2E vs 2I ───────┘              │              │              │
                                     ├─ W98 ───────┘              │
M79: 1A vs 3rd CEFHI ┐              │                             │
                      ├─ W92 ───────┘                             │
M80: 1L vs 3rd EHIJK ┘                                            │
                                                                   ├─ CHAMPION
M81: 1D vs 3rd BEFIJ ┐                                            │
                      ├─ W93 ───────┐                             │
M82: 1G vs 3rd AEHIJ ┘              │                             │
                                     ├─ W99 ───────┐              │
M83: 2K vs 2L ───────┐              │              │              │
                      ├─ W94 ───────┘              │              │
M84: 1H vs 2J ───────┘                             │              │
                                                    ├─ W102 ──────┘
M85: 1B vs 3rd EFGIJ ┐                             │
                      ├─ W95 ───────┐              │
M86: 1J vs 2H ───────┘              │              │
                                     ├─ W100 ──────┘
M87: 1K vs 3rd DEIJL ┐              │
                      ├─ W96 ───────┘
M88: 2D vs 2G ───────┘
```

## Round of 16

| Match | Teams                    |
| ----- | ------------------------ |
| M89   | Winner M73 vs Winner M74 |
| M90   | Winner M75 vs Winner M76 |
| M91   | Winner M77 vs Winner M78 |
| M92   | Winner M79 vs Winner M80 |
| M93   | Winner M81 vs Winner M82 |
| M94   | Winner M83 vs Winner M84 |
| M95   | Winner M85 vs Winner M86 |
| M96   | Winner M87 vs Winner M88 |

## Quarterfinals

| Match | Teams                    |
| ----- | ------------------------ |
| M97   | Winner M89 vs Winner M90 |
| M98   | Winner M91 vs Winner M92 |
| M99   | Winner M93 vs Winner M94 |
| M100  | Winner M95 vs Winner M96 |

## Semifinals

| Match | Teams                     |
| ----- | ------------------------- |
| M101  | Winner M97 vs Winner M98  |
| M102  | Winner M99 vs Winner M100 |

## Third Place Match

| Match | Teams                    |
| ----- | ------------------------ |
| M103  | Loser M101 vs Loser M102 |

## Final

| Match | Teams                      |
| ----- | -------------------------- |
| M104  | Winner M101 vs Winner M102 |

## Host Cities for Later Rounds

### Round of 16

* Philadelphia
* Houston
* Mexico City
* Dallas
* Atlanta
* Seattle
* Miami
* Guadalajara

### Quarterfinals

* Boston
* Los Angeles
* Kansas City
* Miami

### Semifinals

* Dallas
* Atlanta

### Third Place Match

* Miami

### Final

* New York / New Jersey (MetLife Stadium)

```
MetLife Stadium
East Rutherford, New Jersey, USA
July 19, 2026
FIFA World Cup 2026 Final
```

