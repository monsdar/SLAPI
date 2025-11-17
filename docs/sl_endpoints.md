# TeamSL Upstream Endpoints

This document catalogs the publicly accessible endpoints exposed by the upstream TeamSL platform at [basketball-bund.net](https://www.basketball-bund.net) and summarizes the request/response patterns we can rely on when building features that proxy or normalize their data.

---

## REST JSON APIs

### `GET /rest/competition/spielplan/id/{ligaId}`
Returns the complete season schedule for a specific league (`ligaId`). The payload always follows the envelope below:

```json
{
  "timestamp": "2025-11-15T20:20:11+0100",
  "status": 0,
  "message": null,
  "version": "11.42.2-5342324",
  "data": {
    "ligaData": { "... league metadata ..." },
    "matches": [
      {
        "matchId": 2688136,
        "matchDay": 1,
        "matchNo": 8303,
        "kickoffDate": "2025-09-13",
        "kickoffTime": "09:00",
        "homeTeam": { "teamname": "TuS Huchting", "clubId": 153, ... },
        "guestTeam": { "teamname": "TV Delmenhorst", "clubId": 1342, ... },
        "result": "76:64",
        "ergebnisbestaetigt": true,
        "abgesagt": false
      }
    ],
    "... additional keys (tabelle, kreuztabelle, etc.) ..."
  }
}
```

Key points (observed during live calls on 2025‑11‑15):

- `ligaData` contains identifiers (league, season, governing association, cross-table availability flags, etc.).
- `matches[]` always covers the full season, mixing finished games (`result` string) with scheduled ones (`result`: `null`). There is no paging or date filtering server-side—clients must slice data themselves.
- Team objects provide both display names (`teamname`, `teamnameSmall`) and identifiers (`teamPermanentId`, `seasonTeamId`, `clubId`), which is useful when correlating standings and schedules.

Source: [basketball-bund.net](https://www.basketball-bund.net/rest/competition/spielplan/id/48714)

---

### `GET /rest/competition/actual/id/{ligaId}`
Returns the *current* state for a league, combining the latest/next fixtures with the standings table:

- Response envelope matches the schedule API (`timestamp`, `status`, etc.).
- `data.matches` usually holds the most recent or upcoming match days (not the entire season), mirroring what the website shows under “Aktuell”.
- `data.tabelle.entries` is an ordered list of teams with win/loss counters (`s`, `n`), points (`anzGewinnpunkte`/`anzVerlustpunkte`), basket stats (`koerbe`, `gegenKoerbe`, `korbdiff`), and the embedded `team` object.
- `data.ligaData.actualMatchDay` indicates the match day currently highlighted on the website.

This endpoint is best suited when we only need “current standings + near-term fixtures” without downloading the entire schedule.

Source: [basketball-bund.net](https://www.basketball-bund.net/rest/competition/actual/id/48714)

---

### `POST /rest/wam/data`
Backend used by the Angular/SPA league finder. A plain `GET` returns HTTP 405 (Method Not Allowed); requests must be JSON `POST`s with `Content-Type: application/json`.

#### Request shape

- Filters live at the top level. Any of the following keys may be provided with arrays of IDs (as numbers or strings, depending on the list): `verbandIds`, `gebietIds`, `ligatypIds`, `spielklasseIds`, `altersklasseIds`, `akgGeschlechtIds`.
- `sortBy` controls ordering (default `1` = by association/league hierarchy).
- `token` is reserved for the frontend but currently `null`; no token is required for public access.
- Example: restrict leagues to Bezirk “Region Lüneburg” by sending `{"gebietIds": ["102_"]}`. The response’s `data.wam` section simply echoes the active filters so you can verify what the server applied.

#### Response shape

```json
{
  "status": 0,
  "data": {
    "gebiete": [ { "id": "102_", "bezirk": "Region Lüneburg", "hits": 58 }, ... ],
    "verbaende": [ { "id": 7, "label": "Niedersachsen", "hits": 205 }, ... ],
    "ligatypen": [ ... ],
    "spielklassen": [ ... ],
    "altersklassen": [ ... ],
    "agkGeschlechtList": [ ... ],
    "ligaListe": {
      "hasMoreData": true,
      "startAtIndex": 0,
      "size": 10,
      "ligen": [
        {
          "ligaId": 51520,
          "liganame": "1. Bundesliga (easyCredit BBL)",
          "skEbeneName": "Verband",
          "akName": "Senioren",
          "geschlecht": "männlich",
          "verbandId": 100,
          "bezirkName": null,
          "tableExists": null,
          "crossTableExists": null
        },
        ...
      ]
    },
    "wam": { "gebietIds": ["102_"], "sortBy": 1, ... }
  }
}
```

Notes:

- `ligaListe.ligen` is limited to 10 rows per response today. The server advertises the presence of more data via `hasMoreData`, but the public API does not accept `startAtIndex`/`size` overrides (we attempted top-level `startAtIndex`, nested `ligaListe` objects, and combinations thereof—the response always falls back to `startAtIndex: 0`, `size: 10`). Plan to iterate by re-posting with stronger filters rather than true pagination.
- The supporting lists (`verbaende`, `gebiete`, `ligatypen`, etc.) include `hits` counters, which help drive faceted search UIs.
- Enumerating Verband IDs: issuing the request with an empty JSON body (`POST /rest/wam/data` + `{}`) returns the full list in `data.verbaende`. Each entry has `id` (numeric identifier), `label` (e.g., `"Niedersachsen"`, `"Bundesligen"`, `"Regionalliga West"`), and `hits` (how many leagues currently fall under that association). These IDs cover the 16 Bundesländer plus nationwide umbrella groupings (Bundesligen, Regionalligen, Deutsche Meisterschaften, Rollstuhlbasketball). Reuse these IDs for downstream calls by sending them in `verbandIds` arrays.

Source: [basketball-bund.net](https://www.basketball-bund.net/rest/wam/data)

---

## Legacy HTML Endpoints

### `POST /index.jsp?Action=100&Verband={verbandId}`
League search endpoint that allows finding all leagues a specific club participates in. This is the form submission endpoint for the league list page (`/index.jsp?Action=100&Verband=7`).

#### Access pattern

Submit a `POST` request with URL-encoded form data to search for leagues by club name. The club name is automatically URL-encoded (e.g., "Eisbären Bremerhaven" becomes "Eisb%C3%A4ren+Bremerhaven").

#### Request shape

Form data fields (all sent as `application/x-www-form-urlencoded`):

| Field name | Type | Purpose |
| --- | --- | --- |
| `Action` | hidden | Always `"100"` for league list view. |
| `Verband` | number | Association ID (e.g., `7` for Niedersachsen). |
| `search` | text | Club name to search for. Supports German umlauts (ä, ö, ü, ß) which are automatically URL-encoded. |
| `cbSpielklasseFilter` | number | League class filter. `"0"` = all classes. |
| `spieltyp_id` | number | Game type filter. `"0"` = all types. |
| `cbAltersklasseFilter` | number | Age group filter. `"0"` = all age groups. |
| `cbGeschlechtFilter` | number | Gender filter. `"0"` = all genders. |
| `cbBezirkFilter` | number | District filter. `"0"` = all districts. |
| `cbKreisFilter` | number | Sub-district filter. `"0"` = all sub-districts. |

Example request for "Eisbären Bremerhaven":
```
POST /index.jsp?Action=100&Verband=7
Content-Type: application/x-www-form-urlencoded

search=Eisb%C3%A4ren+Bremerhaven&cbSpielklasseFilter=0&spieltyp_id=0&cbAltersklasseFilter=0&cbGeschlechtFilter=0&cbBezirkFilter=0&cbKreisFilter=0
```

#### Session + pagination behavior (verified 2025‑11‑17)

- The website relies on a session cookie named `SESSION`. Always issue an initial `GET /index.jsp?Action=100&Verband={verbandId}` to let the server mint that cookie and to mirror the browser’s flow.
- The search `POST` **must** target `/index.jsp?Action=100&Verband={verbandId}` (query string included). Posting to `/index.jsp` without the query parameters causes the backend to ignore the filters and respond with the nationwide leagues (ProA, Bundesliga, etc.).
- After the initial `POST`, the backend stores the search result set server-side. Pagination links on the page are plain `GET`s such as `/index.jsp?Action=100&Verband=7&startrow=10`. Reusing the same `SESSION` cookie while incrementing `startrow` in steps of 10 yields the complete result list (page size is fixed at 10 rows).
- The summary text `Seite {current} / {total} ({hits} Treffer insgesamt)` appears above the table and can be parsed to know how many `startrow` offsets you need to request.
- No additional view identifiers were required in our tests; `startrow` plus the preserved cookie was sufficient to fetch all pages.
- Script reference: `scripts/test_club_league_search.py` automates this flow and currently returns 23 leagues for “Eisbären Bremerhaven” and 22 leagues for “1860 Bremen”, matching the interactive UI.

#### Response shape

The response is an HTML page containing a table with league information. Each row represents a league the club participates in.

Table columns (in order):
1. **Klasse** (League class/level) - e.g., "2. Bundesliga", "Jugend-Bundesliga"
2. **Alter** (Age group) - e.g., "Senioren", "U19"
3. **m/w** (Gender) - "männlich", "weiblich", or "mix"
4. **Bezirk** (District/region) - often empty for higher-level leagues
5. **Kreis** (Sub-district) - often empty for higher-level leagues
6. **Liganame** (League name) - e.g., "Herren ProA", "NBBL B - Gruppe Nord"
7. **Liganr** (League number) - numeric identifier

Each row contains links to league detail pages. The `liga_id` can be extracted from these links (e.g., `index.jsp?Action=102&liga_id=51529`).

#### Parsing tips

- The main data table is typically the largest table in the response or contains header cells with "Klasse", "Liganame", or "Liganr".
- League IDs are embedded in the `href` attributes of links within each row. Extract using regex pattern `liga_id=(\d+)`.
- Club names with German umlauts (ä, ö, ü) and special characters (ß) must be properly URL-encoded. HTTP clients like `httpx` handle this automatically when using the `data=` parameter.
- The response always paginates in blocks of 10 rows. Use the `Seite …` summary and the `startrow` links to iterate until all hits are collected (details above).

#### Use cases

This endpoint is particularly useful for:
- Discovering all leagues a club participates in across different age groups and genders
- Finding league IDs when you only know the club name
- Building club-to-league mappings for data aggregation

Source: [basketball-bund.net](https://www.basketball-bund.net/index.jsp?Action=100&Verband=7)

---

### `spielplanReportSearch.do`
Historical JSP-based report that still powers the “Spielplanreport” view on the legacy site. It is useful because it can list every match a club participates in—allowing you to discover all relevant league IDs even when the modern JSON APIs do not offer such a reverse lookup.

#### Access pattern

1. `GET /spielplanReportSearch.do` (optionally with `defaultview=1`) renders the form and all dropdowns (associations, districts, leagues, etc.).
2. Submitting the form posts to `/spielplanReportSearch.do?reqCode=list`. A simple URL-encoded POST with the fields below reproduces the website’s table. Example payload that lists every match for BG Bierden‑Bassen‑Achim:

```
defaultview=1
verbandBezirkKreisVereinSelection.bezirk_id=102
verbandBezirkKreisVereinSelection.kreis_id=0
verbandBezirkKreisVereinSelection.verein=BG Bierden-Bassen-Achim
liga_id=0
```

3. The response is an HTML table with sortable columns (`Liga`, `Nr.`, `Tag`, `Datum`, `Heim`, `Gast`, `Halle`). Navigation controls issue additional GET requests that keep the same filters but add control parameters such as `startrow`, `sort_<column>`, `topsort`, `kontakttype_id` (4 for club searches), and `object_id` (the encoded club string).

Key form fields (names confirmed from the rendered markup):

| Field name | Type | Purpose |
| --- | --- | --- |
| `defaultview` | hidden | Website uses `1` to toggle default layout—safe to keep. |
| `verbandBezirkKreisVereinSelection.bezirk_id` | select | Governing bezirk/region; drives the leagues shown in the `liga_id` dropdown. |
| `verbandBezirkKreisVereinSelection.kreis_id` | select | Optional sub-district (0 = all). |
| `verbandBezirkKreisVereinSelection.verein` | text | Club search field. Accepts literal names and wildcard characters (`*`) for substring matching. |
| `liga_id` | select | League filter. `0` means “all leagues within the chosen association/district”. |
| `mannschaft_liga_id` | select | Populated client-side when a league is chosen; lets you filter by a specific team entry. |
| `spielfeld_id` | select | Restricts the output to games played in a specific hall. |

Pagination & sorting:

- `startrow` controls the offset (defaults to `0`, increments in steps of 10 as seen in the navigation URLs).
- Sorting is driven by query params like `sort_liganame=asc` together with `topsort=liganame`. Replace `liganame` with `spielnr`, `spieltag`, `spieldatum_sort`, `heimmannschaft`, `gastmannschaft`, or `spielfeld`.
- Additional links keep `kontakttype_id=4` and `object_id=<club>` so the backend knows which entity you are viewing, even if you omit the original POST body on subsequent requests.

Response parsing tips:

- Each data row contains plain text with the column order defined above, so scraping is straightforward (e.g., `td:nth-child(1)` is the league name, `td:nth-child(4)` is the scheduled date/time).
- League IDs are not part of the visible text, but the HTML contains links (e.g., to league detail pages) that embed `liga_id` query parameters—you can extract them to map a club back to its leagues.

Source: [basketball-bund.net](https://www.basketball-bund.net/spielplanReportSearch.do?reqCode=list)

---

## Open Questions / Future Work

- The JSON `wam` endpoint advertises more data than it returns per call. If true pagination becomes necessary, we may need to inspect the website’s JavaScript bundle further or replicate any authentication tokens it expects.
- The legacy HTML report exposes `mannschaft_liga_id` and `spielfeld_id` dropdowns, but we have not yet enumerated the AJAX endpoints that populate them when the form is used interactively. Capturing those would simplify automated discovery of team-specific IDs.

Until those questions are resolved, the documented flows above are sufficient to pull schedules, standings, and league directories for the majority of use cases.

