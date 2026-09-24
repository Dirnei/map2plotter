# Spec Delta

## Purpose

Let users change single poster colours on top of a theme, from the command line and from the web interface, for every output format.

## ADDED Requirements

### Requirement: Colour overrides
The CLI SHALL accept `--color KEY=#RRGGBB`, repeatable. `KEY` SHALL be one of the theme colour keys:
- `bg`, `text`, `gradient_color`
- `water`, `parks`
- `road_motorway`, `road_primary`, `road_secondary`, `road_tertiary`, `road_residential`, `road_default`

The value SHALL be a six-digit hex colour, with case ignored. Each override SHALL replace that colour of the selected theme for the whole run, in every output format. With `--all-themes`, the overrides SHALL apply to every generated theme. When the same key is given twice, the last value SHALL win. An unknown key or an invalid colour SHALL be rejected with an error before any download. Without `--color`, colours SHALL come from the theme as before.

#### Scenario: Override water in a plotter SVG
- **WHEN** the user runs `--format plotter --theme terracotta --color water=#1F5FA8`
- **THEN** the water paths are in a layer with stroke `#1f5fa8`, and all other layers keep the terracotta colours

#### Scenario: Override in a PNG
- **WHEN** the user runs `--format png --color text=#000000`
- **THEN** the city name, country and coordinates are drawn in black

#### Scenario: Invalid key rejected
- **WHEN** the user passes `--color buildings=#000000`
- **THEN** the tool prints an error naming `buildings` and exits with a non-zero status without downloading

#### Scenario: Invalid colour rejected
- **WHEN** the user passes `--color water=blue`
- **THEN** the tool prints an error and exits with a non-zero status without downloading
