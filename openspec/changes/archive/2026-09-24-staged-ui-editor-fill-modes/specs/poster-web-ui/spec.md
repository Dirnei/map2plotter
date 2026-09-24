# Spec Delta

## ADDED Requirements

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
- **Print poster**: output as PNG, SVG or PDF, with a size limit of 500 mm per side
- **Pen plotter**: stroke-only plotter SVG, with no size limit

The default is Print poster. The chosen workflow SHALL be part of the loaded location. The Customize step SHALL show the workflow, the place and the poster size in a header, and SHALL show only the options of that workflow:
- **Print**: file format (`png`, `svg`, `pdf`) and font family
- **Plotter**: pen width, hatch spacing, fill modes, per-area spacing and water outline. The theme picker SHALL be labelled as pen colours, since each colour becomes a layer. The font family SHALL be hidden, because plotter text always uses the single-line pen font.

Switching the workflow SHALL require going back to Location and loading again.

#### Scenario: Plotter workflow
- **WHEN** the user picks "Pen plotter", enters 600 × 900 mm and loads the map
- **THEN** the load succeeds, the preview is the plotter SVG, and Customize shows the pen options and pen colours, without a file format or font family choice

#### Scenario: Print size limited in Location
- **WHEN** the user picks "Print poster" and enters a width of 600 mm
- **THEN** "Load map" is rejected with an error on the width field that suggests the pen plotter workflow for larger sizes

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

## MODIFIED Requirements

### Requirement: Configuration form covers all CLI options
The page SHALL provide inputs for every poster option of `create_map_poster.py`, split across the two steps.

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

### Requirement: Server-side validation
The server SHALL validate a submitted configuration before running anything, and SHALL reject invalid input with an error message per field. The rules are:
- city and country are required
- latitude and longitude must be set together, and must be parseable by the CLI's coordinate parser
- numeric values must be greater than 0
- in the print workflow, width and height must not exceed 500 mm. The pen plotter workflow has no upper limit.
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

### Requirement: Invoke the existing CLI
Every load, preview and export SHALL run `create_map_poster.py` as a separate process, using the same Python interpreter. The server SHALL pass the configuration as a command-line argument list, never through a shell. Options left empty SHALL be omitted, so the CLI defaults apply.
- Previews and exports SHALL pass `--cache-only`.
- Loads and previews SHALL pass `--output` pointing to the preview file, and PNG previews a reduced `--dpi`.
- When the edit list is not empty, it SHALL be written to a file in the working directory and passed with `--edits`.

The page SHALL display the equivalent command line of the last export or load so the user can copy it.

#### Scenario: Command built from form
- **WHEN** the user has loaded Paris, France and exports with theme "noir", distance 10000 and format "svg"
- **THEN** the process runs with the arguments `--city Paris --country France --theme noir --distance 10000 --format svg --cache-only`, plus `--width`/`--height` in mm, and the page shows that command

#### Scenario: Plotter fill options passed
- **WHEN** the user exports a plotter poster with water fill `concentric`, water spacing 1 and the water outline on
- **THEN** the arguments contain `--water-fill concentric --water-spacing 1 --water-outline`

#### Scenario: No shell interpretation
- **WHEN** the city is `Paris; rm -rf /`
- **THEN** the whole string is passed as the single `--city` argument value and no shell command is executed

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
