# Spec Delta

## MODIFIED Requirements

### Requirement: Start the web server
The project SHALL provide a web server started with the `map2plotter-web` command. By default it SHALL listen on `127.0.0.1:8000`. It SHALL accept `--host` and `--port` options. When started, it SHALL print the URL it serves. The page title and heading SHALL show the project name map2plotter.

#### Scenario: Default start
- **WHEN** the user runs `map2plotter-web`
- **THEN** the page is reachable at `http://127.0.0.1:8000/` and is not reachable from other machines

#### Scenario: Custom bind address
- **WHEN** the user runs `map2plotter-web --host 0.0.0.0 --port 9000`
- **THEN** the page is served on port 9000 on all interfaces

#### Scenario: Project name on the page
- **WHEN** the user opens the page
- **THEN** the browser tab title and the page heading show map2plotter

### Requirement: Configuration form covers all CLI options
The page SHALL provide inputs for every poster option of the `map2plotter` CLI, split across the two steps.

**Location**:
- workflow: print poster or pen plotter
- city and country (both required)
- latitude and longitude (optional, but both must be set together)
- distance
- width and height in mm
- OpenStreetMap server

**Customize**:
- theme, or all themes (for export)
- country label
- display city and display country
- print workflow: font family and output format (`png`, `svg`, `pdf`)
- plotter workflow (output format `plotter`): pen width, hatch spacing, water and parks fill mode (`hatch` or `concentric`), water and parks line spacing, water outline

Defaults SHALL match the CLI defaults. The plotter-only inputs SHALL be shown only in the pen plotter workflow.

#### Scenario: Defaults match CLI
- **WHEN** the page is opened
- **THEN** the workflow is print poster, the theme is `terracotta`, the distance is 18000, the width is 300 mm, the height is 400 mm, the format is `png`, the pen width is 0.3, both fill modes are `hatch` and the water outline is off

#### Scenario: Plotter options toggle
- **WHEN** a map is loaded in the pen plotter workflow
- **THEN** the pen width, hatch spacing, fill mode, per-area spacing and water outline inputs are visible in Customize. In the print workflow they are hidden, and the format and font family are shown instead.

### Requirement: Invoke the existing CLI
Every load, preview and export SHALL run the poster CLI as a separate process, as `python -m map2plotter` using the same Python interpreter as the server. The server SHALL pass the configuration as a command-line argument list, never through a shell. Options left empty SHALL be omitted, so the CLI defaults apply.
- Previews and exports SHALL pass `--cache-only`.
- Loads and previews SHALL pass `--output` pointing to the preview file, and PNG previews a reduced `--dpi`.
- When the edit list is not empty, it SHALL be written to a file in the working directory and passed with `--edits`.

The CLI process SHALL use the same posters and cache directories as the server. The page SHALL display the equivalent command line of the last export or load, starting with `map2plotter`, so the user can copy it.

#### Scenario: Command built from form
- **WHEN** the user has loaded Paris, France and exports with theme "noir", distance 10000 and format "svg"
- **THEN** the process runs with the arguments `--city Paris --country France --theme noir --distance 10000 --format svg --cache-only`, plus `--width`/`--height` in mm, and the page shows that command starting with `map2plotter`

#### Scenario: Plotter fill options passed
- **WHEN** the user exports a plotter poster with water fill `concentric`, water spacing 1 and the water outline on
- **THEN** the arguments contain `--water-fill concentric --water-spacing 1 --water-outline`

#### Scenario: No shell interpretation
- **WHEN** the city is `Paris; rm -rf /`
- **THEN** the whole string is passed as the single `--city` argument value and no shell command is executed

### Requirement: Safe file access
The server SHALL serve files only from the `posters/` directory. It SHALL reject file requests whose name resolves outside that directory, or whose extension is not `png`, `svg` or `pdf`.

#### Scenario: Path traversal rejected
- **WHEN** a client requests the poster file `../pyproject.toml`
- **THEN** the server responds with an error (not found or bad request) and does not return the file
