# Proposal

## Why

The generator has grown to about 20 CLI options: location, theme, size, fonts, i18n labels, output format and the plotter-specific pen/mm/hatch settings. That is hard to remember and easy to get wrong. Generating a poster can also take minutes, and you only see the result by opening a file in `posters/`. A local web page would let users configure everything in one form, run the existing command, watch it progress and see the result right away.

## What Changes

- Add a local web application, started with `python web_app.py`, that serves a single page. The page has a form covering every CLI option:
  - location: city, country, optional lat/lon override, distance
  - theme: picked from `themes/`, with colour swatches, or "all themes"
  - size: width and height in mm, for every format
  - labels: display city/country, country label, Google font family
  - output: format `png`/`svg`/`pdf`/`plotter`
  - plotter options (pen width, hatch spacing), shown only when `plotter` is selected
- The server validates the form and turns it into the argument list for `create_map_poster.py`. It then **invokes the existing CLI as a subprocess**. No poster logic is duplicated or re-implemented.
- The CLI output streams live to the page while the job runs. The page shows the exact command being executed so users can copy it and reuse it in a terminal.
- When the job finishes, the page shows the generated poster (PNG/SVG inline, a link for PDF) with a download button. With "all themes", every generated file is shown.
- A history panel lists the posters already in `posters/`, newest first, with preview and download.
- Only one generation runs at a time. The running job can be cancelled.
- The server binds to `127.0.0.1` by default. `--host`/`--port` flags allow running it in Docker (`0.0.0.0`).
- The Docker image hosts the web UI by default: a container started with no arguments serves the page on port 8000. Arguments starting with `-` still run the CLI, so existing `docker run <image> --city …` usage keeps working. The one exception is a bare `docker run <image>`, which used to print `--help` and now starts the web UI.
- A `compose.yaml` builds the image and runs the web UI. It publishes the port on localhost, mounts `posters/` and `cache/`, keeps fonts in a named volume, and restarts the container unless stopped.
- **BREAKING:** poster sizes are in millimetres everywhere. `--width`/`--height` (`-W`/`-H`) now take mm, default 300×400 mm, for all formats. The inch interpretation and the separate `--width-mm`/`--height-mm` options are removed. png/svg/pdf output is limited to 500 mm per side and plotter output has no limit. Output files are exactly the configured size, because the tight-bbox padding that used to be added is gone.

- **OpenStreetMap server choice:** a "Map data" dropdown in the UI (automatic, the known public servers, or a custom URL) with a "Check servers" button. The CLI gets `--overpass-url` / `OVERPASS_URL`, and by default checks the public servers and falls back automatically. This came from a real outage where `overpass-api.de` refused or timed out while `lz4.overpass-api.de` still worked. The old CLI hid the cause behind the progress bar.

## Capabilities

### New Capabilities
- `osm-data-source`: selects the OpenStreetMap (Overpass) server (`--overpass-url` / `OVERPASS_URL`), with automatic health check and fallback, capped retries on busy servers, and visible download errors.
- `poster-web-ui`: a local web interface for configuring all poster options, invoking the generator, streaming progress and browsing, previewing and downloading results.

### Modified Capabilities
- `plotter-svg-export`: the requirement "Physical size in millimetres" (which had an inch fallback) is replaced by "Poster size in millimetres": `--width`/`--height` in mm, default 300×400, and no other unit.

## Impact

- New `web_app.py` (the HTTP API, job runner and CLI argument builder) and `web/static/` (`index.html`, `app.js`, `style.css`). There is no Node build step.
- New dependencies: `fastapi` and `uvicorn` at runtime, plus `httpx2` for tests (Starlette's TestClient needs it; plain `httpx` is deprecated there). They are added to `pyproject.toml` and `requirements.txt`.
- `Dockerfile` copies `web_app.py` and `web/`, exposes port 8000, adds a healthcheck, and switches to a `docker-entrypoint.sh` dispatcher (web UI by default, CLI when given `--options`). A new `compose.yaml` runs the web UI. The README documents `docker compose up -d`.
- README gets a "Web interface" section. New tests go in `test/test_web_app.py`.
