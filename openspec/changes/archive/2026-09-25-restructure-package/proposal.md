# Proposal

## Why

The repository has grown into nine flat modules at the root. Each of them resolves `themes/`, `fonts/` and `cache/` relative to the current directory. The tool is started with `python create_map_poster.py`, and `pyproject.toml` declares only 4 of its modules, no data and no commands. The dependency list pins every transitive package exactly, including test tools. The README example images live in `posters/`, which is also the output directory. Giving it a proper package structure now makes the code easier to navigate and the tool independent of the working directory. It is also the groundwork for a later change that makes the tool installable.

## What Changes

- **BREAKING (layout)**
  - The code moves into a `maptoposter` package (`src/maptoposter/`) with shorter module names.
  - The built-in themes, the Roboto fonts and the web static files move into the package and are found next to the code.
  - `create_map_poster.py` and `web_app.py` at the root are removed.
- **BREAKING (commands)**
  - `maptoposter` replaces `python create_map_poster.py`, with the same options.
  - `maptoposter-web` replaces `python web_app.py`.
  - `python -m maptoposter` behaves like `maptoposter`.
  - In a clone, they run with `uv run maptoposter …`.
- The web server runs the CLI as `python -m maptoposter` and shows the copyable command as `maptoposter …`.
- The map data cache stays in `./cache` (`CACHE_DIR` override unchanged), and posters stay in `./posters`. Downloaded Google Fonts move from `fonts/cache` to `cache/fonts`.
- **Dependencies:**
  - `pyproject.toml` lists only the direct runtime dependencies, with version ranges.
  - `pytest` and `flake8` move to a dev dependency group.
  - `uv.lock` and a runtime-only `requirements.txt` are regenerated from it.
- **Repository tidy-up:**
  - The README example images move to `docs/images/`, and `posters/old/` is removed.
  - `posters/` and `cache/` are git-ignored.
  - The Dockerfile, the compose file, the CI workflow, `test/all_variations.sh`, the README and the CHANGELOG are updated.

## Capabilities

### New Capabilities
- `package-layout`: covers the `maptoposter` / `maptoposter-web` / `python -m maptoposter` commands, and bundled data that works from any working directory.

### Modified Capabilities
- `poster-web-ui`:
  - "Start the web server" changes from `python web_app.py` to `maptoposter-web`.
  - "Invoke the existing CLI" now runs `python -m maptoposter` and shows `maptoposter …` as the command.

## Impact

- **Code:** every root `*.py` module moves into `src/maptoposter/` and switches to package-relative imports. The data paths now come from the package location, and `web` changes how it launches the CLI.
- **Data:** `themes/`, `fonts/*.ttf` and `web/static/` move into the package. The example posters move to `docs/images/`.
- **Tests:** imports change to `maptoposter.*`. The web tests replace the CLI script path with a command list.
- **Build and CI:**
  - `pyproject.toml`, `uv.lock` and `requirements.txt` are rewritten.
  - The Dockerfile installs the package, and its entrypoint calls the new commands.
  - `pr-checks.yml` runs pytest and flake8 on the package.
- **Users of a clone:**
  - The old commands stop working, and the README documents the new ones.
  - The cache and posters stay where they are.
  - Downloaded Google Fonts are fetched again once.
  - The Docker image, volumes and ports are unchanged, except that the separate font-cache volume is dropped.
- **Deferred to a later change:**
  - installing without a clone (`uv tool install` / pipx)
  - per-user cache and themes directories
  - `--version`
  - standalone binaries
