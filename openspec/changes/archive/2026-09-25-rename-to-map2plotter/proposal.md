# Proposal

## Why

The original project, `originalankur/maptoposter`, is no longer maintained, and this repository will be published as its own project. Several other copies of the same project already use its names: `maptoposter` and `map2poster` are both taken on PyPI. If this project kept the `maptoposter` command and import package, it would clash with those copies whenever both are installed in one environment, and users could not tell the projects apart. The new name is **map2plotter**, which also points at what sets this project apart: pen-plotter output. Publishing independently makes it important to credit the original work visibly, as the MIT license requires and as the contributors deserve.

## What Changes

- **BREAKING (names)**
  - The project/PyPI name becomes `map2plotter`, and the Python package moves from `src/maptoposter/` to `src/map2plotter/`.
  - The commands become `map2plotter` (CLI) and `map2plotter-web` (web interface). `python -m map2plotter` behaves like `map2plotter`. The old `maptoposter` / `maptoposter-web` commands are removed, with no aliases.
  - The Docker Compose service and image become `map2plotter`, and the host-port variable `MAPTOPOSTER_PORT` becomes `MAP2PLOTTER_PORT`.
  - The web page, the CLI banner and the help text show the name map2plotter. The copyable command in the web UI starts with `map2plotter`.
- **Attribution**
  - `LICENSE` keeps Ankur Gupta's copyright notice unchanged and adds a copyright line for Christian Dirnhofer.
  - `pyproject.toml` keeps Ankur Gupta under `authors`, adds Christian Dirnhofer under `maintainers`, and adds `[project.urls]` with the new repository and the original project.
  - A visible note near the top of the README says that map2plotter continues [originalankur/maptoposter](https://github.com/originalankur/maptoposter), which is no longer maintained, and links to it. The web interface's footer links to it as well.
  - The CHANGELOG keeps its historical upstream links, and gets an entry for the rename.
- **Identification to OpenStreetMap services**: the Overpass health check, the Nominatim geocoder and OSMnx's downloads send one User-Agent, `map2plotter/<version> (+<repository URL>)`. It is defined in one place and replaces the current `maptoposter (https://github.com/originalankur/maptoposter)` and `city_map_poster` values.
- **Spec clean-up**: the remaining references in the main specs to `create_map_poster.py` are updated to the new command.
- **Not in this change**: removing the print (PNG/SVG/PDF) output, publishing to PyPI, and installing without a clone.

## Capabilities

### New Capabilities
- `project-attribution`: covers how the project credits the original maptoposter project (license notice, package metadata, README note, web UI link) and how it identifies itself to OpenStreetMap services.

### Modified Capabilities
- `package-layout`: "Package commands" and "Bundled data independent of the working directory" now name the `map2plotter` package and commands.
- `poster-web-ui`:
  - "Start the web server" uses `map2plotter-web`.
  - "Invoke the existing CLI" runs `python -m map2plotter` and shows the command as `map2plotter …`.
  - "Configuration form covers all CLI options" and "Safe file access" drop their leftover `create_map_poster.py` references.
- `plotter-svg-export`: "Plotter output format" drops its leftover `create_map_poster.py` reference in its scenario.

## Impact

- **Code:** the package directory is renamed and every internal and test import changes. The command, prog names, banner, web page title and User-Agent strings change. A new module constant holds the project URL and User-Agent.
- **Build and deployment:** `pyproject.toml`, `uv.lock` and `requirements.txt` (project name only), the Dockerfile's copied paths, `docker-entrypoint.sh`, `compose.yaml` and the CI workflow change. The published GHCR image follows the new repository name automatically (`ghcr.io/${{ github.repository }}`).
- **Docs:** the README, CHANGELOG, LICENSE and `test/all_variations.sh` change.
- **Users:**
  - Existing scripts calling `maptoposter` have to switch to `map2plotter`, and scripts that set `MAPTOPOSTER_PORT` have to set `MAP2PLOTTER_PORT`.
  - The cache, posters, themes and output files are unchanged.
  - The web UI's saved form and pens are reset once, because the browser storage keys are renamed. There are no existing users whose settings would be lost.
- **Open input:** the new repository URL is not known yet. It is needed for the User-Agent, `[project.urls]` and the README. Implementation pauses at that point to ask for it.
