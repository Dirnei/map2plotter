# project-attribution Specification

## Purpose

Makes sure map2plotter credits the original maptoposter project it continues, as the MIT license requires, and identifies itself honestly to the OpenStreetMap services it uses.

## Requirements

### Requirement: License notice preserved
The repository's `LICENSE` file SHALL keep the MIT license text and the original notice `Copyright (c) 2026 Ankur Gupta` unchanged. It SHALL add a separate copyright line for the maintainer of map2plotter. Every distribution of the project (source archive, wheel, Docker image) SHALL include this `LICENSE` file.

#### Scenario: Original notice kept
- **WHEN** a reader opens `LICENSE`
- **THEN** it contains the line `Copyright (c) 2026 Ankur Gupta` and the unmodified MIT permission and warranty text, followed or preceded by a copyright line for Christian Dirnhofer

#### Scenario: License shipped with the package
- **WHEN** the project is built as a wheel
- **THEN** the wheel contains the `LICENSE` file

### Requirement: Original project credited
The project SHALL link to the original project, `https://github.com/originalankur/maptoposter`, in these places:
- near the top of the README, before the installation instructions: a note that map2plotter continues originalankur/maptoposter, which is no longer maintained
- in the package metadata, as a project URL
- in the web interface, as a link visible on the page

The package metadata SHALL keep Ankur Gupta as an author and name the map2plotter maintainer separately. The CHANGELOG SHALL keep its entries and links for releases of the original project.

#### Scenario: README note
- **WHEN** a reader opens the README
- **THEN** before the installation section, they see a sentence saying map2plotter continues originalankur/maptoposter, with a link to `https://github.com/originalankur/maptoposter`

#### Scenario: Package metadata
- **WHEN** the package metadata is inspected (for example on the PyPI page or with `pip show`)
- **THEN** Ankur Gupta is listed as an author, Christian Dirnhofer as a maintainer, and the project URLs include both the map2plotter repository and the original project

#### Scenario: Web interface link
- **WHEN** the user opens the web interface
- **THEN** the page shows a link to the original maptoposter project

### Requirement: Identification to OpenStreetMap services
Every request the project makes to Overpass servers and to the Nominatim geocoder SHALL send the User-Agent `map2plotter/<version> (+<repository URL>)`, where `<version>` is the installed package version and `<repository URL>` is the map2plotter repository. This covers map data downloads, server health checks and geocoding. The project SHALL NOT identify itself with the original project's name or URL.

#### Scenario: Health check User-Agent
- **WHEN** the web interface's **Check servers** runs
- **THEN** each request carries the User-Agent `map2plotter/<version> (+<repository URL>)`

#### Scenario: Download and geocoding User-Agent
- **WHEN** the CLI geocodes a city and downloads its map data
- **THEN** the Nominatim request and the Overpass requests carry the same map2plotter User-Agent, and none mentions `originalankur` or `city_map_poster`
