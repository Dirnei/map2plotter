# Spec Delta

## MODIFIED Requirements

### Requirement: Theme selection with preview
The page SHALL offer all themes found in the themes directory as colour presets in the pens list ("Start from theme"), by display name. The theme list SHALL reflect the directory contents when the page loads. Choosing a theme SHALL set every pen colour from it, and it SHALL be the base theme for the export's file name and colour overrides.

#### Scenario: Themes listed
- **WHEN** the page loads and the themes directory contains `noir.json` and `terracotta.json`
- **THEN** both themes are offered by their display names under "Start from theme"

### Requirement: Invoke the existing CLI
Every load, preview and export SHALL run the poster CLI as a separate process, as `python -m map2plotter` using the same Python interpreter as the server. The server SHALL pass the configuration as a command-line argument list, never through a shell. Options left empty SHALL be omitted, so the CLI defaults apply.
- Previews and exports SHALL pass `--cache-only`.
- Loads and previews SHALL pass `--output` pointing to the preview SVG file, at the full poster size.
- When the edit list is not empty, it SHALL be written to a file in the working directory and passed with `--edits`.

The CLI process SHALL use the same posters and cache directories as the server. The page SHALL display the equivalent command line of the last export or load, starting with `map2plotter`, so the user can copy it.

#### Scenario: Command built from form
- **WHEN** the user has loaded Paris, France at distance 10000 and exports with theme "noir"
- **THEN** the process runs with the arguments `--city Paris --country France --theme noir --distance 10000 --cache-only`, plus `--width`/`--height` in mm and the plotter options, and the page shows that command starting with `map2plotter`

#### Scenario: Plotter fill options passed
- **WHEN** the user exports a poster with water fill `concentric`, water spacing 1 and the water outline on
- **THEN** the arguments contain `--water-fill concentric --water-spacing 1 --water-outline`

#### Scenario: No shell interpretation
- **WHEN** the city is `Paris; rm -rf /`
- **THEN** the whole string is passed as the single `--city` argument value and no shell command is executed

### Requirement: Result preview and download
When an export succeeds, the page SHALL show every poster SVG the export created, previewed inline, each with a download action that serves it as an attachment.

#### Scenario: Single poster shown
- **WHEN** an export succeeds
- **THEN** the new SVG is displayed on the page with a download button

#### Scenario: All themes
- **WHEN** an export with "all themes" succeeds
- **THEN** one result entry per generated file is shown

### Requirement: Poster history
The page SHALL list the SVG poster files in `posters/`, newest first. Each entry SHALL show its file name, creation time and size, together with a preview and a download action. Other files in `posters/` (for example PNG or PDF files from earlier versions) SHALL NOT be listed. The list SHALL refresh after each finished export. Preview renders SHALL NOT appear in the history.

#### Scenario: History lists existing files
- **WHEN** `posters/` contains three SVG posters and one PNG, and the page loads
- **THEN** the three SVGs are listed with the newest first, and the PNG is not listed

### Requirement: Safe file access
The server SHALL serve files only from the `posters/` directory. It SHALL reject file requests whose name resolves outside that directory, or whose extension is not `svg`.

#### Scenario: Path traversal rejected
- **WHEN** a client requests the poster file `../pyproject.toml`
- **THEN** the server responds with an error (not found or bad request) and does not return the file

#### Scenario: Non-SVG file rejected
- **WHEN** `posters/old.png` exists and a client requests it
- **THEN** the server responds with an error and does not return the file

### Requirement: Zoom and pan the preview
The preview SHALL support zooming from fit-to-view up to at least 800 %. It SHALL offer:
- zoom in, zoom out and fit buttons, with the current zoom shown
- Ctrl + mouse wheel, which zooms around the pointer
- panning with a Pan tool or the middle mouse button

Editor tools SHALL keep working at any zoom level, with positions still mapped to page millimetres. The preview is a vector SVG and SHALL stay sharp at every zoom level.

#### Scenario: Zoom into a detail
- **WHEN** the user holds Ctrl and scrolls up over a lake in the preview
- **THEN** the preview zooms in with the lake staying under the pointer, and the zoom percentage increases

#### Scenario: Erase while zoomed
- **WHEN** the user zooms to 400 % and draws an erase rectangle
- **THEN** the rectangle is stored in page millimetres, and the exported poster erases the same area

### Requirement: Load map in the Location step
The Location step SHALL contain city, country, latitude/longitude, distance, width and height in mm, and the OpenStreetMap server choice. Any positive poster size SHALL be accepted. Pressing "Load map" SHALL validate these inputs and start a load job. The job downloads the map data (or reads it from the cache) through the CLI and renders the plotter SVG as the preview, with the currently selected theme's colours. Its output SHALL stream live like any job. When it succeeds, the page SHALL show the preview and switch to Customize. When it fails, the page SHALL stay on Location and show the failure output.

#### Scenario: Successful load
- **WHEN** the user enters Paris, France and presses "Load map"
- **THEN** the download progress streams into the log, a plotter SVG preview of Paris appears and the Customize step opens

#### Scenario: Large poster
- **WHEN** the user enters 841 × 1189 mm and loads the map
- **THEN** the load succeeds and Customize opens with a preview

#### Scenario: Load failure
- **WHEN** every Overpass server fails during "Load map"
- **THEN** the page stays on Location, shows the job as failed and keeps the error output visible

### Requirement: Export the poster
The Customize step SHALL have an "Export" action. It SHALL render the final plotter SVG with the current settings, pen colours and edit list, in cache-only mode, and write it to `posters/` with the usual file name. "All themes" SHALL be available only for export. It writes one SVG per theme with the same edit list.

#### Scenario: Export writes to posters
- **WHEN** the user presses "Export"
- **THEN** a new SVG appears in `posters/` and in the history, with the edits applied

#### Scenario: Export all themes
- **WHEN** the user ticks "all themes" and presses "Export"
- **THEN** one SVG per theme is written to `posters/`, none of them requiring a download

## ADDED Requirements

### Requirement: Configuration form covers all plotter options
The page SHALL provide inputs for every poster option of the `map2plotter` CLI, split across the two steps.

**Location**:
- city and country (both required)
- latitude and longitude (optional, but both must be set together)
- distance
- width and height in mm
- OpenStreetMap server

**Customize**:
- pen colours, starting from a theme, or all themes (for export)
- country label
- display city and display country
- pen width, hatch spacing, water and parks fill mode (`hatch` or `concentric`), water and parks line spacing, water outline

Defaults SHALL match the CLI defaults. The page SHALL NOT offer a choice of output format, resolution or font.

#### Scenario: Defaults match CLI
- **WHEN** the page is opened
- **THEN** the theme is `terracotta`, the distance is 18000, the width is 300 mm, the height is 400 mm, the pen width is 0.3, both fill modes are `hatch` and the water outline is off

#### Scenario: No print options
- **WHEN** a map is loaded and Customize is shown
- **THEN** there is no workflow choice, file format, resolution or font family input

### Requirement: Server-side validation of plotter settings
The server SHALL validate a submitted configuration before running anything, and SHALL reject invalid input with an error message per field. The rules are:
- city and country are required
- latitude and longitude must be set together, and must be parseable by the CLI's coordinate parser
- numeric values must be greater than 0
- the theme must exist
- the hatch spacing, water spacing and parks spacing must each not be less than the pen width
- fill modes must be `hatch` or `concentric`
- colour overrides must use pen colour keys and six-digit hex colours
- the edit list must be valid

Customize previews and exports SHALL be rejected when no location has been loaded in the current session. Fields that older pages may still send (`mode`, `format`, `dpi`, `font_family`) SHALL be ignored.

#### Scenario: Missing city
- **WHEN** a load request is submitted without a city
- **THEN** the server responds with a validation error naming the city field, and no process is started

#### Scenario: Invalid hatch spacing
- **WHEN** the pen width is 0.5 and the hatch spacing is 0.2
- **THEN** the server responds with a validation error naming the hatch spacing field

#### Scenario: Invalid per-area spacing
- **WHEN** the pen width is 0.5 and the water spacing is 0.3
- **THEN** the server responds with a validation error naming the water spacing field

#### Scenario: Invalid edit list
- **WHEN** a preview request contains an edit list with an unknown layer name
- **THEN** the server responds with a validation error for the edits, and no process is started

#### Scenario: Preview before load
- **WHEN** a preview is requested before any location was loaded
- **THEN** the server rejects it with an error saying the map must be loaded first

#### Scenario: Old print fields ignored
- **WHEN** an export request contains `"format": "png", "dpi": 300`
- **THEN** the export runs as a plotter SVG export and the executed command contains neither `--format` nor `--dpi`

### Requirement: Customize the plotter poster without downloading
The Customize step SHALL contain the pens list, display city and country, country label, the plotter options and the editor. Every change to them, except a pen colour change (see "Pens in the plotter workflow"), SHALL re-render the preview from the map data loaded in the Location step, using the CLI's cache-only mode. A Customize preview SHALL never download map data. Changes SHALL be debounced, so a burst of changes starts at most one preview. The preview SHALL be the actual plotter SVG. If a cache-only render fails because the data is no longer cached, the page SHALL say so and offer to go back to Location and reload.

#### Scenario: Option change reuses data
- **WHEN** the map has loaded and the user changes the water fill to `concentric`
- **THEN** a new preview with concentric water appears, the executed command contains `--cache-only`, and no request is sent to an Overpass server

#### Scenario: Colours from another theme
- **WHEN** the map has loaded and the user applies the `noir` colours with "Start from theme"
- **THEN** the preview shows the plotter SVG with its pen strokes in the `noir` colours

#### Scenario: Cache cleared meanwhile
- **WHEN** the cache directory was emptied after loading and the user changes the pen width
- **THEN** the page reports that the map data is no longer cached and offers to reload the location

### Requirement: Pens and layers
The Customize step SHALL show a pens list with one row per plottable element:
- water, parks
- motorways, primary, secondary, tertiary and residential roads, other roads
- text

Each row SHALL have a colour picker. Each map layer row SHALL also have a show/hide toggle, which controls the hidden layers of the edit list. The list SHALL show how many distinct pens (colours of visible elements) the poster needs.

Two presets SHALL be offered:
- **Start from theme**: sets every element's colour from a chosen theme
- **Single pen**: sets every element to black

The initial colours SHALL come from the theme selected when the map was loaded.

The preview SHALL be shown on white paper, without a theme background. A colour change SHALL update the preview immediately in the browser, without starting a render. Exports SHALL pass the pen colours to the CLI with `--color` for every colour that differs from the base theme, so the exported file and the displayed command match the preview.

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

## REMOVED Requirements

### Requirement: Configuration form covers all CLI options
**Reason**: Its print-workflow behaviour is gone, so it is replaced by "Configuration form covers all plotter options", which covers the same ground for plotter output only.
**Migration**: See "Configuration form covers all plotter options".

### Requirement: Server-side validation
**Reason**: Its print-workflow behaviour is gone, so it is replaced by "Server-side validation of plotter settings", which covers the same ground for plotter output only.
**Migration**: See "Server-side validation of plotter settings".

### Requirement: Customize without downloading
**Reason**: Its print-workflow behaviour is gone, so it is replaced by "Customize the plotter poster without downloading", which covers the same ground for plotter output only.
**Migration**: See "Customize the plotter poster without downloading".

### Requirement: Pens in the plotter workflow
**Reason**: Its print-workflow behaviour is gone, so it is replaced by "Pens and layers", which covers the same ground for plotter output only.
**Migration**: See "Pens and layers".

### Requirement: Choose the workflow
**Reason**: map2plotter produces plotter SVGs only, so there is no choice between a print poster and a pen plotter workflow any more.
**Migration**: None in the page. The Location step goes straight to the location inputs, and Customize always shows the pens list and plotter options. For print posters (PNG/PDF), use one of the other maptoposter projects.

### Requirement: PNG resolution in the print workflow
**Reason**: There is no PNG output any more, so there is no resolution field, pixel limit or "Use N dpi" suggestion.
**Migration**: None. The exported SVG has no resolution. Convert it to a raster image outside the tool if needed.
