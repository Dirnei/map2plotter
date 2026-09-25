# Design

## Context

- The package lives in `src/maptoposter/` and uses package-relative imports throughout (`from . import …`), except for two places that name the package: `web.CLI_COMMAND = [sys.executable, "-u", "-m", "maptoposter"]` and the tests' `maptoposter.*` imports. The project name, the two console scripts and the package-data key are in `pyproject.toml`.
- The old name also appears in:
  - the CLI prog, examples, epilog and banner ("City Map Poster Generator")
  - the web `prog`, FastAPI title, startup message and `display_command`
  - `static/index.html` (title and `<h1>`) and a comment in `app.js`
  - `docker-entrypoint.sh`, `compose.yaml` (service, image, `MAPTOPOSTER_PORT`), `pr-checks.yml`, `test/all_variations.sh`, README and CHANGELOG
- The web UI saves the form and pens in browser storage under `maptoposter-form-v3` and `maptoposter-pens-v1`.
- Three different User-Agents are sent today:
  - `overpass.USER_AGENT = "maptoposter (https://github.com/originalankur/maptoposter)"`, only for the health check
  - `Nominatim(user_agent="city_map_poster")` in `poster.get_coordinates`
  - OSMnx's default `"OSMnx Python package (https://github.com/gboeing/osmnx)"` for the map data downloads
- The Docker publish workflow tags `ghcr.io/${{ github.repository }}`, so the image name follows the new repository without any change.
- The new repository URL is not known yet.

## Goals / Non-Goals

**Goals:**
- One rename that leaves no user-facing or importable trace of `maptoposter`, apart from the attribution links and the history.
- A single place for the project's identity: name, version, repository URL, original project URL and User-Agent.

**Non-Goals:**
- Compatibility aliases (`maptoposter` commands or a shim package). Keeping them would bring back exactly the clash the rename avoids.
- Renaming internal module names (`poster.py`, `web.py`, …), or the test file names.
- Rewriting historical CHANGELOG entries or archived OpenSpec changes.

## Decisions

### 1. Identity constants in the package root
`src/map2plotter/__init__.py` defines:
```
__version__          = importlib.metadata.version("map2plotter")
PROJECT_URL          = "<repository URL>"         # the one value to fill in
ORIGINAL_PROJECT_URL = "https://github.com/originalankur/maptoposter"
USER_AGENT           = f"map2plotter/{__version__} (+{PROJECT_URL})"
```
- `overpass.USER_AGENT` is replaced by the root constant.
- `poster.get_coordinates` passes it to `Nominatim(user_agent=…)`.
- `poster` sets `ox.settings.http_user_agent` to it at import, so OSMnx downloads carry it too.
The URLs also have to appear literally in `pyproject.toml` (`[project.urls]`), the README and the web page footer (Decision 4), because those cannot import Python. The apply step asks for the repository URL once and writes it into all four places.

*Alternative:* read the URL from package metadata (`importlib.metadata`'s `Project-URL`). That removes the duplicate in `__init__.py`, but it breaks when metadata is missing, for example when running from a source tree that has not been installed. A literal constant is simpler.

### 2. Plain `git mv` rename, same layout
`src/maptoposter/` → `src/map2plotter/` in one `git mv`, so history follows the files. Only `CLI_COMMAND`, the tests' imports and `pyproject.toml` name the package; everything else is already relative. The package-data key and `[project.scripts]` change with it.

### 3. Rename the browser storage keys and restart their versions
`maptoposter-form-v3` becomes `map2plotter-form-v1`, and `maptoposter-pens-v1` becomes `map2plotter-pens-v1`. The project has no users with saved settings yet, so nothing is lost, and the old name does not linger in the code. The new prefix already makes old saved data unreachable, so the version suffix starts again at 1. The `v3: two-step form` comment in `form.js` goes with it.

*Alternative:* keep the old keys so saved settings survive. That only matters once there are users, and it would leave the one internal `maptoposter` reference in the code.

### 4. Web UI attribution in a footer
`index.html` gets a small `<footer>` after `</main>`: "Based on maptoposter by Ankur Gupta" linking to `ORIGINAL_PROJECT_URL`, plus a link to the map2plotter repository. It is static HTML, so it needs no new endpoint. The final check greps that the URLs in `index.html`, `pyproject.toml` and the README match `__init__.py`.

*Alternative:* serve the URLs from a small `/api/about` endpoint. That keeps one source, but adds an endpoint and a fetch for two fixed links.

### 5. Compose and Docker
- The compose service and image become `map2plotter`, and `MAPTOPOSTER_PORT` becomes `MAP2PLOTTER_PORT`. The volumes (`./posters`, `./cache`) and the default host port 8001 are unchanged.
- The entrypoint execs `map2plotter-web` / `map2plotter`.
- The Dockerfile copies `LICENSE` into the image. Setuptools also includes it in the wheel through `license-files`.

### 6. Lock and requirements
Only the project name changes in `uv.lock`. `uv lock` rewrites the name without upgrading anything, since the dependency ranges are unchanged. `requirements.txt` omits the project itself (`--no-emit-project`), so regenerating it changes only its header comment, if anything.

## Risks / Trade-offs

- [The placeholder URL ships] → Apply pauses to ask for the URL before touching `__init__.py`. A final grep for the placeholder string must come back empty before the change is complete.
- [Stale `maptoposter.egg-info` or `build/` directories keep an old `maptoposter` package importable in the editable environment, so the tests pass by accident] → Delete `src/maptoposter.egg-info` and `build/` and run `uv sync` again. Then check that `python -c "import maptoposter"` fails.
- [Users' scripts and compose overrides still use `maptoposter` / `MAPTOPOSTER_PORT`] → This is intended and marked BREAKING. The README and CHANGELOG list the replacements.
- [An existing Docker container named `maptoposter-maptoposter-1` keeps running under the old service name] → `docker compose up -d --build --remove-orphans` replaces it.

## Migration Plan

1. Merge. Users of a clone run `uv sync`, then `uv run map2plotter …` / `uv run map2plotter-web`.
2. Docker users run `docker compose up -d --build --remove-orphans`, and rename `MAPTOPOSTER_PORT` to `MAP2PLOTTER_PORT` if they set it.
3. Rollback: revert the commit. No data formats change.
