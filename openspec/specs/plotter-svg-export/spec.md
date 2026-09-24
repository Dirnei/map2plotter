# plotter-svg-export Specification

## Purpose

Produce a map poster as a pen-plotter-ready SVG in which every mark is a stroked path, sized in real millimetres and computed for a configured pen width.

## Requirements

### Requirement: Plotter output format
The CLI SHALL accept `plotter` as a value of `--format`. When it is selected, the tool SHALL write a single `.svg` file to the `posters/` directory. The filename SHALL follow the existing `<city>_<theme>_<timestamp>` pattern with a `.svg` extension. The existing `png`, `svg` and `pdf` formats SHALL behave as before.

#### Scenario: Plotter format writes an SVG file
- **WHEN** the user runs `create_map_poster.py -c Paris -C France --format plotter`
- **THEN** a file ending in `.svg` is written to `posters/` and the command exits successfully

#### Scenario: Existing formats unchanged
- **WHEN** the user runs with `--format png`
- **THEN** a PNG poster is produced exactly as before this change

#### Scenario: Plotter format with all themes
- **WHEN** the user runs with `--format plotter --all-themes`
- **THEN** one plotter SVG is written per theme

### Requirement: Poster size in millimetres
The CLI SHALL accept `--width` and `--height` (short forms `-W`/`-H`) as the poster size in millimetres. Both must be positive numbers, and they default to 300 and 400. The plotter SVG root element SHALL declare `width` and `height` in `mm` units that match these values. Its `viewBox` SHALL be `0 0 <width> <height>`, so that one user unit equals one millimetre. No other size unit SHALL be accepted. The map SHALL be cropped to the aspect ratio of the configured size.

#### Scenario: Explicit mm size
- **WHEN** the user passes `--format plotter --width 300 --height 400`
- **THEN** the SVG root has `width="300mm"`, `height="400mm"` and `viewBox="0 0 300 400"`

#### Scenario: Default size
- **WHEN** the user passes `--format plotter` without size options
- **THEN** the SVG root has `width="300mm"` and `height="400mm"`

#### Scenario: Large format not limited
- **WHEN** the user passes `--format plotter --width 841 --height 1189`
- **THEN** the SVG root has `width="841mm"` and `height="1189mm"`

#### Scenario: All geometry inside the page
- **WHEN** a plotter SVG is generated
- **THEN** every path coordinate lies within `[0, width] × [0, height]`

#### Scenario: Invalid size rejected
- **WHEN** the user passes `--width 0` or a negative value
- **THEN** the tool prints an error and exits with a non-zero status without writing a file

### Requirement: Configurable pen width
The CLI SHALL accept `--pen-width` in millimetres (a positive number, default `0.3`). Every path in the plotter SVG SHALL have `fill="none"` and a `stroke-width` equal to the pen width. The pen width SHALL be used to compute multi-stroke road fills and the default hatch spacing.

#### Scenario: Stroke width applied
- **WHEN** the user passes `--pen-width 0.5`
- **THEN** every stroked element in the SVG has `stroke-width` 0.5 and no element has a non-`none` fill

#### Scenario: Invalid pen width rejected
- **WHEN** the user passes `--pen-width 0` or a negative value
- **THEN** the tool prints an error and exits with a non-zero status

### Requirement: Stroke-only output
The plotter SVG SHALL contain only stroked vector paths or polylines. It SHALL NOT contain filled shapes, raster images, gradients, `<text>` elements or embedded fonts. The background colour and the top and bottom gradient fades SHALL be omitted.

#### Scenario: No non-plottable elements
- **WHEN** a plotter SVG is generated with any theme
- **THEN** it contains no `<image>`, `<text>`, `<linearGradient>`, `<radialGradient>` or `<font>` elements and no filled shapes

### Requirement: Road width rendered with multiple strokes
Each road-hierarchy class (motorway, primary, secondary, tertiary, residential/default) SHALL have a target width in mm. The target width SHALL scale with the poster's physical size and preserve the existing relative hierarchy. When a class's target width is greater than the pen width, its roads SHALL be drawn with enough parallel strokes, spaced no more than one pen width apart, to cover the target width. When the target width is less than or equal to the pen width, the roads SHALL be drawn as a single centerline stroke. Where roads of different classes overlap, only the higher class SHALL be drawn in the overlapping area.

#### Scenario: Wide road gets several strokes
- **WHEN** motorway target width is 1.2 mm and the pen width is 0.3 mm
- **THEN** a motorway is drawn with strokes that cover its 1.2 mm width with gaps no larger than 0.3 mm

#### Scenario: Thin road gets one stroke
- **WHEN** residential target width is 0.25 mm and the pen width is 0.3 mm
- **THEN** each residential road is drawn as a single stroke along its centerline

#### Scenario: Thicker pen reduces stroke count
- **WHEN** the same poster is generated with `--pen-width 0.6` instead of `0.3`
- **THEN** wide roads use fewer parallel strokes while covering the same target width

#### Scenario: Higher class knocks out lower class
- **WHEN** a residential road meets a primary road
- **THEN** no residential stroke is drawn inside the primary road's area

### Requirement: Hatch-filled areas
Water and park polygons SHALL be filled with pen lines clipped to the polygon, holes included. The fill mode SHALL be configurable per area type with `--water-fill` and `--parks-fill`, each either `hatch` or `concentric`, both defaulting to `hatch`:
- In `hatch` mode the area is filled with parallel straight lines. Water and parks SHALL use different hatch angles.
- In `concentric` mode the area is filled with closed contours that follow the area's outline and holes, each inset from the previous one by the spacing, until the area is used up.

The line spacing SHALL be configurable per area type with `--water-spacing` and `--parks-spacing` in mm. Each SHALL default to `--hatch-spacing`, which in turn defaults to the pen width. No spacing SHALL be less than the pen width. Road areas and the text block SHALL be excluded from every fill.

#### Scenario: Water is hatched
- **WHEN** the map area contains a lake and no fill options are given
- **THEN** the lake is drawn as parallel lines, clipped to its outline, spaced by the hatch spacing

#### Scenario: Custom hatch spacing
- **WHEN** the user passes `--hatch-spacing 1.5`
- **THEN** adjacent fill lines inside water and park areas are 1.5 mm apart

#### Scenario: Per-area spacing
- **WHEN** the user passes `--water-spacing 0.6 --parks-spacing 2`
- **THEN** adjacent water fill lines are 0.6 mm apart and adjacent park fill lines are 2 mm apart

#### Scenario: Concentric water
- **WHEN** the user passes `--water-fill concentric --water-spacing 1`
- **THEN** each lake is drawn as nested closed contours that follow its shoreline, 1 mm apart, and no straight hatch lines are drawn in water

#### Scenario: Mixed modes
- **WHEN** the user passes `--water-fill concentric` and no parks option
- **THEN** water is filled concentrically and parks are still hatched

#### Scenario: Hatch spacing below pen width rejected
- **WHEN** the user passes `--pen-width 0.5 --hatch-spacing 0.2`
- **THEN** the tool prints an error and exits with a non-zero status

#### Scenario: Per-area spacing below pen width rejected
- **WHEN** the user passes `--pen-width 0.5 --parks-spacing 0.3`
- **THEN** the tool prints an error and exits with a non-zero status

#### Scenario: Invalid fill mode rejected
- **WHEN** the user passes `--water-fill spiral`
- **THEN** the tool prints an error and exits with a non-zero status

#### Scenario: Roads not hatched over
- **WHEN** a road crosses a park
- **THEN** no park fill line is drawn inside the road's area, in either fill mode

### Requirement: Single-stroke typography
The city name, the country, the coordinates, the divider line and the OpenStreetMap attribution SHALL be drawn as stroked paths with a single-line (stroke) font. Their relative placement and scaling SHALL match the existing poster layout. The map SHALL be knocked out, with no strokes, within the text block region so that text is not overdrawn. City name formatting rules (letter spacing and uppercase for Latin scripts) SHALL be preserved. Characters that the stroke font cannot render SHALL be skipped with a printed warning, not fail the run.

#### Scenario: Text drawn as paths
- **WHEN** a plotter SVG is generated for Paris
- **THEN** "P  A  R  I  S", "FRANCE", the coordinates and "© OpenStreetMap contributors" appear as stroked paths in the text layer

#### Scenario: Map cleared behind text
- **WHEN** a plotter SVG is generated
- **THEN** no road or hatch stroke intersects the text block region

#### Scenario: Unsupported glyphs
- **WHEN** the display city contains characters outside the stroke font (e.g. Japanese)
- **THEN** a warning is printed, unsupported characters are omitted and the SVG is still written

### Requirement: One layer per pen colour
Paths SHALL be grouped into SVG layers (`<g>` with `inkscape:groupmode="layer"`), one per distinct theme colour used. Theme keys that share a colour value SHALL share one layer. Each layer SHALL set its `stroke` to that colour and SHALL have an `inkscape:label` that includes the colour and the element types it contains.

#### Scenario: Layers per colour
- **WHEN** a theme uses five distinct road colours plus distinct water, parks and text colours
- **THEN** the SVG contains one layer for each of those distinct colours

#### Scenario: Shared colours merged
- **WHEN** `road_tertiary` and `road_default` have the same colour
- **THEN** their paths are placed in the same layer

### Requirement: Optional water outline
The CLI SHALL accept `--water-outline`, which is off by default. When it is on, the boundary of every water area, including the boundaries of islands (holes), SHALL be drawn as a stroke in the water layer. The outline SHALL be clipped to the page and SHALL NOT be drawn inside road areas or the text block. When the outline is on, the water fill SHALL keep at least the water spacing away from the outline, so the first fill line does not overlap it. Without the option, no outline SHALL be drawn and the fill SHALL be unchanged.

#### Scenario: Lake outlined
- **WHEN** the user passes `--format plotter --water-outline` and the map contains a lake
- **THEN** the water layer contains a closed stroke along the lake's shoreline in addition to the fill

#### Scenario: Island outlined
- **WHEN** a lake with an island is drawn with `--water-outline`
- **THEN** the island's shoreline is also stroked

#### Scenario: Outline respects roads
- **WHEN** a bridge crosses a river drawn with `--water-outline`
- **THEN** no outline stroke is drawn inside the bridge's road area

#### Scenario: Off by default
- **WHEN** a plotter SVG is generated without `--water-outline`
- **THEN** water contains fill lines only
