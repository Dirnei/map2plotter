# poster-web-ui Specification

## Purpose

Provide a local web interface where users configure every poster option in a form, run the existing poster generator command, follow its progress, and preview, download and browse the generated posters.

## Requirements

### Requirement: Start the web server
The project SHALL provide a web server started with `python web_app.py`. By default it SHALL listen on `127.0.0.1:8000`. It SHALL accept `--host` and `--port` options. When started, it SHALL print the URL it serves.

#### Scenario: Default start
- **WHEN** the user runs `python web_app.py`
- **THEN** the page is reachable at `http://127.0.0.1:8000/` and is not reachable from other machines

#### Scenario: Custom bind address
- **WHEN** the user runs `python web_app.py --host 0.0.0.0 --port 9000`
- **THEN** the page is served on port 9000 on all interfaces

### Requirement: Configuration form covers all CLI options
The page SHALL provide inputs for every poster option of `create_map_poster.py`:
- city and country (both required)
- latitude and longitude (optional, but both must be set together)
- distance
- theme, or all themes
- width and height in mm
- country label
- display city and display country
- font family
- output format (`png`, `svg`, `pdf`, `plotter`)
- pen width and hatch spacing

Defaults SHALL match the CLI defaults. The plotter-only inputs SHALL be shown only when the format is `plotter`.

#### Scenario: Defaults match CLI
- **WHEN** the page is opened
- **THEN** the theme is `terracotta`, the distance is 18000, the width is 300 mm, the height is 400 mm, the format is `png` and the pen width is 0.3

#### Scenario: Plotter options toggle
- **WHEN** the user selects format `plotter`
- **THEN** the pen width and hatch spacing inputs become visible, and they are hidden again when another format is selected

### Requirement: Theme selection with preview
The page SHALL list all themes found in the `themes/` directory, with their name, their description and swatches of their colours. The theme list SHALL reflect the directory contents when the page loads.

#### Scenario: Themes listed
- **WHEN** the page loads and `themes/` contains `noir.json` and `terracotta.json`
- **THEN** both themes are selectable, each shown with its display name and colour swatches

### Requirement: Server-side validation
The server SHALL validate a submitted configuration before running anything, and SHALL reject invalid input with an error message per field. The rules are:
- city and country are required
- latitude and longitude must be set together, and must be parseable by the CLI's coordinate parser
- numeric values must be greater than 0
- width and height must not exceed 500 mm, except for `plotter`, which has no upper limit
- the theme must exist
- the format must be one of the four supported values
- for `plotter`, the hatch spacing must not be less than the pen width

#### Scenario: Missing city
- **WHEN** a generation request is submitted without a city
- **THEN** the server responds with a validation error naming the city field, and no process is started

#### Scenario: Invalid plotter hatch spacing
- **WHEN** format is `plotter`, pen width is 0.5 and hatch spacing is 0.2
- **THEN** the server responds with a validation error naming the hatch spacing field

### Requirement: Invoke the existing CLI
On a valid request, the server SHALL run `create_map_poster.py` as a separate process, using the same Python interpreter. It SHALL pass the configuration as a command-line argument list, never through a shell. Options left empty SHALL be omitted, so the CLI defaults apply. The page SHALL display the equivalent command line so the user can copy it.

#### Scenario: Command built from form
- **WHEN** the user submits city "Paris", country "France", theme "noir", distance 10000, format "svg"
- **THEN** the process runs with the arguments `--city Paris --country France --theme noir --distance 10000 --format svg`, plus `--width`/`--height` in mm, and the page shows that command

#### Scenario: No shell interpretation
- **WHEN** the city is `Paris; rm -rf /`
- **THEN** the whole string is passed as the single `--city` argument value and no shell command is executed

### Requirement: Live progress
While a job runs, the page SHALL show the process output as it is produced, and the job status (running, succeeded, failed or cancelled). When the process exits with a non-zero code, the page SHALL show the job as failed and keep the full output visible.

#### Scenario: Output streams
- **WHEN** the CLI prints "Downloading street network" during a job
- **THEN** the line appears in the page's log view before the job finishes

#### Scenario: Failure reported
- **WHEN** the CLI exits with status 1
- **THEN** the page shows the job as failed along with the output that explains the error

### Requirement: Single job and cancellation
The server SHALL run at most one generation at a time. A generation request made while a job is running SHALL be rejected with a message that a job is already running. The user SHALL be able to cancel the running job. Cancelling SHALL terminate the process and mark the job as cancelled.

#### Scenario: Concurrent request rejected
- **WHEN** a job is running and another generation is submitted
- **THEN** the server rejects the second request with a "job already running" error, and the first job continues

#### Scenario: Cancel
- **WHEN** the user presses cancel during a running job
- **THEN** the process is terminated, the job status becomes cancelled and a new job can be started

### Requirement: Result preview and download
When a job succeeds, the page SHALL show every poster file the job created:
- PNG and SVG files are previewed inline in the page
- PDF files are shown as a link
- every file has a download action that serves it as an attachment

#### Scenario: Single poster shown
- **WHEN** a PNG job succeeds
- **THEN** the new PNG is displayed on the page with a download button

#### Scenario: All themes
- **WHEN** a job with "all themes" succeeds
- **THEN** one result entry per generated file is shown

### Requirement: Poster history
The page SHALL list the poster files in `posters/` (PNG, SVG and PDF), newest first. Each entry SHALL show its file name, creation time and size, together with a preview or open link and a download action. The list SHALL refresh after each finished job.

#### Scenario: History lists existing files
- **WHEN** `posters/` contains three posters and the page loads
- **THEN** all three are listed with the newest first

### Requirement: Safe file access
The server SHALL serve files only from the `posters/` directory. It SHALL reject file requests whose name resolves outside that directory, or whose extension is not `png`, `svg` or `pdf`.

#### Scenario: Path traversal rejected
- **WHEN** a client requests the poster file `../create_map_poster.py`
- **THEN** the server responds with an error (not found or bad request) and does not return the file

### Requirement: Container hosts the web interface
The Docker image SHALL start the web interface on port 8000, listening on all container interfaces, when it is run without arguments. When the first argument starts with `-`, the image SHALL run the poster CLI with those arguments instead. The project SHALL provide a Docker Compose file that runs the web interface. That file SHALL publish the port on the host's loopback interface by default, and SHALL persist generated posters and the map data cache in the project's `posters/` and `cache/` directories.

#### Scenario: Container defaults to web UI
- **WHEN** the user runs `docker run -p 127.0.0.1:8000:8000 <image>` without arguments
- **THEN** the web interface is reachable at `http://localhost:8000/`

#### Scenario: CLI still available in container
- **WHEN** the user runs `docker run <image> --city Paris --country France`
- **THEN** the poster CLI runs with those arguments, as it did before

#### Scenario: Compose
- **WHEN** the user runs `docker compose up -d` in the project directory
- **THEN** the web interface is served on `127.0.0.1:8000`, and posters generated through it appear in the host's `posters/` directory

### Requirement: Choose the OpenStreetMap server
The page SHALL offer a dropdown with these choices:
- "Automatic (with fallback)"
- each known public Overpass server
- "Custom…", which shows a URL field

The chosen server SHALL be passed to the CLI as `--overpass-url`. The preselected choice SHALL be the server's `OVERPASS_URL` environment variable when it is set, and automatic otherwise, unless the user saved another choice. A "Check servers" action SHALL test all known servers, plus a custom URL if one is entered, in parallel, and show for each whether it answered, with its response time or failure reason.

#### Scenario: Server passed to the CLI
- **WHEN** the user selects `lz4.overpass-api.de` and generates a poster
- **THEN** the executed command contains `--overpass-url https://lz4.overpass-api.de/api`

#### Scenario: Check servers
- **WHEN** the user presses "Check servers" while the main server times out and `maps.mail.ru` answers
- **THEN** the page lists the main server with a failure reason and `maps.mail.ru` with a check mark and its response time

#### Scenario: Invalid custom URL
- **WHEN** the user enters `not a url` as a custom server and generates
- **THEN** the server rejects the request with a validation error for the OpenStreetMap server field
