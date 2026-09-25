# Spec Delta

## MODIFIED Requirements

### Requirement: Start the web server
The project SHALL provide a web server started with the `maptoposter-web` command. By default it SHALL listen on `127.0.0.1:8000`. It SHALL accept `--host` and `--port` options. When started, it SHALL print the URL it serves.

#### Scenario: Default start
- **WHEN** the user runs `maptoposter-web`
- **THEN** the page is reachable at `http://127.0.0.1:8000/` and is not reachable from other machines

#### Scenario: Custom bind address
- **WHEN** the user runs `maptoposter-web --host 0.0.0.0 --port 9000`
- **THEN** the page is served on port 9000 on all interfaces

### Requirement: Invoke the existing CLI
Every load, preview and export SHALL run the poster CLI as a separate process, as `python -m maptoposter` using the same Python interpreter as the server. The server SHALL pass the configuration as a command-line argument list, never through a shell. Options left empty SHALL be omitted, so the CLI defaults apply.
- Previews and exports SHALL pass `--cache-only`.
- Loads and previews SHALL pass `--output` pointing to the preview file, and PNG previews a reduced `--dpi`.
- When the edit list is not empty, it SHALL be written to a file in the working directory and passed with `--edits`.

The CLI process SHALL use the same posters and cache directories as the server. The page SHALL display the equivalent command line of the last export or load, starting with `maptoposter`, so the user can copy it.

#### Scenario: Command built from form
- **WHEN** the user has loaded Paris, France and exports with theme "noir", distance 10000 and format "svg"
- **THEN** the process runs with the arguments `--city Paris --country France --theme noir --distance 10000 --format svg --cache-only`, plus `--width`/`--height` in mm, and the page shows that command starting with `maptoposter`

#### Scenario: Plotter fill options passed
- **WHEN** the user exports a plotter poster with water fill `concentric`, water spacing 1 and the water outline on
- **THEN** the arguments contain `--water-fill concentric --water-spacing 1 --water-outline`

#### Scenario: No shell interpretation
- **WHEN** the city is `Paris; rm -rf /`
- **THEN** the whole string is passed as the single `--city` argument value and no shell command is executed
