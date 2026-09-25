# Tasks

## 1. Package layout

- [x] 1.1 Move the modules with `git mv` into `src/maptoposter/` under their new names (`poster`, `web`, `fonts`, `osm_cache`, `overpass`, `plotter`, `colors`, `edits`, `size`). Move `themes/` → `data/themes/`, `fonts/*.ttf` → `data/fonts/`, and `web/static/` → `static/`. Add `__init__.py` and `__main__.py`. Switch all imports to package-relative ones, including the lazy imports in `web.layout`. Verify with `python -c "import maptoposter.poster, maptoposter.web"` after an editable install.
- [x] 1.2 Add `paths.py` (package data dirs, `CACHE_DIR` from the environment or `cache`, `POSTERS_DIR`). Point `poster`, `osm_cache`, `fonts` (Google Fonts cache in `CACHE_DIR/fonts`) and `web` (`WORK_DIR = CACHE_DIR/web`) at it. Verify that `maptoposter --list-themes` run from an empty temporary directory lists all 17 built-in themes.

## 2. Commands and web launcher

- [x] 2.1 Add `[project.scripts]` for `maptoposter` / `maptoposter-web`, and add `__main__.py` calling `poster.main()`. Replace `python create_map_poster.py` with `maptoposter` in `print_examples` and the argparse epilog. Verify that `uv run maptoposter --help` and `python -m maptoposter --help` print the same help.
- [x] 2.2 In `web`, replace `CLI_SCRIPT` with `CLI_COMMAND = [sys.executable, "-u", "-m", "maptoposter"]`. Drop `cwd=ROOT`, pass the resolved absolute `CACHE_DIR` in the child's environment, and have `display_command` show `maptoposter …`. Update the `test_web_app.py` fixture to set `CLI_COMMAND`. Verify that the web tests pass and that the command-display test expects `maptoposter`.

## 3. Project metadata and dependencies

- [x] 3.1 Rewrite `pyproject.toml`:
  - src-layout package discovery and package data (`data/**/*`, `static/*`)
  - direct runtime dependencies with major-version ranges
  - `[dependency-groups].dev` with pytest, flake8 and httpx
  - pytest `testpaths`, without `pythonpath = ["."]`

  Install `uv` into the venv if it is missing, then run `uv lock` and `uv export --no-dev --no-emit-project --no-hashes -o requirements.txt`. Verify with `uv sync --locked`, followed by `uv run pytest`.
- [x] 3.2 Update the imports of every test module (`maptoposter.poster as cmp`, `maptoposter.osm_cache`, and so on). Verify that the full `pytest` suite passes with the same number of tests as before, and that `flake8 src test` is clean.

## 4. Repository and deployment files

- [x] 4.1 Move the README example images from `posters/` to `docs/images/` and delete `posters/old/`. Update the `<img>` paths, and add `posters/` and `cache/` to `.gitignore` (dropping the `uv.lock` ignore). Verify that every image path referenced in the README exists.
- [x] 4.2 Dockerfile:
  - install `requirements.txt`, then `pip install --no-deps .`
  - the entrypoint runs `maptoposter-web` / `maptoposter`

  Update `.dockerignore`, and drop the `font-cache` volume from `compose.yaml`. Verify with `docker compose up -d --build`, a healthy container, a web load and preview of a small area on port 8001, and `docker compose run --rm maptoposter --list-themes`.
- [x] 4.3 Update `.github/workflows/pr-checks.yml`:
  - `pip install -r requirements.txt && pip install --no-deps .` plus the dev tools
  - `maptoposter --help` and `--list-themes`
  - `flake8 src test`
  - `pytest`

  Also update `test/all_variations.sh` to `uv run maptoposter`. Verify by running the same commands locally.

## 5. Documentation

- [x] 5.1 README:
  - installation from a clone (`uv sync`, then `uv run maptoposter` / `uv run maptoposter-web`; pip with `pip install -r requirements.txt && pip install -e .`)
  - replace every `create_map_poster.py` / `web_app.py` command
  - custom themes now go in `src/maptoposter/data/themes/`

  Add a CHANGELOG entry. Verify that `grep -rn "create_map_poster\|web_app" README.md Dockerfile docker-entrypoint.sh compose.yaml .github test src` finds nothing.
