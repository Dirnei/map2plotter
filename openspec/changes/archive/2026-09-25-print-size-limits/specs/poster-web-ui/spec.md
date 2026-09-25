# Spec Delta

## MODIFIED Requirements

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

## ADDED Requirements

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
