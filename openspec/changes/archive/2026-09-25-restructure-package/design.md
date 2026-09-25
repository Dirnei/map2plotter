# Design

## Context

- There are nine flat modules at the repository root. They import each other by bare name (`import osm_cache`), and every data path is resolved relative to the current directory:
  - `create_map_poster.py`: `THEMES_DIR = "themes"`, `POSTERS_DIR = "posters"`
  - `font_management.py`: `FONTS_DIR = "fonts"`, fonts cache in `fonts/cache`
  - `osm_cache.py`: `CACHE_DIR = $CACHE_DIR or "cache"`
- `web_app.py` resolves its paths from its own file location (`ROOT = Path(__file__).parent`). It runs the CLI as `sys.executable -u ROOT/create_map_poster.py` with `cwd=ROOT`, and its web work directory is `ROOT/cache/web`.
- The tests import the flat modules and monkeypatch module globals:
  - `cmp.THEMES_DIR`, `cmp.POSTERS_DIR`, `osm_cache.CACHE_DIR`, `cmp.fetch_graph`
  - `web_app.POSTERS_DIR`, `THEMES_DIR`, `WORK_DIR`, `CLI_SCRIPT`
- In Docker, the working directory is `/app`, and the volumes are mounted at `/app/posters`, `/app/cache` and `/app/fonts/cache`.
- The README example images are tracked inside `posters/`, which is also the default output directory.

## Goals / Non-Goals

**Goals:**
- A navigable package with consistent module names.
- Built-in data that does not depend on the working directory.
- The tests keep working with only import and fixture changes.

**Non-Goals:**
- Installing without a clone, per-user data directories, `--version`, binaries. These belong to a later change, which this layout prepares for.
- Splitting `create_map_poster.py` into a renderer and a CLI. Its module globals (`THEME`, `CACHE_ONLY`, `OVERPASS_CHOICE`) are what the tests patch, and splitting them is a separate refactor.
- Custom themes outside the package. For now, they are added to `src/maptoposter/data/themes/`.

## Decisions

### 1. src layout with shorter module names
```
src/maptoposter/
  __init__.py
  __main__.py        python -m maptoposter -> poster.main()
  paths.py           package data and working-directory locations
  poster.py          (was create_map_poster.py) render + CLI, main()
  web.py             (was web_app.py) FastAPI app, main()
  fonts.py           (was font_management.py)
  osm_cache.py       (unchanged name)
  overpass.py        (was overpass_servers.py)
  plotter.py         (was plotter_svg.py)
  colors.py / edits.py / size.py   (were poster_colors / poster_edits / poster_size)
  data/themes/*.json
  data/fonts/Roboto-*.ttf
  static/            (was web/static)
```
Inside a `maptoposter` namespace, the `poster_` / `_svg` / `_servers` prefixes are redundant. Imports become package-relative (`from . import osm_cache`).

- The data sits under `data/`, so it cannot clash with the `fonts` module.
- With the src layout, only the installed package is importable (`uv sync` installs it in editable mode). That means the tests cannot pass by accident on stray root files.

*Alternative:* keep the old module names in the package. This is a smaller diff, but the names would stay long and inconsistent for good. The tests are updated either way.

### 2. One `paths` module
```
PACKAGE_DIR = Path(__file__).parent
THEMES_DIR  = PACKAGE_DIR / "data" / "themes"
FONTS_DIR   = PACKAGE_DIR / "data" / "fonts"
STATIC_DIR  = PACKAGE_DIR / "static"
CACHE_DIR   = Path(os.environ.get("CACHE_DIR", "cache"))   # unchanged behaviour
POSTERS_DIR = Path("posters")                              # unchanged behaviour
```
The other modules keep their own globals, but take their values from `paths`:
- `poster.THEMES_DIR` / `POSTERS_DIR`
- `osm_cache.CACHE_DIR`
- `fonts.FONTS_DIR`, and `fonts.FONTS_CACHE_DIR = CACHE_DIR / "fonts"`
- `web.THEMES_DIR` / `POSTERS_DIR` / `STATIC_DIR`, and `web.WORK_DIR = CACHE_DIR / "web"`

That way the existing monkeypatch-based tests keep working unchanged.

- `Path(__file__)` rather than `importlib.resources`: every consumer (`glob`, `open`, matplotlib font paths, `StaticFiles`) needs a real filesystem path, and the package is always installed as files.
- The Google Fonts cache moves to `CACHE_DIR/fonts` because the package directory must not be written to.
- The web server's posters and work paths used to be anchored at the repository root. They are now relative to the working directory, like the CLI's. In Docker (`/app`) and in a clone run from the root, the result is the same folder.

### 3. The web server launches `python -m maptoposter`
- `web.CLI_COMMAND = [sys.executable, "-u", "-m", "maptoposter"]`.
- The `cwd=ROOT` argument is dropped, so the process inherits the server's working directory. Its environment gets `CACHE_DIR` set to the server's resolved absolute cache path, so both always agree.
- `display_command()` shows `maptoposter …`.
- The tests set `CLI_COMMAND = [sys.executable, "-u", str(fake_script)]` instead of `CLI_SCRIPT`.

*Alternative:* call `poster.main()` in-process. That loses cancellation (terminating a process) and isolates matplotlib state less well, so it was rejected.

### 4. Dependencies: ranges in pyproject, exact pins in the lock
- `[project].dependencies` lists only what the code imports directly, each with a range up to the next major version (for example `osmnx>=2.0,<3`):
  - numpy, matplotlib, osmnx, geopandas, shapely, scipy, networkx, geopy
  - lat-lon-parser, tqdm, requests, Hershey-Fonts, fastapi, uvicorn, pydantic
- `pytest`, `flake8` and `httpx` (for the FastAPI `TestClient`) go in `[dependency-groups].dev`.
- `uv.lock` is regenerated.
- `requirements.txt` becomes `uv export --no-dev --no-emit-project --no-hashes`, so pip and Docker installs keep the exact tested versions.

The build backend stays setuptools, with `[tool.setuptools.package-data]` for `data/**` and `static/*`, and `[project.scripts]`:
```
maptoposter = "maptoposter.poster:main"
maptoposter-web = "maptoposter.web:main"
```

### 5. Docker
- Install `requirements.txt`, then `pip install --no-deps .`.
- The working directory stays `/app`, so `cache/` and `posters/` resolve to the same volumes as before. The font cache is now under `/app/cache/fonts`, so the `font-cache` volume is removed from compose.
- The entrypoint calls `maptoposter-web --host 0.0.0.0` and `maptoposter "$@"`.

### 6. Repository layout outside the package
- `posters/*.png` moves to `docs/images/` (`posters/old/` is dropped: it is not referenced by the README), and the README `<img src>` paths are updated.
- `posters/` and `cache/` are added to `.gitignore`. The existing ignore of `uv.lock` is removed, since the file is tracked anyway.
- `test/` keeps its name.

## Risks / Trade-offs

- [Package data is left out by a wrong glob, which the editable install hides] → The tests read the themes and fonts through the package paths. The Docker build (a non-editable install) is checked with `--list-themes` and a render.
- [Loose version ranges let a future major release break a fresh resolve] → The upper bounds sit at the next major version, and the lock plus requirements.txt give reproducible installs.
- [`uv` is not installed on the dev machine] → Install it into the venv (`pip install uv`) to regenerate the lock and the export.
- [Starting the web server from another directory moves its posters folder] → The behaviour is now the same as the CLI's, and it is documented in the README.

## Migration Plan

1. Merge. Users of a clone run `uv sync`, then `uv run maptoposter …` / `uv run maptoposter-web`.
2. The Docker image, volumes and ports are unchanged, and `docker compose up -d --build` is enough.
3. Rollback: revert the commit. There are no data format changes.
