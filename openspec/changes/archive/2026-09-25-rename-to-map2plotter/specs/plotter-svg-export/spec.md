# Spec Delta

## MODIFIED Requirements

### Requirement: Plotter output format
The CLI SHALL accept `plotter` as a value of `--format`. When it is selected, the tool SHALL write a single `.svg` file to the `posters/` directory. The filename SHALL follow the existing `<city>_<theme>_<timestamp>` pattern with a `.svg` extension. The existing `png`, `svg` and `pdf` formats SHALL behave as before.

#### Scenario: Plotter format writes an SVG file
- **WHEN** the user runs `map2plotter -c Paris -C France --format plotter`
- **THEN** a file ending in `.svg` is written to `posters/` and the command exits successfully

#### Scenario: Existing formats unchanged
- **WHEN** the user runs with `--format png`
- **THEN** a PNG poster is produced exactly as before this change

#### Scenario: Plotter format with all themes
- **WHEN** the user runs with `--format plotter --all-themes`
- **THEN** one plotter SVG is written per theme
