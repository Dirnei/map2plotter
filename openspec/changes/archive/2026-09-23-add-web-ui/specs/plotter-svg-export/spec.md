# Spec Delta

## ADDED Requirements

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

## REMOVED Requirements

### Requirement: Physical size in millimetres
**Reason**: It allowed the size to be derived from `--width`/`--height` in inches. Sizes are now given only in millimetres.
**Migration**: Use `--width`/`--height` in mm (they replace both the old inch options and `--width-mm`/`--height-mm`). The requirement "Poster size in millimetres" replaces this one.
