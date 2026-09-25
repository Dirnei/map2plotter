# Spec Delta

## MODIFIED Requirements

### Requirement: Raster resolution
The CLI SHALL accept `--dpi <n>`, a positive integer, with a default of 300. It SHALL set the resolution of PNG output, so the image is `width_mm / 25.4 × dpi` pixels wide (rounded). The option SHALL have no effect on `svg`, `pdf` and `plotter` output. A value of 0 or less SHALL be rejected with an error.

A PNG SHALL NOT exceed 200,000,000 pixels in total, nor 65,535 pixels on either side. A request over either limit SHALL be rejected with an error before any download. The error SHALL state the resulting pixel size and the highest whole dpi that would fit. The poster size SHALL never be clamped or otherwise changed to fit a limit.

#### Scenario: Low-resolution preview
- **WHEN** the user runs `--format png --width 254 --height 254 --dpi 50`
- **THEN** the PNG is 500 × 500 pixels

#### Scenario: Default unchanged
- **WHEN** the user runs `--format png` without `--dpi`
- **THEN** the PNG is rendered at 300 dpi as before

#### Scenario: Invalid dpi rejected
- **WHEN** the user passes `--dpi 0`
- **THEN** the tool prints an error and exits with a non-zero status

#### Scenario: A0 PNG allowed
- **WHEN** the user runs `--format png --width 841 --height 1189` at the default 300 dpi
- **THEN** the PNG is 9933 × 14043 pixels

#### Scenario: Oversized PNG rejected with a suggestion
- **WHEN** the user runs `--format png --width 1000 --height 1500` at 300 dpi
- **THEN** the tool exits with a non-zero status before downloading, and the error states the pixel size and that at most 293 dpi fits

## ADDED Requirements

### Requirement: No size limit for vector output
SVG, PDF and plotter output SHALL accept any positive width and height. The output SHALL have exactly the requested size. The CLI SHALL NOT clamp or warn about large sizes for these formats.

#### Scenario: Large PDF
- **WHEN** the user runs `--format pdf --width 841 --height 1189`
- **THEN** the PDF page is 841 × 1189 mm

#### Scenario: Large SVG keeps its aspect ratio
- **WHEN** the user runs `--format svg --width 600 --height 900`
- **THEN** the SVG is 600 × 900 mm, not clamped to 500 mm
