# Spec Delta

## MODIFIED Requirements

### Requirement: In-browser editor
In the Customize step, the web interface SHALL offer editing tools on the preview:
- **Erase**: draw a rectangle or freehand polygon on the preview to add an erase region
- **Select**: select an existing erase region to delete it
- **Move text**: drag the city, country, coordinates or divider to a new position
- **Hide text**: toggle city, country, coordinates or divider on or off
- **Layers**: toggle each map layer on or off, in the pens list
- **Undo/redo**, and **reset all edits**

Positions drawn on the preview SHALL be converted to page millimetres, so edits land in the same place at any preview size and in the exported file. The current edits SHALL be shown as an overlay right away, before the re-rendered preview arrives. Every change SHALL trigger a re-render of the preview with the edit list, and the export SHALL use the same edit list. The edit list SHALL be kept when the pen colours, labels or plotter options change. It SHALL be cleared, after the user confirms, when the user goes back to Location and loads a different location or size.

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
- **WHEN** the user has erased a region and then applies another theme's colours with "Start from theme"
- **THEN** the preview uses the new colours and still has the region erased

#### Scenario: New location clears edits
- **WHEN** the user goes back to Location, changes the city, confirms and loads the map
- **THEN** the edit list is empty

## ADDED Requirements

### Requirement: Apply edits to the plotter SVG
The CLI SHALL accept `--edits <file>` with an edit list. An unreadable file or an invalid edit list SHALL be rejected with an error before any download. The edits SHALL apply to the plotter SVG for every theme:
- **Erase regions** remove all map content (roads, water, parks) inside each polygon: no stroke of those layers lies inside an erase polygon. Erase regions SHALL NOT remove text or the OpenStreetMap attribution.
- **Text offsets** move the city name, country, coordinates or divider by `dx`/`dy` mm from their normal position, and the map knockout behind the text moves with it.
- **Hidden text** leaves out that line and its knockout.
- **Hidden layers** leave out those map layers entirely.

The OpenStreetMap attribution SHALL always be drawn and cannot be moved, hidden or erased. Without `--edits`, output SHALL be unchanged.

#### Scenario: Erase
- **WHEN** a plotter SVG is rendered with an erase rectangle from (20, 20) to (80, 60) mm
- **THEN** no road, water or park stroke lies inside that rectangle, and strokes outside it are unaffected

#### Scenario: Edits survive a theme change
- **WHEN** the same edit list is used to render with theme `noir` and then with theme `ocean`
- **THEN** both posters have the same erased area and the same text positions

#### Scenario: Move the city name
- **WHEN** the edit list sets `text.city.dy` to `-10`
- **THEN** the city name is drawn 10 mm higher than without edits

#### Scenario: Hide coordinates
- **WHEN** the edit list sets `text.coords.hidden` to `true`
- **THEN** the poster has no coordinates line, and the attribution is still present

#### Scenario: Hide parks
- **WHEN** the edit list hides `parks`
- **THEN** the poster contains no parks layer

#### Scenario: Invalid edits file
- **WHEN** the user passes `--edits broken.json` and the file is not valid JSON
- **THEN** the tool prints an error and exits with a non-zero status without downloading

## REMOVED Requirements

### Requirement: Apply edits when rendering
**Reason**: Its print-output behaviour is gone, so it is replaced by "Apply edits to the plotter SVG", which covers the same ground for the plotter SVG only.
**Migration**: See "Apply edits to the plotter SVG".
