# Design

## Context

`create_map_poster.py` is a CLI script. Importing it has side effects: it creates `cache/`, calls `load_fonts()`, and keeps the theme in a module-level global `THEME`. It writes output to `posters/<city>_<theme>_<timestamp>.<ext>` and reports progress only through `print`/`tqdm` on stdout/stderr. Validation lives in its `__main__` block. Themes are JSON files in `themes/`. Before this change, the Docker image ran `ENTRYPOINT ["python", "create_map_poster.py"]`. For motivation see proposal.md. For behaviour see `specs/poster-web-ui/spec.md`.

## Goals / Non-Goals

**Goals:**
- Wrap the CLI instead of re-implementing it. The web layer is a thin form, a process runner and a file browser.
- Add no frontend build tooling. The UI is static HTML/CSS/JS served by the Python app.
- Keep the web layer testable without network access or real poster generation.

**Non-Goals:**
- Multi-user use, authentication, job queues or persistence of job state across server restarts.
- An interactive map picker, or live previews of the map before generating.
- Changing the CLI's behaviour or output locations.

## Decisions

### D1: FastAPI + uvicorn, single module `web_app.py`
FastAPI gives us request validation through Pydantic models (field-level errors come back as 422 for free), async endpoints and `StreamingResponse` for Server-Sent Events. uvicorn serves it, and `web_app.py` runs it from `__main__` using argparse `--host`/`--port`, defaulting to `127.0.0.1:8000`. Static files come from `web/static/` through `StaticFiles`, and `/` returns `index.html`.
*Alternative:* Flask. Flask is simpler, but streaming and validation would need more hand-written code, and the sync workers make cancel and stream handling clumsier.

### D2: Do not import `create_map_poster`
Importing it would trigger its side effects and bring matplotlib and osmnx into the web process. The web app instead:
- reads `themes/*.json` itself to build the theme list
- mirrors the CLI's cheap validations (required fields, > 0, max 500 mm for non-plotter formats, hatch ≥ pen, theme exists) in its Pydantic model
- uses `lat_lon_parser.parse` to validate coordinates
- relies on the CLI as the final authority at runtime

### D3: Argument builder
`build_args(config) -> list[str]` maps each field to its long CLI flag and skips any field that is `None` or empty. Booleans (`all_themes`) become bare flags. Plotter fields are sent only when `format == "plotter"`. The process runs as `[sys.executable, "-u", CLI_PATH, *args]` with `cwd` set to the project root. `-u` makes the output unbuffered, which streaming needs. The display string comes from `shlex.join(["python", "create_map_poster.py", *args])`. The command is always an argument list; there is never `shell=True` (spec: no shell interpretation).

### D4: Job runner with asyncio subprocess + Server-Sent Events
A single in-memory `Job` holds `id`, `command`, `status` (`running|succeeded|failed|cancelled`), `lines: list[str]`, `files: list[str]`, `started_at` and `proc`. A single slot enforces one job at a time and returns 409 when busy. The check-and-set has no `await` in between, so it is atomic on the event loop. A module-level `asyncio.Lock` would bind to one event loop and break when the app runs under more than one (e.g. across test clients).
- `POST /api/jobs` validates the config, snapshots the `posters/` listing, starts `asyncio.create_subprocess_exec(..., stdout=PIPE, stderr=STDOUT, env={**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUNBUFFERED": "1"})`, launches a reader task and returns `{id, command}`. Forcing UTF-8 avoids the Windows cp1252 crash we saw with piped output, where the CLI prints ✓ and ⚠ characters.
- The reader task reads chunks and splits them on both `\n` and `\r`, because tqdm redraws its bar with `\r`. It appends the lines, and on exit sets the status from the return code. It computes `files` as the new poster files: the listing after the job, minus the listing before, filtered by extension.
- `GET /api/jobs/{id}/events` is an SSE stream. It first replays the existing lines, then sends new lines as they arrive (the stream waits on an `asyncio.Condition`), and finishes with a final `status` event that carries `files`. Replaying makes a page reload mid-job work.
- `POST /api/jobs/{id}/cancel` calls `proc.terminate()`, then `kill()` after 5 s, and sets the status to `cancelled`.
- `GET /api/jobs/current` returns the running or last job, so the page can reattach after a reload.

The new files are detected by diffing the `posters/` directory, which handles `--all-themes` (many files) and every format. We don't parse the CLI output text for file names. On Windows, asyncio uses the Proactor event loop by default, which supports subprocesses.
*Alternative:* WebSockets. They are bidirectional, which we don't need, and the client code is more complex. SSE works with the browser's native `EventSource` and reconnects automatically.

### D5: File endpoints
- `GET /api/posters` lists `posters/*.{png,svg,pdf}` (not recursive, so `posters/old/` is ignored) sorted by modification time, newest first, with `name`, `size` and `mtime`.
- `GET /api/posters/{name}` serves the file inline, and adds `?download=1` for `Content-Disposition: attachment`. The name must equal its own `Path(name).name`, the resolved path must be inside `POSTERS_DIR.resolve()`, and the extension must be in the allow-list. Anything else returns 404.
- `GET /api/themes` returns `[{id, name, description, colors: {key: hex}}]`.

`POSTERS_DIR`, `THEMES_DIR` and the CLI command are module-level settings, so the tests can point them at temporary directories and a fake CLI script.

### D6: Frontend
There is one `index.html` with a plain `<form>`, plus `app.js` (vanilla ES modules, no framework) and `style.css`.
- **Sections:** Location, Style (a theme grid with swatches, and an "all themes" checkbox), Size & Format (the plotter fieldset is toggled by the format select), Labels & Fonts, then Generate and Cancel buttons.
- **Log view:** a `<pre>` that auto-scrolls. Consecutive tqdm `\r` updates replace the last line when they share a prefix, so the log doesn't fill up with progress bars.
- **Results and history:** cards with `<img>` for png/svg, a link for pdf, and a download button.
- **Errors:** 422 errors are shown next to their fields, and a 409 shows a banner.
- **Remembered values:** the last used form values are stored in `localStorage` for convenience.

### D7: Docker and packaging
The Dockerfile copies `web_app.py` and `web/`, adds `EXPOSE 8000` and `ENV PORT=8000`, and replaces the fixed CLI entrypoint with `docker-entrypoint.sh`:
- **No arguments:** `exec python web_app.py --host 0.0.0.0 --port $PORT`, so the container hosts the UI.
- **First argument starts with `-`:** `exec python create_map_poster.py "$@"`. Existing `docker run <image> --city … --country …` and `--list-themes` usage keeps working.
- **Anything else:** runs that command (e.g. `sh`).

`exec` makes the server PID 1, so `docker stop` sends SIGTERM straight to uvicorn, and its shutdown hook terminates any running job. The Dockerfile strips CRLF from the script, so checkouts on Windows still build. A `HEALTHCHECK` fetches `/api/themes` using Python, because the slim image has no curl.
*Alternative:* keep the CLI entrypoint and document `--entrypoint python … web_app.py`. Rejected because the user wants the container to host the UI, and that command is clumsy in compose.

`compose.yaml` defines one `maptoposter` service. It builds from the repo, is tagged `maptoposter:latest`, and publishes `127.0.0.1:${MAPTOPOSTER_PORT:-8000}:8000`, on loopback only because there is no auth. It bind-mounts `./posters` and `./cache` so results and OSM data persist on the host, puts downloaded Google fonts in a named `font-cache` volume (because `fonts/cache` isn't git-ignored), and uses `restart: unless-stopped`. `docker compose run --rm maptoposter --city …` runs the CLI with the same volumes.
The dependencies `fastapi`, `uvicorn` and `httpx2` (tests) are pinned in `requirements.txt` and `pyproject.toml`.

### D8: Tests
`test/test_web_app.py` uses FastAPI's `TestClient`. A fake CLI script (a tiny Python file written into `tmp_path`) prints a few lines and writes a dummy PNG into the temp posters directory, or exits 1, or sleeps (for cancellation). This covers:
- validation errors
- the argument list, and that no shell is used
- streaming lines
- success with detected files, and failure status
- the 409 for concurrent jobs
- cancel
- history sorting
- path-traversal rejection
- theme listing

### D9: Millimetres only
Sizes are millimetres everywhere. The CLI's `--width`/`--height` (`-W`/`-H`) take mm (default 300×400), and so do the web form fields `width`/`height`. The CLI converts to inches only internally, for matplotlib's `figsize`. The layout reference size (304.8 mm, the old 12-inch default) stays as an internal constant, so text and road widths scale exactly as before. `savefig` no longer uses `bbox_inches="tight"` with padding, so a png/pdf/svg is exactly the configured size (the axes already fill the whole figure). The 20-inch limit becomes 500 mm for matplotlib output. Plotter output has no limit, because large-format plotters (A0 and up) are common.
*Alternative:* keep inch flags as hidden legacy aliases. Rejected on request: the user wants no inch units anywhere.

### D10: OpenStreetMap server selection and fallback
A new module `overpass_servers.py` is shared by the CLI and the web app. It has no side effects on import and loads OSMnx lazily. It holds:
- **The server list:** in fallback order, with `overpass-api.de` first, then `lz4`/`z.overpass-api.de`, `maps.mail.ru`, `overpass.private.coffee` and `overpass.kumi.systems`. Servers seen failing in testing are left out: `overpass.openstreetmap.fr` (403 "white-listed usages" for real downloads), `overpass.osm.jp` (TLS error) and `overpass.osm.ch` (Swiss data only).
- **`normalize()`:** accepts `auto`, `/api` and `/api/interpreter` URLs.
- **The health check:** a count query in a ~100 m box, 15 s timeout, run in parallel with a thread pool.
- **`candidates()`:** in `auto` mode, returns the healthy servers first, then the rest.
- **`run()`:** sets `osmnx.settings.overpass_url`, calls the download, and on a server error (`requests` exceptions, OSMnx `ResponseStatusCodeError`, or the busy cap below) logs the failure and tries the next server. `InsufficientResponseError` (no data in the area) is re-raised, because it isn't a server fault.
- **`limit_retries()`:** OSMnx retries 429/504 answers recursively and without limit, pausing 55 s each time, so an overloaded server would block the fallback forever. The recursion goes through the module attribute `osmnx._overpass._overpass_request`, so wrapping that attribute counts the attempts of one request and raises `OverpassBusyError` after 3. This touches a private OSMnx function, a trade-off accepted for an unbounded hang. OSMnx is pinned (2.0.7), and a test covers the hook.
- **OSMnx slot check per server:** `run()` turns OSMnx's slot check (`overpass_rate_limit`) on only for `*.overpass-api.de`. Servers without a rate limit (e.g. `maps.mail.ru`, "Rate limit: 0") have no slot line on `/status`, and OSMnx then re-checks every 5 s forever. That was observed as a run hanging for more than 8 minutes, which dropped to 30 s after the fix.

In the CLI, `overpass_download()` resolves the candidate order once per run and moves the server that answered to the front. It logs through `tqdm.write`, so the progress bar no longer hides messages. `fetch_graph` raises a `RuntimeError` naming each server's failure. `fetch_features` warns and continues without that layer. `--overpass-url` defaults to `$OVERPASS_URL` or `auto`.

The web app always passes the choice explicitly (`--overpass-url auto|<url>`), so the displayed command is complete. `GET /api/overpass/servers` returns the list and the default (`$OVERPASS_URL`, normalised, or auto) used to preselect the dropdown. `POST /api/overpass/check` runs the health check in a worker thread (`asyncio.to_thread`) for the known servers plus an optional custom URL. `compose.yaml` passes `OVERPASS_URL` (default `auto`).

## Risks / Trade-offs

- [Two sources of validation (web model and CLI) can drift] → The web model only duplicates cheap checks. The CLI still validates and its error output is shown, so drift degrades to a slower error message and never to wrong output.
- [Binding to `0.0.0.0` in Docker exposes an unauthenticated service that can start CPU- and network-heavy jobs] → The default bind is loopback. The README warns to use `0.0.0.0` only on trusted networks or behind a proxy.
- [Long-running jobs (18 km radius) keep an SSE connection open for minutes] → SSE sends a comment ping every 15 s so proxies don't close it. `EventSource` reconnects automatically, and the replay-on-connect covers any gap.
- [If the server process exits while a job is running, the CLI subprocess may be orphaned] → On FastAPI shutdown, terminate any running job.
- [Diffing `posters/` could pick up files written by something else during the job] → This is acceptable for a single-user local tool.

## Migration Plan

The change is additive, apart from one thing: a bare `docker run <image>` now starts the web UI instead of printing the CLI help. All CLI invocations with options behave as before. Rolling back means removing `web_app.py`, `web/` and the new dependencies.
