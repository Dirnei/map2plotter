# Spec Delta

## MODIFIED Requirements

### Requirement: Choose the workflow
The Location step SHALL start with a choice between two workflows:
- **Print poster**: output as PNG, SVG or PDF, with a size limit of 500 mm per side
- **Pen plotter**: stroke-only plotter SVG, with no size limit

The default is Print poster. The chosen workflow SHALL be part of the loaded location. The Customize step SHALL show the workflow, the place and the poster size in a header, and SHALL show only the options of that workflow:
- **Print**: the theme grid, file format (`png`, `svg`, `pdf`) and font family
- **Plotter**: the pens list (see "Pens in the plotter workflow") instead of the theme grid, plus pen width, hatch spacing, fill modes, per-area spacing and water outline. The font family SHALL be hidden, because plotter text always uses the single-line pen font.

Switching the workflow SHALL require going back to Location and loading again.

#### Scenario: Plotter workflow
- **WHEN** the user picks "Pen plotter", enters 600 × 900 mm and loads the map
- **THEN** the load succeeds, the preview is the plotter SVG, and Customize shows the pens list and pen options, without a theme grid, file format or font family choice

#### Scenario: Print size limited in Location
- **WHEN** the user picks "Print poster" and enters a width of 600 mm
- **THEN** "Load map" is rejected with an error on the width field that suggests the pen plotter workflow for larger sizes

## ADDED Requirements

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
