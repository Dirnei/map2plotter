# package-layout Specification

## Purpose

Defines how the map poster generator is started as a Python package, and makes sure its built-in data is found no matter which directory it is run from.

## Requirements

### Requirement: Package commands
The project SHALL be a Python package named `maptoposter` that provides two commands once the project is installed into an environment, for example with `uv sync`:
- `maptoposter`: the poster CLI, with all existing options and defaults.
- `maptoposter-web`: the web interface.

Running `python -m maptoposter` SHALL behave exactly like `maptoposter`.

#### Scenario: CLI command
- **WHEN** the user runs `uv run maptoposter -c Paris -C France -t noir` in a clone
- **THEN** a Paris poster with the noir theme is written to `posters/`, as `create_map_poster.py` did before

#### Scenario: Module invocation
- **WHEN** the user runs `python -m maptoposter --help` in the project environment
- **THEN** the same help as `maptoposter --help` is printed

### Requirement: Bundled data independent of the working directory
The built-in themes, the default Roboto fonts and the web interface's static files SHALL be part of the package. They SHALL be found relative to the package, not to the current working directory. Map data SHALL still be cached in `cache` in the current working directory, or in `CACHE_DIR` when that is set. Posters without `--output` SHALL still be written to `posters` in the current working directory. Downloaded Google Fonts SHALL be cached in a `fonts` subdirectory of the map data cache directory.

#### Scenario: Themes from another directory
- **WHEN** the user runs `maptoposter --list-themes` in a directory that has no `themes/` folder
- **THEN** all built-in themes are listed

#### Scenario: Default fonts from another directory
- **WHEN** the user renders a poster without `--font-family` in a directory that has no `fonts/` folder
- **THEN** the poster text uses the bundled Roboto fonts, and no "Font not found" warning is printed

#### Scenario: Google Font cache location
- **WHEN** the user renders with `--font-family "Open Sans"` and `CACHE_DIR=/data/cache`
- **THEN** the downloaded font files are stored in `/data/cache/fonts/`
