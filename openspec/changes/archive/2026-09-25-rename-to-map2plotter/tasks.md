# Tasks

## 1. Repository URL

- [x] 1.1 Ask the user for the map2plotter repository URL and record it here: `https://github.com/Dirnei/map2plotter`. Implementation does not continue past this task without it.

## 2. Package and commands

- [x] 2.1 `git mv src/maptoposter src/map2plotter`. Delete `src/maptoposter.egg-info/` and `build/`. In `pyproject.toml`, set `name = "map2plotter"`, set `[project.scripts]` to `map2plotter` / `map2plotter-web`, and change the package-data key. Change `web.CLI_COMMAND` to `-m map2plotter` and update every test import to `map2plotter.*`. Run `uv lock` and `uv sync`, and regenerate `requirements.txt`. Verify that `uv run pytest` passes 178 tests, that `uv run python -c "import maptoposter"` fails, and that `.venv/Scripts` has no `maptoposter*` command.
- [x] 2.2 Update the user-facing name:
  - CLI `prog`, examples, epilog and banner
  - web `prog`, FastAPI title, startup message and `display_command`
  - `index.html` title and `<h1>`, and the `app.js` header comment
  - `__main__.py` docstring

  Rename the browser storage keys to `map2plotter-form-v1` (`form.js`, dropping the `v3` comment) and `map2plotter-pens-v1` (`app.js`). Update the command-display test to expect `map2plotter`. Verify that `map2plotter --help` and `python -m map2plotter --help` print identical help naming `map2plotter`, and that the web tests pass.

## 3. Attribution and identity

- [x] 3.1 Add `__version__`, `PROJECT_URL`, `ORIGINAL_PROJECT_URL` and `USER_AGENT` to `src/map2plotter/__init__.py`. Use `USER_AGENT` for the Overpass health check, for `Nominatim(user_agent=…)` and for `ox.settings.http_user_agent`. Add a test that `USER_AGENT` matches `map2plotter/<version> (+<url>)` and that the health check sends it. Verify with pytest, and with `grep -rn "city_map_poster\|originalankur" src` finding only `ORIGINAL_PROJECT_URL` and the footer link.
- [x] 3.2 `LICENSE`: keep the existing text and add `Copyright (c) 2026 Christian Dirnhofer`. `pyproject.toml`:
  - keep Ankur Gupta under `authors`
  - add `maintainers = [{name = "Christian Dirnhofer"}]`
  - add `license-files = ["LICENSE"]`
  - add `[project.urls]` with Homepage, Source, Issues and "Original project"

  Verify that `uv build --wheel` contains `LICENSE` and that its METADATA lists the author, the maintainer and both URLs.
- [x] 3.3 Add a footer to `index.html` with "Based on maptoposter by Ankur Gupta", linking to the original project, and a link to the map2plotter repository, styled in `style.css`. Verify that the web test for `/` finds both links in the returned HTML, and check it in the browser at desktop and phone width.

## 4. Deployment, CI and docs

- [x] 4.1 Update the deployment and CI files:
  - `docker-entrypoint.sh`: exec `map2plotter-web` / `map2plotter`
  - `compose.yaml`: service and image `map2plotter`, and `MAP2PLOTTER_PORT`
  - Dockerfile: copy `LICENSE`
  - `pr-checks.yml`: `map2plotter --help` / `--list-themes`
  - `test/all_variations.sh`: `uv run map2plotter`

  Verify with `docker compose up -d --build --remove-orphans`, a healthy `map2plotter` container, a web load and preview on port 8001, `docker compose run --rm map2plotter --list-themes`, and that `/app/LICENSE` exists in the image.
- [x] 4.2 README:
  - title "map2plotter", with the attribution note linking to the original project before Installation
  - every command, the project structure and the custom-themes path
  - the GHCR image name (`ghcr.io/<owner>/map2plotter`)
  - `MAP2PLOTTER_PORT`

  CHANGELOG: add a BREAKING rename entry listing the old → new commands and variables, and leave the historical entries untouched. Verify that `grep -rn -i "maptoposter" README.md` finds only the attribution note, and that every README link to the original project uses `ORIGINAL_PROJECT_URL`.

## 5. Final checks

- [x] 5.1 `grep -rn -i "maptoposter\|create_map_poster\|<repository URL>" --exclude-dir=.git --exclude-dir=.venv --exclude-dir=cache --exclude-dir=archive .` finds only:
  - the attribution links
  - the historical CHANGELOG entries
  - `ORIGINAL_PROJECT_URL`

  `flake8 src test` is clean and the full `pytest` suite passes.
