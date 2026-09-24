# Spec Delta

## Purpose

Let users adjust a poster by hand (erase parts of the map, move or hide text lines, hide layers). Edits are stored as data that every re-render and export applies again, so changing the theme, format or pen settings never loses them.

## ADDED Requirements

### Requirement: Edit list format
An edit list SHALL be a JSON object with these optional members:
- `version`: must be `1` when present
- `erase`: a list of polygons. Each polygon is a list of at least three `[x, y]` points in page millimetres, with the origin at the top-left corner of the page and y pointing down.
- `text`: an object with optional entries `city`, `country`, `coords` and `divider`. Each entry may set `dx` and `dy` (an offset in mm, default 0) and `hidden` (boolean, default false).
- `hidden_layers`: a list of layer names from `water`, `parks`, `road_motorway`, `road_primary`, `road_secondary`, `road_tertiary`, `road_residential` and `road_default`.

Unknown members, unknown text entries or layer names, non-numeric coordinates and polygons with fewer than three points SHALL make the edit list invalid. Coordinates outside the page SHALL be allowed and clipped to the page. An empty object SHALL be a valid edit list that changes nothing.

#### Scenario: Valid edit list
- **WHEN** the edit list is `{"version": 1, "erase": [[[10,10],[50,10],[50,40]]], "text": {"city": {"dy": -5}}, "hidden_layers": ["parks"]}`
- **THEN** it is accepted

#### Scenario: Unknown layer rejected
- **WHEN** the edit list contains `"hidden_layers": ["buildings"]`
- **THEN** it is rejected as invalid, naming `buildings`

#### Scenario: Degenerate polygon rejected
- **WHEN** an erase polygon has two points
- **THEN** the edit list is rejected as invalid

### Requirement: Apply edits when rendering
The CLI SHALL accept `--edits <file>` with an edit list. An unreadable file or an invalid edit list SHALL be rejected with an error before any download. The edits SHALL apply to every output format (`png`, `svg`, `pdf`, `plotter`) and every theme:
- **Erase regions** remove all map content (roads, water, parks) inside each polygon, so the background shows through. In plotter output, no stroke of those layers lies inside an erase polygon. Erase regions SHALL NOT remove text or the OpenStreetMap attribution.
- **Text offsets** move the city name, country, coordinates or divider by `dx`/`dy` mm from their normal position. In plotter output, the map knockout behind the text moves with it.
- **Hidden text** leaves out that line, and in plotter output its knockout too.
- **Hidden layers** leave out those map layers entirely.

The OpenStreetMap attribution SHALL always be drawn and cannot be moved, hidden or erased. Without `--edits`, output SHALL be unchanged.

#### Scenario: Erase in plotter output
- **WHEN** a plotter SVG is rendered with an erase rectangle from (20, 20) to (80, 60) mm
- **THEN** no road, water or park stroke lies inside that rectangle, and strokes outside it are unaffected

#### Scenario: Erase in raster output
- **WHEN** a PNG is rendered with the same erase rectangle
- **THEN** that area shows only the theme background colour

#### Scenario: Edits survive a theme change
- **WHEN** the same edit list is used to render with theme `noir` and then with theme `ocean`
- **THEN** both posters have the same erased area and the same text positions

#### Scenario: Move the city name
- **WHEN** the edit list sets `text.city.dy` to `-10`
- **THEN** the city name is drawn 10 mm higher than without edits, in both PNG and plotter output

#### Scenario: Hide coordinates
- **WHEN** the edit list sets `text.coords.hidden` to `true`
- **THEN** the poster has no coordinates line, and the attribution is still present

#### Scenario: Hide parks
- **WHEN** the edit list hides `parks`
- **THEN** the poster contains no park fill, and in plotter output no parks layer

#### Scenario: Invalid edits file
- **WHEN** the user passes `--edits broken.json` and the file is not valid JSON
- **THEN** the tool prints an error and exits with a non-zero status without downloading

### Requirement: In-browser editor
In the Customize step, the web interface SHALL offer editing tools on the preview:
- **Erase**: draw a rectangle or freehand polygon on the preview to add an erase region
- **Select**: select an existing erase region to delete it
- **Move text**: drag the city, country, coordinates or divider to a new position
- **Hide text**: toggle city, country, coordinates or divider on or off
- **Layers**: toggle each map layer on or off
- **Undo/redo**, and **reset all edits**

Positions drawn on the preview SHALL be converted to page millimetres, so edits land in the same place at any preview size and in the exported file. The current edits SHALL be shown as an overlay right away, before the re-rendered preview arrives. Every change SHALL trigger a re-render of the preview with the edit list, and the export SHALL use the same edit list. The edit list SHALL be kept when the theme, format, labels or plotter options change. It SHALL be cleared, after the user confirms, when the user goes back to Location and loads a different location or size.

#### Scenario: Erase from the preview
- **WHEN** the user draws a rectangle over a stadium on the preview
- **THEN** the region appears as an overlay at once, and the next preview and the exported poster show the stadium area erased

#### Scenario: Drag city name
- **WHEN** the user drags the city name 20 mm upward on the preview
- **THEN** the exported poster has the city name 20 mm higher

#### Scenario: Undo
- **WHEN** the user adds an erase region and presses undo
- **THEN** the region is removed and the preview re-renders without it

#### Scenario: Edits kept across theme change
- **WHEN** the user has erased a region and then picks another theme
- **THEN** the new preview uses the new theme and still has the region erased

#### Scenario: New location clears edits
- **WHEN** the user goes back to Location, changes the city, confirms and loads the map
- **THEN** the edit list is empty
