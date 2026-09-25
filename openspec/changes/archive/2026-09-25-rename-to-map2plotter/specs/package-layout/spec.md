# Spec Delta

## MODIFIED Requirements

### Requirement: Package commands
The project SHALL be a Python package named `map2plotter` that provides two commands once the project is installed into an environment, for example with `uv sync`:
- `map2plotter`: the poster CLI, with all existing options and defaults.
- `map2plotter-web`: the web interface.

Running `python -m map2plotter` SHALL behave exactly like `map2plotter`. Installing the project SHALL NOT install a `maptoposter` package or `maptoposter` / `maptoposter-web` commands, so that it can be installed next to other projects that use those names.

#### Scenario: CLI command
- **WHEN** the user runs `uv run map2plotter -c Paris -C France -t noir` in a clone
- **THEN** a Paris poster with the noir theme is written to `posters/`

#### Scenario: Module invocation
- **WHEN** the user runs `python -m map2plotter --help` in the project environment
- **THEN** the same help as `map2plotter --help` is printed, and it names the program `map2plotter`

#### Scenario: No old names installed
- **WHEN** the project is installed into an empty environment
- **THEN** the environment contains neither a `maptoposter` command nor an importable `maptoposter` package

### Requirement: Bundled data independent of the working directory
The built-in themes, the default Roboto fonts and the web interface's static files SHALL be part of the package. They SHALL be found relative to the package, not to the current working directory. Map data SHALL still be cached in `cache` in the current working directory, or in `CACHE_DIR` when that is set. Posters without `--output` SHALL still be written to `posters` in the current working directory. Downloaded Google Fonts SHALL be cached in a `fonts` subdirectory of the map data cache directory.

#### Scenario: Themes from another directory
- **WHEN** the user runs `map2plotter --list-themes` in a directory that has no `themes/` folder
- **THEN** all built-in themes are listed

#### Scenario: Default fonts from another directory
- **WHEN** the user renders a poster without `--font-family` in a directory that has no `fonts/` folder
- **THEN** the poster text uses the bundled Roboto fonts, and no "Font not found" warning is printed

#### Scenario: Google Font cache location
- **WHEN** the user renders with `--font-family "Open Sans"` and `CACHE_DIR=/data/cache`
- **THEN** the downloaded font files are stored in `/data/cache/fonts/`
