# Tasks

## 1. Setup

- [x] 1.1 Add pinned `fastapi` and `uvicorn` to `pyproject.toml` and `requirements.txt`, and `httpx2` to `requirements.txt`. Verify that `pip install -r requirements.txt` succeeds and that `python -c "import fastapi, uvicorn, httpx2"` works
- [x] 1.2 Create `web_app.py` with the FastAPI app, configurable `POSTERS_DIR`/`THEMES_DIR`/CLI command settings and an argparse `__main__` (`--host` default `127.0.0.1`, `--port` default `8000`) that prints the URL. Also create a `web/static/index.html` placeholder served at `/`. Verify that `python web_app.py` serves the page at `http://127.0.0.1:8000/`
- [x] 1.3 Create `test/test_web_app.py` with TestClient fixtures that point the settings at `tmp_path`, plus a fake CLI script factory (success, failure, slow). Verify that `pytest test/test_web_app.py` runs

## 2. API: config, validation, command

- [x] 2.1 Implement `GET /api/themes`, which reads `themes/*.json` into `{id, name, description, colors}`. Verify with a test using two temporary theme files
- [x] 2.2 Implement the Pydantic `PosterConfig` with CLI defaults and validation (required city/country, lat/lon set together and parseable, > 0 values, ≤ 500 mm for non-plotter formats, theme exists, format enum, hatch ≥ pen for plotter) (D2). Verify with tests that a missing city and a hatch below the pen each return 422 naming the field
- [x] 2.3 Implement `build_args(config)` and the display command (D3): empty fields omitted, `all_themes` as a flag, plotter fields only for the plotter format. Verify with tests for the Paris/noir/svg example, the plotter example, and that `Paris; rm -rf /` stays a single argument value

## 3. API: job runner

- [x] 3.1 Implement the `Job` model and the single-slot runner with `asyncio.create_subprocess_exec` (unbuffered, UTF-8 env, stderr merged), line splitting on `\n`/`\r`, and a status set from the return code (D4). Verify with tests that the fake success script ends `succeeded` and the failing one ends `failed` with its output kept
- [x] 3.2 Implement `POST /api/jobs` (validate, snapshot posters, start, return `{id, command}`, 409 when busy) and `GET /api/jobs/current`. Verify with a test that a second submit during the slow fake job returns 409
- [x] 3.3 Implement the SSE stream `GET /api/jobs/{id}/events`: replay existing lines, send live lines, send pings every 15 s, and finish with a final status event that includes the new files. Verify with a test that reads the stream to completion and checks the lines, the final status and the detected file list
- [x] 3.4 Implement `POST /api/jobs/{id}/cancel` (terminate, then kill after 5 s, status `cancelled`), and terminate the running job on app shutdown. Verify with a test that cancelling the slow fake job yields `cancelled` and that a new job can start afterwards

## 4. API: posters

- [x] 4.1 Implement `GET /api/posters`: png/svg/pdf in `posters/`, not recursive, newest first, with name, size and mtime. Verify with a test that three files with staggered mtimes come back newest first and that `posters/old/` is excluded
- [x] 4.2 Implement `GET /api/posters/{name}`, served inline, with `?download=1` producing an attachment. It applies the traversal and extension guard (D5). Verify with tests that a valid file returns 200 with the correct content type, the download sets `Content-Disposition: attachment`, and `../create_map_poster.py`, an encoded traversal and a `.txt` file all return 404

## 5. Frontend (web/static)

- [x] 5.1 Build the `index.html` form sections with every CLI option and CLI defaults, and `style.css` with a responsive layout. Verify manually that all fields are present and the defaults match the CLI `--help`
- [x] 5.2 In `app.js`, load themes into a swatch grid, toggle the plotter fieldset on the format change, and persist form values in `localStorage`. Verify manually that the plotter fields appear and disappear, and that the values survive a reload
- [x] 5.3 In `app.js`, submit to `/api/jobs` and show 422 errors inline and 409 as a banner, display the command with a copy button, stream the log over `EventSource` with tqdm line collapsing, and wire up the Cancel button. Verify manually with a real run (e.g. Venice, `-d 3000`) that the log streams and cancel works
- [x] 5.4 In `app.js`, render the result cards (img preview for png/svg, a link for pdf, download buttons) and the history list, refreshing after each job and reattaching to the current job on load. Verify manually that a finished PNG and a plotter SVG both preview and download, and that the history updates

## 6. Packaging and docs

- [x] 6.1 Update the `Dockerfile` (copy `web_app.py` and `web/`, `EXPOSE 8000`). Verify that `docker build` succeeds and that the web UI is served from the container
- [x] 6.2 Add a README "Web interface" section (local start, Docker command, trusted-network warning). Verify that the commands in the README match the implemented flags
- [x] 6.3 Run `flake8` and the full `pytest` suite. Verify that both pass

## 7. Container hosting and compose

- [x] 7.1 Add `docker-entrypoint.sh` (no args → web UI on `0.0.0.0:$PORT`; `-…` args → CLI; else exec). Wire it into the Dockerfile with CRLF stripping, `ENV PORT`, and a Python `HEALTHCHECK`. Verify that the container becomes `healthy`, serves the page, and still runs `--list-themes`
- [x] 7.2 Add `compose.yaml` (build, localhost port with `MAPTOPOSTER_PORT`, `./posters` + `./cache` bind mounts, `font-cache` volume, `restart: unless-stopped`). Verify that `docker compose config` is valid, that `docker compose up -d` serves the UI, that a job run through the API writes its poster to the host `posters/`, and that `docker compose run --rm maptoposter --list-themes` works
- [x] 7.3 Update the README Docker sections (compose usage, container default, CLI via options). Verify that the commands match the entrypoint behaviour

## 8. Millimetres only

- [x] 8.1 CLI: `--width`/`--height` (`-W`/`-H`) in mm (default 300×400) for all formats, with the inch options and `--width-mm`/`--height-mm` removed, a 500 mm limit for non-plotter output only, and exact output size (no tight-bbox padding). Verify that `--help` shows mm, that `--width-mm` is rejected, that a Venice PNG is 3543×4724 px (300×400 mm at 300 DPI), that the PDF MediaBox is 300×400 mm and the plotter SVG is `300mm`×`400mm`
- [x] 8.2 Web: form, API and argument builder use `width`/`height` in mm, with the plotter-only mm fields removed. Verify with the updated `test_web_app.py` (validation, argument list, plotter size not limited)
- [x] 8.3 Docs, variation script and specs: README tables (options, plotter, resolution guide in mm), `test/all_variations.sh`, and the `plotter-svg-export` size requirement replaced (REMOVED "Physical size in millimetres", ADDED "Poster size in millimetres"). Verify that `openspec validate --strict` passes and that no user-facing inch references remain

## 9. OpenStreetMap server choice

- [x] 9.1 Add `overpass_servers.py`: server list, `normalize`, a parallel health check, `candidates` (healthy servers first), `run` with fallback on server errors but not on "no data", and `limit_retries` (max 3 attempts on 429/504). Verify with `test/test_overpass_servers.py`
- [x] 9.2 CLI: `--overpass-url` (default `$OVERPASS_URL` or `auto`) with validation; `overpass_download` shared by the graph and feature downloads; errors via `tqdm.write`; a street network failure raises with each server's cause. Verify with a real uncached run in `auto` mode that fell back past a failing `overpass-api.de` to `lz4.overpass-api.de`, and with a run using an explicit server
- [x] 9.3 Web: `overpass_url` config field and CLI argument, `GET /api/overpass/servers`, `POST /api/overpass/check`, and the "Map data" dropdown (auto, known servers, custom URL) with "Check servers" results and the choice saved in the browser. Verify with tests plus a browser check of the dropdown, custom field visibility, saved choice and live check results
- [x] 9.4 Packaging and docs: Dockerfile copies `overpass_servers.py`, pyproject `py-modules`, `OVERPASS_URL` in `compose.yaml`, and a README section "OpenStreetMap Servers". Verify that `docker compose config` is valid and that the image builds
