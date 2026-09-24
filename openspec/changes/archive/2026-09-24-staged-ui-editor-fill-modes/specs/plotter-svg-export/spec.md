# Spec Delta

## MODIFIED Requirements

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

## ADDED Requirements

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
