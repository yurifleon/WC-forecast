# FIFA World Cup 2026 Master Guide

> ⚠️ **THE KNOCKOUT BRACKET FEED IN THIS GUIDE IS WRONG — do not use it for topology.**
> The "Knockout Bracket" section shows a fully *sequential* feed (e.g. M89 = W73 v W74,
> M101 = W97 v W98). The real FIFA WC2026 bracket is **non-sequential** at R16 **and** QF.
> Authoritative sources: `knockout-round.md` (R16, M89–M96: M89 = W73 v **W75**) and
> Wikipedia "2026 FIFA World Cup knockout stage" (QF, M97–M100: **M98 = W93 v W94,
> M99 = W91 v W92**). SF onward *are* sequential. The app encodes the correct feed in
> `_R16_FEED` / `_QF_FEED` (app.py) — see commit 752e05a. Groups, venues, dates, and
> the R32 matchups here are fine; only the downstream **feeds** are wrong.

## Tournament Overview

* Hosts: Canada, Mexico, United States
* Teams: 48
* Groups: 12 (A-L)
* Group Format: 12 groups of 4 teams
* Advancement: Top 2 teams from each group plus the 8 best third-place teams advance to the Round of 32.

---

# Group A

* Mexico
* South Africa
* South Korea
* Czechia

# Group B

* Canada
* Bosnia and Herzegovina
* Qatar
* Switzerland

# Group C

* Brazil
* Morocco
* Haiti
* Scotland

# Group D

* United States
* Paraguay
* Australia
* Türkiye

# Group E

* Germany
* Ecuador
* Côte d'Ivoire
* Curaçao

# Group F

* Netherlands
* Japan
* Sweden
* Tunisia

# Group G

* Belgium
* Egypt
* Iran
* New Zealand

# Group H

* Spain
* Uruguay
* Saudi Arabia
* Cape Verde

# Group I

* France
* Senegal
* Norway
* Iraq

# Group J

* Argentina
* Austria
* Algeria
* Jordan

# Group K

* Portugal
* Colombia
* Uzbekistan
* DR Congo

# Group L

* England
* Croatia
* Ghana
* Panama

---

# All 48 Participating Nations

| Country                | Group |
| ---------------------- | ----- |
| Algeria                | J     |
| Argentina              | J     |
| Australia              | D     |
| Austria                | J     |
| Belgium                | G     |
| Bosnia and Herzegovina | B     |
| Brazil                 | C     |
| Canada                 | B     |
| Cape Verde             | H     |
| Colombia               | K     |
| Croatia                | L     |
| Curaçao                | E     |
| Côte d'Ivoire          | E     |
| Czechia                | A     |
| DR Congo               | K     |
| Ecuador                | E     |
| Egypt                  | G     |
| England                | L     |
| France                 | I     |
| Germany                | E     |
| Ghana                  | L     |
| Haiti                  | C     |
| Iran                   | G     |
| Iraq                   | I     |
| Japan                  | F     |
| Jordan                 | J     |
| Mexico                 | A     |
| Morocco                | C     |
| Netherlands            | F     |
| New Zealand            | G     |
| Norway                 | I     |
| Panama                 | L     |
| Paraguay               | D     |
| Portugal               | K     |
| Qatar                  | B     |
| Saudi Arabia           | H     |
| Scotland               | C     |
| Senegal                | I     |
| South Africa           | A     |
| South Korea            | A     |
| Spain                  | H     |
| Sweden                 | F     |
| Switzerland            | B     |
| Tunisia                | F     |
| Türkiye                | D     |
| United States          | D     |
| Uruguay                | H     |
| Uzbekistan             | K     |

---

# Round of 32

| Match | Date   | Time        | City                   | Teams                      |
| ----- | ------ | ----------- | ---------------------- | -------------------------- |
| M73   | Jun 28 | 12:00 PM PT | Los Angeles            | 2A vs 2B                   |
| M74   | Jun 29 | 4:30 PM ET  | Boston                 | 1E vs Best 3rd (A/B/C/D/F) |
| M75   | Jun 29 | 7:00 PM MT  | Monterrey              | 1F vs 2C                   |
| M76   | Jun 29 | 12:00 PM CT | Houston                | 1C vs 2F                   |
| M77   | Jun 29 | 5:00 PM ET  | New York/New Jersey    | 1I vs Best 3rd (C/D/F/G/H) |
| M78   | Jun 30 | 12:00 PM CT | Dallas                 | 2E vs 2I                   |
| M79   | Jun 30 | 7:00 PM CT  | Mexico City            | 1A vs Best 3rd (C/E/F/H/I) |
| M80   | Jun 30 | 12:00 PM ET | Atlanta                | 1L vs Best 3rd (E/H/I/J/K) |
| M81   | Jun 30 | 5:00 PM PT  | San Francisco Bay Area | 1D vs Best 3rd (B/E/F/I/J) |
| M82   | Jul 1  | 1:00 PM PT  | Seattle                | 1G vs Best 3rd (A/E/H/I/J) |
| M83   | Jul 2  | 7:00 PM ET  | Toronto                | 2K vs 2L                   |
| M84   | Jul 2  | 12:00 PM PT | Los Angeles            | 1H vs 2J                   |
| M85   | Jul 2  | 8:00 PM PT  | Vancouver              | 1B vs Best 3rd (E/F/G/I/J) |
| M86   | Jul 3  | 6:00 PM ET  | Miami                  | 1J vs 2H                   |
| M87   | Jul 3  | 8:30 PM CT  | Kansas City            | 1K vs Best 3rd (D/E/I/J/L) |
| M88   | Jul 3  | 1:00 PM CT  | Dallas                 | 2D vs 2G                   |

---

# Round of 16

| Match | Date  | Time        | City         | Teams                    |
| ----- | ----- | ----------- | ------------ | ------------------------ |
| M89   | Jul 5 | 12:00 PM ET | Philadelphia | Winner M73 vs Winner M74 |
| M90   | Jul 5 | 5:00 PM ET  | Houston      | Winner M75 vs Winner M76 |
| M91   | Jul 6 | 3:00 PM CT  | Mexico City  | Winner M77 vs Winner M78 |
| M92   | Jul 6 | 2:00 PM CT  | Dallas       | Winner M79 vs Winner M80 |
| M93   | Jul 7 | 12:00 PM ET | Atlanta      | Winner M81 vs Winner M82 |
| M94   | Jul 7 | 7:30 PM PT  | Seattle      | Winner M83 vs Winner M84 |
| M95   | Jul 8 | 3:00 PM ET  | Miami        | Winner M85 vs Winner M86 |
| M96   | Jul 8 | 6:00 PM CT  | Guadalajara  | Winner M87 vs Winner M88 |

---

# Quarterfinals

| Match | Date   | Time       | City        | Teams                    |
| ----- | ------ | ---------- | ----------- | ------------------------ |
| M97   | Jul 9  | 5:00 PM ET | Boston      | Winner M89 vs Winner M90 |
| M98   | Jul 10 | 6:00 PM PT | Los Angeles | Winner M91 vs Winner M92 |
| M99   | Jul 11 | 4:00 PM CT | Kansas City | Winner M93 vs Winner M94 |
| M100  | Jul 11 | 4:00 PM ET | Miami       | Winner M95 vs Winner M96 |

---

# Semifinals

| Match | Date   | Time       | City    | Teams                     |
| ----- | ------ | ---------- | ------- | ------------------------- |
| M101  | Jul 14 | 8:00 PM CT | Dallas  | Winner M97 vs Winner M98  |
| M102  | Jul 15 | 8:00 PM ET | Atlanta | Winner M99 vs Winner M100 |

---

# Third Place Match

| Match | Date   | Time       | City  | Teams                    |
| ----- | ------ | ---------- | ----- | ------------------------ |
| M103  | Jul 18 | 3:00 PM ET | Miami | Loser M101 vs Loser M102 |

---

# Final

| Match | Date   | Time       | City                        | Teams                      |
| ----- | ------ | ---------- | --------------------------- | -------------------------- |
| M104  | Jul 19 | 3:00 PM ET | East Rutherford, New Jersey | Winner M101 vs Winner M102 |

---

# Knockout Bracket

```text
M73 ─┐
     ├─ M89 ─┐
M74 ─┘       │
             ├─ M97 ─┐
M75 ─┐       │       │
     ├─ M90 ─┘       │
M76 ─┘               │
                     ├─ M101 ─┐
M77 ─┐               │        │
     ├─ M91 ─┐       │        │
M78 ─┘       │       │        │
             ├─ M98 ─┘        │
M79 ─┐       │                │
     ├─ M92 ─┘                │
M80 ─┘                        │
                              ├─ M104
M81 ─┐                        │
     ├─ M93 ─┐                │
M82 ─┘       │                │
             ├─ M99 ─┐        │
M83 ─┐       │       │        │
     ├─ M94 ─┘       │        │
M84 ─┘               │        │
                     ├─ M102 ─┘
M85 ─┐               │
     ├─ M95 ─┐       │
M86 ─┘       │       │
             ├─ M100 ┘
M87 ─┐       │
     ├─ M96 ─┘
M88 ─┘

Third Place:
M103 = Loser M101 vs Loser M102
```

---

# Tournament Timeline

| Round         | Dates                 |
| ------------- | --------------------- |
| Group Stage   | Jun 11 – Jun 27, 2026 |
| Round of 32   | Jun 28 – Jul 3, 2026  |
| Round of 16   | Jul 5 – Jul 8, 2026   |
| Quarterfinals | Jul 9 – Jul 11, 2026  |
| Semifinals    | Jul 14 – Jul 15, 2026 |
| Third Place   | Jul 18, 2026          |
| Final         | Jul 19, 2026          |

EOF

