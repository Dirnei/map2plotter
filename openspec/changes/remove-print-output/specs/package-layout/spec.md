# Spec Delta

## ADDED Requirements

### Requirement: Bundled data without fonts
The built-in themes and the web interface's static files SHALL be part of the package. They SHALL be found relative to the package, not to the current working directory. The package SHALL NOT bundle or download any font files: poster text uses the single-line pen font of the plotter renderer. Map data SHALL still be cached in `cache` in the current working directory, or in `CACHE_DIR` when that is set. Posters without `--output` SHALL still be written to `posters` in the current working directory.

#### Scenario: Themes from another directory
- **WHEN** the user runs `map2plotter --list-themes` in a directory that has no `themes/` folder
- **THEN** all built-in themes are listed

#### Scenario: Text without font files
- **WHEN** the user renders a poster in a directory that has no `fonts/` folder, with no network access other than the map data
- **THEN** the poster text is drawn as single-line pen strokes, and no font file is read or downloaded

## REMOVED Requirements

### Requirement: Bundled data independent of the working directory
**Reason**: The bundled Roboto fonts and the Google Fonts cache existed only for print output. It is replaced by "Bundled data without fonts", which keeps the themes, static files, cache and posters rules unchanged.
**Migration**: See "Bundled data without fonts".
