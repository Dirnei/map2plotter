# poster-output Specification

## Purpose

Let scripts and the web interface choose exactly where a poster is written and at what raster resolution, so previews can be produced without touching the `posters/` directory.

## Requirements

### Requirement: Explicit output path
The CLI SHALL accept `--output <path>`. When it is given, the poster SHALL be written to exactly that path instead of the generated `posters/<city>_<theme>_<timestamp>` name, and missing parent directories SHALL be created. The file extension SHALL match the format: `.png` for `png`, `.svg` for `svg` and `plotter`, and `.pdf` for `pdf`. A mismatching extension SHALL be rejected with an error before any download. `--output` together with `--all-themes` SHALL be rejected with an error. Without `--output`, file naming SHALL be unchanged.

#### Scenario: Output to a given file
- **WHEN** the user runs `--format png --output previews/p.png`
- **THEN** the poster is written to `previews/p.png` and no new file appears in `posters/`

#### Scenario: Extension mismatch rejected
- **WHEN** the user runs `--format pdf --output out.png`
- **THEN** the tool prints an error and exits with a non-zero status without downloading or writing a file

#### Scenario: Not combinable with all themes
- **WHEN** the user runs `--all-themes --output out.png`
- **THEN** the tool prints an error and exits with a non-zero status

### Requirement: Raster resolution
The CLI SHALL accept `--dpi <n>`, a positive integer, with a default of 300. It SHALL set the resolution of PNG output, so the image is `width_mm / 25.4 × dpi` pixels wide (rounded). The option SHALL have no effect on `svg`, `pdf` and `plotter` output. A value of 0 or less SHALL be rejected with an error.

#### Scenario: Low-resolution preview
- **WHEN** the user runs `--format png --width 254 --height 254 --dpi 50`
- **THEN** the PNG is 500 × 500 pixels

#### Scenario: Default unchanged
- **WHEN** the user runs `--format png` without `--dpi`
- **THEN** the PNG is rendered at 300 dpi as before

#### Scenario: Invalid dpi rejected
- **WHEN** the user passes `--dpi 0`
- **THEN** the tool prints an error and exits with a non-zero status
