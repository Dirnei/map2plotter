# Spec Delta

## ADDED Requirements

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
