# Spec Delta

## ADDED Requirements

### Requirement: Pen colour overrides
The CLI SHALL accept `--color KEY=#RRGGBB`, repeatable. `KEY` SHALL be one of the pen colour keys:
- `text`
- `water`, `parks`
- `road_motorway`, `road_primary`, `road_secondary`, `road_tertiary`, `road_residential`, `road_default`

The value SHALL be a six-digit hex colour, with case ignored. Each override SHALL replace that colour of the selected theme for the whole run. With `--all-themes`, the overrides SHALL apply to every generated theme. When the same key is given twice, the last value SHALL win. An unknown key or an invalid colour SHALL be rejected with an error before any download. Without `--color`, colours SHALL come from the theme as before. Theme files MAY contain other keys (for example `bg` from older themes). They SHALL be ignored, and SHALL NOT be accepted by `--color`.

#### Scenario: Override water
- **WHEN** the user runs `--theme terracotta --color water=#1F5FA8`
- **THEN** the water paths are in a layer with stroke `#1f5fa8`, and all other layers keep the terracotta colours

#### Scenario: Background key rejected
- **WHEN** the user passes `--color bg=#000000`
- **THEN** the tool prints an error naming `bg` and exits with a non-zero status without downloading

#### Scenario: Invalid key rejected
- **WHEN** the user passes `--color buildings=#000000`
- **THEN** the tool prints an error naming `buildings` and exits with a non-zero status without downloading

#### Scenario: Invalid colour rejected
- **WHEN** the user passes `--color water=blue`
- **THEN** the tool prints an error and exits with a non-zero status without downloading

## REMOVED Requirements

### Requirement: Colour overrides
**Reason**: Its print-output behaviour is gone, so it is replaced by "Pen colour overrides", which covers the same ground for the plotter SVG only.
**Migration**: See "Pen colour overrides".
