# osm-data-source Specification

## Purpose

Choose which OpenStreetMap (Overpass API) server the generator downloads map data from, and keep generation working when public servers are overloaded or down.

## Requirements

### Requirement: Selectable Overpass server
The CLI SHALL accept `--overpass-url` with either `auto` or an http(s) Overpass API URL. The URL may be given as the `/api` base or the full `/api/interpreter` endpoint. When the option is omitted, the value of the `OVERPASS_URL` environment variable SHALL be used, and `auto` when that is unset. A value that is neither `auto` nor an http(s) URL SHALL be rejected with an error before any download. A specific server SHALL be the only server used for the run.

#### Scenario: Specific server
- **WHEN** the user passes `--overpass-url https://lz4.overpass-api.de/api/interpreter`
- **THEN** all map data downloads of the run go to `https://lz4.overpass-api.de/api`

#### Scenario: Environment default
- **WHEN** `OVERPASS_URL=https://maps.mail.ru/osm/tools/overpass/api` is set and `--overpass-url` is not passed
- **THEN** the downloads go to that server

#### Scenario: Invalid value
- **WHEN** the user passes `--overpass-url ftp://example.org`
- **THEN** the tool prints an error and exits with a non-zero status without downloading

### Requirement: Automatic server fallback
In `auto` mode, the tool SHALL health-check the known public servers in parallel with a small test query before the first download. It SHALL then try the servers that answered first, in their priority order, followed by the others. When a download fails with a server error (connection error, timeout, or an error HTTP status), the tool SHALL print which server failed and why, and SHALL retry the download on the next server. A server that keeps answering 429 or 504 SHALL be given up after 3 attempts. When a server succeeds, the following downloads of the run SHALL use it first. If the area simply contains no data of a kind (e.g. no parks), that SHALL NOT count as a server failure.

#### Scenario: Main server down
- **WHEN** the main server refuses connections and `lz4.overpass-api.de` answers
- **THEN** the poster is generated from `lz4.overpass-api.de`, and the output shows that the main server failed and which server was tried next

#### Scenario: Busy server does not block forever
- **WHEN** a server answers 504 to every attempt
- **THEN** the tool stops trying that server after 3 attempts and moves on to the next one

### Requirement: Download errors are visible
When the street network cannot be downloaded, the tool SHALL exit with an error message that includes the cause for each server tried. When water or park features cannot be downloaded, the tool SHALL print a warning with the cause and continue without them. These messages SHALL NOT be hidden by the progress bar.

#### Scenario: All servers fail
- **WHEN** every server fails for the street network download
- **THEN** the error reads "Failed to retrieve street network data from OpenStreetMap:" followed by each server and its failure reason

### Requirement: Cache-only mode
The CLI SHALL accept `--cache-only`. In this mode it SHALL NOT make any network request for map data or geocoding, and SHALL NOT run the Overpass server health check. Map data SHALL come only from the local cache, including a larger cached area cropped to the requested one. If the street network for the requested area is not cached, the tool SHALL exit with a non-zero status and an error saying the map data is not cached. If the coordinates cannot be resolved without geocoding (no `--latitude`/`--longitude` and no cached result for the city and country), it SHALL exit the same way. Water or park data that is not cached SHALL be treated like a failed download: a warning is printed and the poster is drawn without them. Without `--cache-only`, behaviour SHALL be unchanged.

#### Scenario: Cached area renders offline
- **WHEN** a poster of Paris at 10000 m was generated before, and the user runs the same location with `--cache-only --theme noir`
- **THEN** the poster is written and no request is sent to any Overpass or geocoding server

#### Scenario: Smaller area reuses cached data
- **WHEN** Paris was fetched at 10000 m and the user runs Paris at 6000 m with `--cache-only`
- **THEN** the poster is rendered from the cropped cached data without a download

#### Scenario: Missing data fails fast
- **WHEN** no data for Lisbon is cached and the user runs Lisbon with `--cache-only`
- **THEN** the tool exits with a non-zero status, prints that the map data is not cached, and makes no network request

#### Scenario: Missing water cache is a warning
- **WHEN** the street network is cached but the water download had failed earlier, and the user runs with `--cache-only`
- **THEN** a warning is printed and the poster is written without water
