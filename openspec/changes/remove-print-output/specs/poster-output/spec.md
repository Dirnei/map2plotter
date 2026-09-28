# Spec Delta

## MODIFIED Requirements

### Requirement: Explicit output path
The CLI SHALL accept `--output <path>`. When it is given, the poster SHALL be written to exactly that path instead of the generated `posters/<city>_<theme>_<timestamp>.svg` name, and missing parent directories SHALL be created. The path SHALL end in `.svg`, with case ignored. Any other extension SHALL be rejected with an error before any download. `--output` together with `--all-themes` SHALL be rejected with an error. Without `--output`, file naming SHALL be unchanged.

#### Scenario: Output to a given file
- **WHEN** the user runs `--output previews/p.svg`
- **THEN** the poster is written to `previews/p.svg` and no new file appears in `posters/`

#### Scenario: Extension mismatch rejected
- **WHEN** the user runs `--output out.png`
- **THEN** the tool prints an error saying the output must be an `.svg` file, and exits with a non-zero status without downloading or writing a file

#### Scenario: Not combinable with all themes
- **WHEN** the user runs `--all-themes --output out.svg`
- **THEN** the tool prints an error and exits with a non-zero status

## REMOVED Requirements

### Requirement: Raster resolution
**Reason**: map2plotter no longer produces raster (PNG) output, so there is no resolution to set and no pixel limit to enforce. The `--dpi` option is removed.
**Migration**: Drop `--dpi` from scripts. To get a raster image of a plotter SVG, convert it outside the tool (for example with Inkscape or a browser).

### Requirement: No size limit for vector output
**Reason**: With the SVG as the only output, "no size limit" is a property of the plotter output itself. It is now stated in `plotter-svg-export`'s "Poster size in millimetres".
**Migration**: None. Any positive size is still accepted without clamping.
