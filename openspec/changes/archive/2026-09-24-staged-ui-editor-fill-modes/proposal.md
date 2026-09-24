# Proposal

## Why

The web UI is one long form. Every change, even just the theme, starts a full CLI run and only shows the result once the final file is written. With cached data this still reloads and reprojects everything. Without a cache hit, a small tweak can trigger a new download from a slow Overpass server. Users also can't fix details on the finished poster, like a label in the wrong place or a hatch over a spot they want empty, without leaving the tool. For pen plotters, water and parks can only be hatch-filled at one shared spacing, and water has no outline, so shorelines look ragged and every area looks alike.

## What Changes

- **Two-step web UI.**
  - **Step 1 "Location"**: city, country, optional lat/lon, distance, poster size and OpenStreetMap server. Pressing "Load map" downloads (or loads from the cache) the map data and shows a quick low-resolution preview.
  - **Step 2 "Customize"**: theme, labels, fonts, output format, plotter options, fill options and the editor. Every change here re-renders the preview **from the already-fetched data and never downloads map data**. "Export" writes the final poster to `posters/`.
  - Changing anything in step 1 means going back to step 1 and loading again.
- **Cache-only rendering.** A new CLI option `--cache-only` makes a run fail with a clear error instead of downloading when the map data is not cached. The web UI passes it on every step-2 render, so "no redownload" is guaranteed, not just likely.
- **Preview output.** New CLI options `--output <path>` (write to an explicit file instead of `posters/`) and `--dpi <n>` (PNG resolution, default 300). The web UI uses them for fast, low-DPI previews that do not clutter `posters/` or the history.
- **In-browser editor.** In step 2 the preview can be edited:
  - erase regions of the map
  - move or edit the city, country and coordinate texts, and hide single text lines
  - hide individual layers (water, parks, road classes)

  Edits are stored as a small JSON edit list in page millimetres and passed to the CLI with a new `--edits <file>` option. They are re-applied on every re-render and export, for every output format, so theme or pen changes never lose them.
- **Plotter fill options.**
  - Fill mode per area type: `--water-fill` / `--parks-fill` with `hatch` (current behaviour, default) or `concentric` (inset contours that follow the shape).
  - Line spacing per area type: `--water-spacing` / `--parks-spacing`. These default to `--hatch-spacing` and must not be less than the pen width.
  - Optional water outline: `--water-outline` draws the water shoreline as a stroke in the water layer.
- **BREAKING (web UI only):** the single "Generate poster" form and its `POST /api/jobs` payload are replaced by the step flow and new endpoints. The CLI stays backwards compatible, and all new options are optional.

## Capabilities

### New Capabilities
- `poster-editor`: the edit list (erase regions, text overrides, hidden layers), how the CLI applies it via `--edits` for all formats, and the in-browser editing tools in step 2.
- `poster-output`: CLI output control for scripted and preview use: `--output` target path and `--dpi` for PNG.

### Modified Capabilities
- `poster-web-ui`: the single form, job and result flow is replaced by the two-step Location → Customize flow with live previews, cache-only re-rendering and an explicit export. Validation, the single running job and the history requirements change accordingly.
- `plotter-svg-export`: "Hatch-filled areas" becomes configurable per area type (fill mode `hatch` or `concentric`, separate spacing). A new optional water outline is added.
- `osm-data-source`: adds cache-only mode (`--cache-only`), which fails instead of downloading.

## Impact

- `create_map_poster.py`: new options `--cache-only`, `--output`, `--dpi`, `--edits`, `--water-fill`, `--parks-fill`, `--water-spacing`, `--parks-spacing` and `--water-outline`. The fetch helpers honour cache-only, and the edit list is applied in both the matplotlib and plotter render paths.
- `osm_cache.py`: `load_area` gets a no-download mode.
- `plotter_svg.py`: concentric fill, per-area spacing and angle settings, water outline, erase-region and hidden-layer knockouts, and text overrides in `layout_text`.
- `web_app.py`: a project (session) model holding the step-1 config, the edit list and preview files under `cache/web/`, with new endpoints for load, preview, export and the preview file. Preview jobs replace each other, and export is exclusive.
- `web/static/`: the page is restructured into two steps, with an SVG overlay editor (plain JS, no build step).
- Tests: `test/test_web_app.py`, `test/test_plotter_svg.py` and a new `test/test_edits.py`. The README gets updated CLI options and a web UI walkthrough.
- No new dependencies.
