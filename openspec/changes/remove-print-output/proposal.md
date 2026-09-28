# Proposal

## Why

map2plotter's name and purpose is pen-plotter output, but half of the code base still serves the inherited print posters:
- matplotlib rendering to PNG, SVG and PDF
- raster dpi and PNG pixel limits
- Google Fonts and the bundled Roboto fonts
- a second workflow in the web interface

Every copy of maptoposter already does print posters. The plotter output, pens and editor are what this project adds. Removing print makes the tool, the web interface and the documentation about one thing. It also drops matplotlib and its dependencies, and it removes the largest source of branching (`if format == "plotter"`) from the CLI and the server. Doing it now, before the first release (1.0.0), means no released version ever promised print output.

## What Changes

- **BREAKING (CLI)**
  - The plotter SVG is the only output. The `--format`/`-f` option is removed, and so are `--dpi` and `--font-family`.
  - `--output` must end in `.svg`.
  - `--color` no longer accepts `bg` or `gradient_color`.
  - Non-Latin display names are drawn only as far as the single-line pen font covers them. The existing behaviour stays: a warning, with unsupported characters skipped.
- **BREAKING (web interface)**
  - The "What are you making?" choice and the print options are removed: theme grid, file format, PNG resolution, font family and the layer-toggle panel.
  - Every load and preview renders the plotter SVG. Colours are chosen in the pens list, whose "Start from theme" preset is the theme choice.
  - The poster history and downloads cover SVG files only. PNG and PDF files already in `posters/` are no longer listed.
- **Removed code and data:**
  - the matplotlib rendering path in `poster.py` (gradient fades, edge colours and widths, raster erase patches)
  - `fonts.py` (Google Fonts) and `size.py` (PNG limits)
  - the Roboto fonts in `data/fonts/`, and the `cache/fonts/` download cache
  - the `bg` and `gradient_color` keys in the built-in themes
  - the `matplotlib` dependency
- **Refactor:** the poster text layout (city title formatting, coordinates, base font sizes) moves next to the plotter renderer. The CLI and the web editor's `/api/layout` then share one implementation, and the web server no longer imports the whole CLI module for it.
- **Docs:**
  - The README is rewritten around pen plotting: install, CLI, web interface, pens and layers, fills, the vpype/Inkscape workflow, Docker and releases.
  - The print gallery, the resolution guide and the font/i18n sections are removed.
  - New example images are rendered from locally cached map data as small PNG previews of plotter SVGs.
  - The CHANGELOG notes the removal.
- The commit is `feat!:`, so release-please treats it as breaking.

## Capabilities

### New Capabilities
<!-- None. -->

### Modified Capabilities
- `plotter-svg-export`: the plotter SVG becomes the only output. There is no `--format` any more, and the scenarios drop `--format plotter`.
- `poster-output`: `--output` accepts `.svg` only. The raster resolution and vector size-limit requirements are removed.
- `poster-colors`: the colour keys shrink to the pen colours (`text`, `water`, `parks`, road classes). The PNG scenario is removed.
- `poster-editor`: edits apply to the plotter SVG only. The raster scenarios are removed, and "format" is no longer among the settings edits survive.
- `package-layout`: the bundled data no longer includes fonts, and there is no Google Fonts cache.
- `poster-web-ui`:
  - removed: the workflow choice and the PNG resolution
  - changed: the form contents, theme selection (pen presets), validation, CLI invocation, result preview, history, file access, zoom, load, customize, export and pens requirements, to plotter-only

## Impact

- **Code:**
  - `poster.py` shrinks by about 300 lines.
  - `fonts.py` and `size.py` are deleted.
  - `plotter.py` gains the text-layout helpers.
  - `web.py`, `colors.py`, `paths.py` and the static files (`index.html`, `app.js`, `form.js`, `editor.js`, `style.css`) change.
- **Data:** `data/fonts/` is deleted and the 17 theme JSON files are trimmed.
- **Dependencies:** `matplotlib` is removed from `pyproject.toml`. `uv.lock` and `requirements.txt` are regenerated, dropping contourpy, cycler, fonttools, kiwisolver, pillow and pyparsing. The Docker image gets smaller.
- **Tests:** 13 print-only tests are deleted, about 16 are adapted, and a few are added: `--format` is rejected, `.png` output is rejected, and matplotlib is not imported.
- **Docs:** README, CHANGELOG and `test/all_variations.sh`, plus new `docs/images/*.png`.
- **Users:** none released yet. Anyone running the unreleased `main` loses print output and must use another maptoposter copy for print posters. Saved web form settings are reset once, because the form's storage key changes.
