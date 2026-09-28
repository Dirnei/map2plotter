# Spec Delta

## MODIFIED Requirements

### Requirement: Poster size in millimetres
The CLI SHALL accept `--width` and `--height` (short forms `-W`/`-H`) as the poster size in millimetres. Both must be positive numbers, and they default to 300 and 400. Any positive size SHALL be accepted, and the output SHALL have exactly the requested size, without clamping or a size warning. The plotter SVG root element SHALL declare `width` and `height` in `mm` units that match these values. Its `viewBox` SHALL be `0 0 <width> <height>`, so that one user unit equals one millimetre. No other size unit SHALL be accepted. The map SHALL be cropped to the aspect ratio of the configured size.

#### Scenario: Explicit mm size
- **WHEN** the user passes `--width 300 --height 400`
- **THEN** the SVG root has `width="300mm"`, `height="400mm"` and `viewBox="0 0 300 400"`

#### Scenario: Default size
- **WHEN** the user passes no size options
- **THEN** the SVG root has `width="300mm"` and `height="400mm"`

#### Scenario: Large format not limited
- **WHEN** the user passes `--width 841 --height 1189`
- **THEN** the SVG root has `width="841mm"` and `height="1189mm"`

#### Scenario: All geometry inside the page
- **WHEN** a plotter SVG is generated
- **THEN** every path coordinate lies within `[0, width] × [0, height]`

#### Scenario: Invalid size rejected
- **WHEN** the user passes `--width 0` or a negative value
- **THEN** the tool prints an error and exits with a non-zero status without writing a file

### Requirement: Optional water outline
The CLI SHALL accept `--water-outline`, which is off by default. When it is on, the boundary of every water area, including the boundaries of islands (holes), SHALL be drawn as a stroke in the water layer. The outline SHALL be clipped to the page and SHALL NOT be drawn inside road areas or the text block. When the outline is on, the water fill SHALL keep at least the water spacing away from the outline, so the first fill line does not overlap it. Without the option, no outline SHALL be drawn and the fill SHALL be unchanged.

#### Scenario: Lake outlined
- **WHEN** the user passes `--water-outline` and the map contains a lake
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

## ADDED Requirements

### Requirement: SVG is the only output
The CLI SHALL always write a pen-plotter-ready SVG. It SHALL NOT offer any other output format and SHALL NOT accept a `--format` option. Each run SHALL write a single `.svg` file to the `posters/` directory, or one per theme with `--all-themes`. The filename SHALL follow the `<city>_<theme>_<timestamp>` pattern with a `.svg` extension.

#### Scenario: Plotter SVG written by default
- **WHEN** the user runs `map2plotter -c Paris -C France`
- **THEN** a file ending in `.svg` is written to `posters/` and the command exits successfully

#### Scenario: Format option rejected
- **WHEN** the user runs `map2plotter -c Paris -C France --format png`
- **THEN** the tool prints a usage error about the unknown option and exits with a non-zero status without downloading

#### Scenario: All themes
- **WHEN** the user runs with `--all-themes`
- **THEN** one plotter SVG is written per theme

## REMOVED Requirements

### Requirement: Plotter output format
**Reason**: Its print-output behaviour is gone, so it is replaced by "SVG is the only output", which covers the same ground for the plotter SVG only.
**Migration**: See "SVG is the only output".
