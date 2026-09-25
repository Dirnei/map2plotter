# poster-web-ui Specification

## Purpose

Provide a local web interface where users configure every poster option in a form, run the existing poster generator command, follow its progress, and preview, download and browse the generated posters.

## Requirements

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

### Requirement: Theme selection with preview
The page SHALL list all themes found in the `themes/` directory, with their name, their description and swatches of their colours. The theme list SHALL reflect the directory contents when the page loads.

#### Scenario: Themes listed
- **WHEN** the page loads and `themes/` contains `noir.json` and `terracotta.json`
- **THEN** both themes are selectable, each shown with its display name and colour swatches

### Requirement: Server-side validation
The server SHALL validate a submitted configuration before running anything, and SHALL reject invalid input with an error message per field. The rules are:
- city and country are required
- latitude and longitude must be set together, and must be parseable by the CLI's coordinate parser
- numeric values must be greater than 0
- a PNG export must fit the CLI's PNG pixel limits at the chosen dpi and the loaded size. SVG, PDF and plotter output have no size limit.
- the theme must exist
- the format must be `png`, `svg` or `pdf` in the print workflow. The pen plotter workflow always uses `plotter`.
- for `plotter`, the hatch spacing, water spacing and parks spacing must each not be less than the pen width
- fill modes must be `hatch` or `concentric`
- the edit list must be valid

Customize previews and exports SHALL be rejected when no location has been loaded in the current session.

#### Scenario: Missing city
- **WHEN** a load request is submitted without a city
- **THEN** the server responds with a validation error naming the city field, and no process is started

#### Scenario: Invalid plotter hatch spacing
- **WHEN** the workflow is pen plotter, pen width is 0.5 and hatch spacing is 0.2
- **THEN** the server responds with a validation error naming the hatch spacing field

#### Scenario: Invalid per-area spacing
- **WHEN** the workflow is pen plotter, pen width is 0.5 and water spacing is 0.3
- **THEN** the server responds with a validation error naming the water spacing field

#### Scenario: Invalid edit list
- **WHEN** a preview request contains an edit list with an unknown layer name
- **THEN** the server responds with a validation error for the edits, and no process is started

#### Scenario: Preview before load
- **WHEN** a preview is requested before any location was loaded
- **THEN** the server rejects it with an error saying the map must be loaded first

#### Scenario: Oversized PNG export
- **WHEN** a 1000 × 1500 mm print poster is loaded and a PNG export at 300 dpi is requested
- **THEN** the server responds with a validation error on the dpi field naming the highest dpi that fits, and no process is started

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

### Requirement: Live progress
While a load or export runs, the page SHALL show the process output as it is produced, and the job status (running, succeeded, failed or cancelled). While a preview renders, the page SHALL show a busy indicator on the preview, and SHALL show the output only if the preview fails. When a process exits with a non-zero code, the page SHALL show the job as failed and keep the full output visible.

#### Scenario: Output streams
- **WHEN** the CLI prints "Downloading street network" during a load
- **THEN** the line appears in the page's log view before the job finishes

#### Scenario: Failure reported
- **WHEN** an export's CLI process exits with status 1
- **THEN** the page shows the job as failed along with the output that explains the error

#### Scenario: Preview failure shown
- **WHEN** a preview render fails
- **THEN** the preview keeps the last good image, marked as outdated, and the failure output is shown

### Requirement: Single job and cancellation
The server SHALL run at most one CLI process at a time.
- A new preview request made while a preview is running SHALL cancel the running preview and start the new one.
- A load or export request made while another load or export is running SHALL be rejected with a message that a job is already running.
- A preview request made during a load or export SHALL also be rejected that way.
- A load or export request made while a preview is running SHALL cancel the preview and start.

The user SHALL be able to cancel a running load or export. Cancelling SHALL terminate the process and mark the job as cancelled.

#### Scenario: Concurrent request rejected
- **WHEN** an export is running and another export is submitted
- **THEN** the server rejects the second request with a "job already running" error, and the first job continues

#### Scenario: Newer preview wins
- **WHEN** a preview is rendering and the user changes the theme again
- **THEN** the running preview is terminated and a preview for the latest settings starts

#### Scenario: Cancel
- **WHEN** the user presses cancel during a running export
- **THEN** the process is terminated, the job status becomes cancelled and a new job can be started

### Requirement: Result preview and download
When an export succeeds, the page SHALL show every poster file the export created:
- PNG and SVG files are previewed inline in the page
- PDF files are shown as a link
- every file has a download action that serves it as an attachment

#### Scenario: Single poster shown
- **WHEN** a PNG export succeeds
- **THEN** the new PNG is displayed on the page with a download button

#### Scenario: All themes
- **WHEN** an export with "all themes" succeeds
- **THEN** one result entry per generated file is shown

### Requirement: Poster history
The page SHALL list the poster files in `posters/` (PNG, SVG and PDF), newest first. Each entry SHALL show its file name, creation time and size, together with a preview or open link and a download action. The list SHALL refresh after each finished export. Preview renders SHALL NOT appear in the history.

#### Scenario: History lists existing files
- **WHEN** `posters/` contains three posters and the page loads
- **THEN** all three are listed with the newest first

### Requirement: Safe file access
The server SHALL serve files only from the `posters/` directory. It SHALL reject file requests whose name resolves outside that directory, or whose extension is not `png`, `svg` or `pdf`.

#### Scenario: Path traversal rejected
- **WHEN** a client requests the poster file `../pyproject.toml`
- **THEN** the server responds with an error (not found or bad request) and does not return the file

### Requirement: Container hosts the web interface
The Docker image SHALL start the web interface on port 8000, listening on all container interfaces, when it is run without arguments. When the first argument starts with `-`, the image SHALL run the poster CLI with those arguments instead. The project SHALL provide a Docker Compose file that runs the web interface. That file SHALL publish the port on the host's loopback interface by default, and SHALL persist generated posters and the map data cache in the project's `posters/` and `cache/` directories.

#### Scenario: Container defaults to web UI
- **WHEN** the user runs `docker run -p 127.0.0.1:8000:8000 <image>` without arguments
- **THEN** the web interface is reachable at `http://localhost:8000/`

#### Scenario: CLI still available in container
- **WHEN** the user runs `docker run <image> --city Paris --country France`
- **THEN** the poster CLI runs with those arguments, as it did before

#### Scenario: Compose
- **WHEN** the user runs `docker compose up -d` in the project directory
- **THEN** the web interface is served on `127.0.0.1:8000`, and posters generated through it appear in the host's `posters/` directory

### Requirement: Choose the OpenStreetMap server
The page SHALL offer a dropdown with these choices:
- "Automatic (with fallback)"
- each known public Overpass server
- "Custom…", which shows a URL field

The chosen server SHALL be passed to the CLI as `--overpass-url`. The preselected choice SHALL be the server's `OVERPASS_URL` environment variable when it is set, and automatic otherwise, unless the user saved another choice. A "Check servers" action SHALL test all known servers, plus a custom URL if one is entered, in parallel, and show for each whether it answered, with its response time or failure reason.

#### Scenario: Server passed to the CLI
- **WHEN** the user selects `lz4.overpass-api.de` and generates a poster
- **THEN** the executed command contains `--overpass-url https://lz4.overpass-api.de/api`

#### Scenario: Check servers
- **WHEN** the user presses "Check servers" while the main server times out and `maps.mail.ru` answers
- **THEN** the page lists the main server with a failure reason and `maps.mail.ru` with a check mark and its response time

#### Scenario: Invalid custom URL
- **WHEN** the user enters `not a url` as a custom server and generates
- **THEN** the server rejects the request with a validation error for the OpenStreetMap server field

### Requirement: Two-step workflow
The page SHALL guide the user through two steps: **Location** and **Customize**. Only one step's inputs are shown at a time, and a step indicator shows which step is active. Customize SHALL become available only after the map for the current location has loaded successfully. The user SHALL be able to go back from Customize to Location at any time. The Customize inputs and edits SHALL be kept when going back, unless the location changes (see the editor's rules for edits).

#### Scenario: Customize locked before loading
- **WHEN** the page is opened for the first time
- **THEN** the Location step is shown and the Customize step cannot be opened

#### Scenario: Back to Location
- **WHEN** the user is in Customize and presses "Back to location"
- **THEN** the Location inputs are shown with their previous values, and the chosen theme is still selected when returning

### Requirement: Choose the workflow
The Location step SHALL start with a choice between two workflows:
- **Print poster**: output as PNG, SVG or PDF
- **Pen plotter**: stroke-only plotter SVG

Neither workflow SHALL limit the poster size in the Location step. The default is Print poster. The chosen workflow SHALL be part of the loaded location. The Customize step SHALL show the workflow, the place and the poster size in a header, and SHALL show only the options of that workflow:
- **Print**: the theme grid, file format (`png`, `svg`, `pdf`), PNG resolution and font family
- **Plotter**: the pens list (see "Pens in the plotter workflow") instead of the theme grid, plus pen width, hatch spacing, fill modes, per-area spacing and water outline. The font family SHALL be hidden, because plotter text always uses the single-line pen font.

Switching the workflow SHALL require going back to Location and loading again.

#### Scenario: Plotter workflow
- **WHEN** the user picks "Pen plotter", enters 600 × 900 mm and loads the map
- **THEN** the load succeeds, the preview is the plotter SVG, and Customize shows the pens list and pen options, without a theme grid, file format or font family choice

#### Scenario: Print size limited in Location
- **WHEN** the user picks "Print poster" and enters a width of 0
- **THEN** "Load map" is rejected with an error on the width field; any positive size is accepted

#### Scenario: Large print poster
- **WHEN** the user picks "Print poster", enters 841 × 1189 mm and loads the map
- **THEN** the load succeeds and Customize opens with a preview

### Requirement: Zoom and pan the preview
The preview SHALL support zooming from fit-to-view up to at least 800 %. It SHALL offer:
- zoom in, zoom out and fit buttons, with the current zoom shown
- Ctrl + mouse wheel, which zooms around the pointer
- panning with a Pan tool or the middle mouse button

Editor tools SHALL keep working at any zoom level, with positions still mapped to page millimetres. Plotter previews SHALL stay sharp at every zoom level. Print previews SHALL be rendered at about 2000 pixels on the long side.

#### Scenario: Zoom into a detail
- **WHEN** the user holds Ctrl and scrolls up over a lake in the preview
- **THEN** the preview zooms in with the lake staying under the pointer, and the zoom percentage increases

#### Scenario: Erase while zoomed
- **WHEN** the user zooms to 400 % and draws an erase rectangle
- **THEN** the rectangle is stored in page millimetres, and the exported poster erases the same area

### Requirement: Preview errors are visible
When a preview request is rejected or its render fails, the preview area SHALL show the reason. The last good preview SHALL stay visible, marked as outdated. The message SHALL be removed when a later preview succeeds.

#### Scenario: Invalid option
- **WHEN** the user enters a water spacing below the pen width
- **THEN** the preview area says that the preview was not updated, and why

### Requirement: Load map in the Location step
The Location step SHALL contain the workflow choice, city, country, latitude/longitude, distance, width and height in mm, and the OpenStreetMap server choice. Pressing "Load map" SHALL validate these inputs and start a load job. The job downloads the map data (or reads it from the cache) through the CLI and renders a preview with the currently selected theme: a PNG for print posters, and the plotter SVG for the pen plotter workflow. Its output SHALL stream live like any job. When it succeeds, the page SHALL show the preview and switch to Customize. When it fails, the page SHALL stay on Location and show the failure output.

#### Scenario: Successful load
- **WHEN** the user enters Paris, France and presses "Load map"
- **THEN** the download progress streams into the log, a preview of Paris appears and the Customize step opens

#### Scenario: Load failure
- **WHEN** every Overpass server fails during "Load map"
- **THEN** the page stays on Location, shows the job as failed and keeps the error output visible

### Requirement: Customize without downloading
The Customize step SHALL contain the theme, display city and country, country label, the options of the chosen workflow, and the editor. Every change to them SHALL re-render the preview from the map data loaded in the Location step, using the CLI's cache-only mode. A Customize preview SHALL never download map data. Changes SHALL be debounced, so a burst of changes starts at most one preview. The preview SHALL be a PNG for print posters and the actual plotter SVG for the pen plotter workflow. If a cache-only render fails because the data is no longer cached, the page SHALL say so and offer to go back to Location and reload.

#### Scenario: Theme change reuses data
- **WHEN** the map has loaded and the user switches the theme from `terracotta` to `noir`
- **THEN** a new preview in `noir` appears, the executed command contains `--cache-only`, and no request is sent to an Overpass server

#### Scenario: Plotter preview
- **WHEN** the pen plotter workflow is loaded and the user changes the pen colours from `terracotta` to `noir`
- **THEN** the preview shows the plotter SVG with its pen strokes in the new colours

#### Scenario: Cache cleared meanwhile
- **WHEN** the cache directory was emptied after loading and the user changes the theme
- **THEN** the page reports that the map data is no longer cached and offers to reload the location

### Requirement: Export the poster
The Customize step SHALL have an "Export" action. It SHALL render the final poster with the current settings and edit list, in the chosen format and at full resolution, in cache-only mode, and write it to `posters/` with the usual file name. "All themes" SHALL be available only for export. It writes one poster per theme with the same edit list.

#### Scenario: Export writes to posters
- **WHEN** the user presses "Export" with format `png`
- **THEN** a new 300 dpi PNG appears in `posters/` and in the history, with the edits applied

#### Scenario: Export all themes
- **WHEN** the user ticks "all themes" and presses "Export"
- **THEN** one poster per theme is written to `posters/`, none of them requiring a download

### Requirement: Preview files are kept out of the history
Preview images SHALL be written outside `posters/`, to a working directory of the web interface inside the cache directory. The server SHALL serve only the most recent preview of the current session, at a dedicated URL. Each new preview SHALL replace the previous preview files.

#### Scenario: Previews not in history
- **WHEN** the user changes the theme five times and then exports once
- **THEN** the history shows exactly one new poster

### Requirement: Pens in the plotter workflow
In the pen plotter workflow, the Customize step SHALL show a pens list with one row per plottable element:
- water, parks
- motorways, primary, secondary, tertiary and residential roads, other roads
- text

Each row SHALL have a colour picker. Each map layer row SHALL also have a show/hide toggle, which controls the hidden layers of the edit list. The list SHALL show how many distinct pens (colours of visible elements) the poster needs.

Two presets SHALL be offered:
- **Start from theme**: sets every element's colour from a chosen theme
- **Single pen**: sets every element to black

The initial colours SHALL come from the theme selected when the map was loaded.

The plotter preview SHALL be shown on white paper, without a theme background. A colour change SHALL update the preview immediately in the browser, without starting a render. Exports SHALL pass the pen colours to the CLI with `--color` for every colour that differs from the base theme, so the exported file and the displayed command match the preview.

#### Scenario: Recolour water instantly
- **WHEN** the user picks blue for water in the pens list
- **THEN** the water paths in the preview turn blue at once and no new preview job is started

#### Scenario: Shared pen count
- **WHEN** tertiary roads and other roads are set to the same colour and everything else differs
- **THEN** the pens list shows one pen fewer than the number of visible elements

#### Scenario: Single pen preset
- **WHEN** the user chooses "Single pen"
- **THEN** every row is black, the pen count shows 1, and the exported SVG has one layer

#### Scenario: Export uses the pen colours
- **WHEN** the base theme is terracotta, the user sets water to `#1f5fa8` and exports
- **THEN** the executed command contains `--color water=#1f5fa8`, and the exported SVG's water layer has that stroke

#### Scenario: Hide a layer from the pens list
- **WHEN** the user turns off parks in the pens list
- **THEN** the preview re-renders without parks, and the parks row stays in the list, switched off

#### Scenario: Print keeps themes
- **WHEN** the loaded workflow is Print poster
- **THEN** Customize shows the theme grid and no pens list

### Requirement: PNG resolution in the print workflow
In the print workflow, Customize SHALL offer a PNG resolution field in dpi (default 300), shown when the format is PNG and passed to the export as `--dpi`. The page SHALL show the resulting pixel size next to the field:
- above 100 megapixels, a warning that the file will be large and the export slow
- over the PNG pixel limit, an error with the highest dpi that fits and a "Use N dpi" action that sets it

Export SHALL be blocked while the PNG is over the limit. Previews SHALL NOT depend on this setting.

#### Scenario: Suggest a lower dpi
- **WHEN** a 1000 × 1500 mm print poster is loaded and the format is PNG at 300 dpi
- **THEN** the field shows the pixel size, an error, and "Use 293 dpi". Pressing it sets 293, and the export succeeds.

#### Scenario: Vector format avoids the limit
- **WHEN** the same poster is set to SVG
- **THEN** the dpi field is hidden, and export is possible without any limit message
