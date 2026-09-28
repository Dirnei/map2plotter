# Design

## Context

- **`poster.py`:**
  - `create_poster` fetches the data (shared), then either calls `create_plotter_poster` (L663-668) or renders with matplotlib (L670-872).
  - The print-only helpers are `create_gradient_fade`, `get_edge_colors_by_type`, `get_edge_widths_by_type` and `add_erase_patches`.
  - Importing the module runs `FONTS = load_fonts()`.
  - `main` has format-dependent branches: the PNG pixel check through `size.py`, `PlotterSettings` only for `plotter`, an "ignoring plotter options" warning, and the extension map for `--output`.
- **Text layout helpers** (`is_latin_script`, `format_city_title`, `format_coordinates`, `BASE_SUB`/`BASE_COORDS`/`BASE_ATTR`) live in `poster.py`. They are used by the plotter branch and by `web /api/layout`, which imports all of `poster.py` (osmnx, matplotlib, `load_fonts`) to build the same `texts` dict as `create_plotter_poster`.
- **matplotlib** is imported only by `poster.py`. For osmnx 2.0.7 and geopandas 1.1.2 it is an optional extra, so removing it also drops contourpy, cycler, fonttools, kiwisolver, pillow and pyparsing from the lock.
- **`web.py`** branches on `LocationConfig.mode` (`print`/`plotter`) and `CustomizeConfig.format`/`dpi`/`font_family`:
  - Print loads and previews render a scaled PNG (`preview_size`, `preview_dpi`, `PREVIEW_MAX_MM`, `PREVIEW_PIXELS`).
  - Plotter loads and previews render the full-size SVG.
  - `POSTER_TYPES` covers png/svg/pdf.
- **Frontend:**
  - `index.html` has `data-mode="print"` / `data-mode="plotter"` sections.
  - The theme grid appears only in print mode; plotter mode uses the pens list with `#pen-theme`.
  - `app.js` has the PNG section (`updatePngInfo` and the PNG constants), plus `applyMode` and `MODE_NAMES`.
  - `editor.js` builds `#layer-toggles`, which only print mode shows.
- **Themes:** 17 files with the keys `bg`, `text`, `gradient_color`, `water`, `parks` and six `road_*` keys. The plotter uses `text`, `water`, `parks` and the road keys.
- **Tests:** 182 passing. 9 CLI and 4 web tests exercise print only.
- **Map data cache:** locally cached areas exist for Amsterdam, Venice, Barcelona, Hallstatt and Unterwössen.

## Goals / Non-Goals

**Goals:**
- One output and one code path: no `format` branching left in the CLI, the server or the page.
- The web server's layout endpoint no longer imports the CLI module.
- A README that describes the tool as it is, with example images that come from its own output.

**Non-Goals:**
- A raster export of plotter SVGs (PNG previews for sharing).
- Non-Latin stroke fonts. Characters Hershey lacks are still skipped with a warning.
- Changing the plotter rendering itself (fills, layers, pen width, knockouts).
- Performance work on large SVG previews. See Risks.

## Decisions

### 1. Remove `--format` instead of keeping `--format plotter` as a no-op
Nothing has been released yet, so no user script depends on the option, and a single-value option is noise. argparse then rejects `--format` / `-f` as an unknown option (exit 2), which the spec requires. `generate_output_filename` always uses `.svg`. `--output` must end in `.svg`, compared case-insensitively.

*Alternative:* keep `-f plotter` accepted and reject the other values with a hint. Friendlier for old command lines, but it keeps a meaningless option in `--help` forever.

### 2. `create_poster` becomes the plotter pipeline
- The matplotlib part and its helpers are deleted, along with `numpy`/matplotlib/`orient`/`size`/`fonts` imports that are no longer used.
- `create_poster` keeps the shared fetch step and then renders through `plotter`. `create_plotter_poster` is folded into it, or kept as a helper it calls.
- Its signature loses `output_format`, `fonts` and `dpi`, and `plotter_settings` becomes required.
- `main` always builds `PlotterSettings`, runs the spacing checks as before, and drops the PNG check, the "only apply to --format plotter" warning and the `load_fonts` call.
- The positive-value check drops `dpi`.
- `print_examples`, the argparse epilog and the `--width`/`--height` help lose PNG and `-f` references.

### 3. Text layout moves into `plotter.py`
`is_latin_script`, `format_city_title`, `format_coordinates`, `BASE_SUB`/`BASE_COORDS`/`BASE_ATTR` (and `BASE_MAIN`) move to `plotter.py`, together with a new builder:
```
poster_texts(display_city, display_country, lat, lon, width_mm, height_mm) -> texts dict
```
It replaces the duplicated dicts in `create_plotter_poster` and `web /api/layout`. `/api/layout` then imports only `plotter`, which uses shapely, scipy and Hershey but not osmnx. The layout is the plotter's own concern: its comment "matching the raster layout" becomes plain "poster layout".

*Alternative:* a new `layout.py` module. It would be cleaner in theory, but the functions are only used together with plotter rendering, and one more module adds nothing here.

### 4. Colour keys and themes
- `colors.THEME_COLOR_KEYS` becomes `text`, `water`, `parks` and the six road keys, so `--color bg=…` fails with the existing "unknown key" error.
- `bg` and `gradient_color` are removed from the 17 built-in themes and from `load_theme`'s fallback theme.
- `load_theme` keeps loading files that still have the keys (custom themes) and ignores them. `get_themes` in `web.py` returns only the pen keys.

### 5. The web interface becomes single-workflow
- **Server:**
  - `LocationConfig.mode` and `CustomizeConfig.font_family`/`format`/`dpi` are removed. Pydantic ignores unknown fields, so older pages or saved forms that still send them just work.
  - `validate_customize` drops the mode/format coupling and the PNG limit, so its `export` flag goes away. The spacing checks always apply.
  - `customize_args` always emits the plotter options. `location_args` loses its width/height overrides. `preview_size`, `preview_dpi`, `PREVIEW_*` and the `MPLBACKEND` env entry are removed.
  - `/api/load` and `/api/preview` always render `rendering.svg` at the full size.
  - `POSTER_TYPES = {".svg": "image/svg+xml"}` limits the history, preview and download to SVG.
- **Page:**
  - The "What are you making?" fieldset, the theme grid fieldset, font family, the file-format fieldset (format, dpi, `#png-size`), `#layer-toggles-panel` and `<img id="preview-img">` are removed.
  - The hidden `theme` input moves into the pens fieldset, and `#mode-badge` goes. The mode bar keeps the place and size summary and "Change".
  - In `app.js`: `applyMode`, `currentMode`, `MODE_NAMES`, the PNG section and the raster branch of `showPreview` are removed, and the `saved.format` migration goes.
  - `editor.js` loses its `layerToggles` option; layer visibility stays in the pens list, through `setLayerVisible`/`layerHidden`.
  - `posterCard` handles SVG only.
  - The form's storage key becomes `map2plotter-form-v2`, so print values saved by the old page are not restored. The pens key is unchanged.

### 6. matplotlib is removed from the dependencies
- `matplotlib` comes out of `pyproject.toml`, then `uv lock`, `uv sync` and `uv export` run.
- `test_cli.py`'s `matplotlib.use("Agg")` and PIL imports go with the raster tests.
- A test checks that importing `map2plotter.poster` and `map2plotter.web` in a fresh interpreter does not load `matplotlib`. That catches a stray import that the installed dev environment would otherwise hide.

### 7. Example images for the README
- Plotter SVGs are rendered with `map2plotter --cache-only` from the cached cities, choosing distances the cache covers (`--cache-only` fails fast otherwise), at a small paper size such as 200 × 280 mm, with a few different themes and fill modes.
- They are rasterized to PNG on white paper, about 1000 px on the long side, with headless Chromium (the Playwright browser already used for UI checks). The target is under 400 KB each, so the repository stays small.
- The README shows them with the exact command under each.
- The PNGs are committed in `docs/images/`, and the SVGs are not.

*Alternatives:*
- Commit the SVGs and show them directly. They are sharp, but 0.3-6.5 MB each, and their transparent background hides dark strokes on GitHub's dark theme.
- Photos of real plots. That is better later, but none exist yet.

### 8. Tests
- **Deleted:**
  - CLI: `test_output_path_and_dpi`, the four `test_raster_*` tests, `test_color_override_in_png`, `test_oversized_png_rejected_with_suggested_dpi`, `test_png_limits` and `test_large_svg_and_pdf_not_clamped`
  - web: `test_png_export_pixel_limit`, `test_format_follows_workflow`, `test_plotter_options_omitted_for_other_formats` and `test_preview_size_and_dpi`
  - the helpers `render_png`/`red_rows`
- **Adapted:** the tests that pass `-f plotter`, `mode=`, `format=`, png file names or the `bg` key, as listed in the code map. The fake CLI writes `paris_noir_1.svg`.
- **Added:**
  - `--format` rejected
  - `.png` output rejected
  - `--color bg=` rejected
  - no matplotlib import
  - history ignores `.png`
  - `/api/posters/x.png` rejected
  - old print fields ignored by the server
  - `/api/layout` works without importing `map2plotter.poster`
- **Expected count:** 182 − 13 + about 8 new ≈ 177, confirmed at the end.

### 9. Commit type
The commit message is `feat!: make map2plotter plotter-only and drop print output`. The `!` makes release-please treat it as breaking. Before 1.0.0 the `release-as` setting decides the version anyway.

## Risks / Trade-offs

- [Loads at large distances render a full-size plotter SVG as the preview, instead of a light PNG] → This is how the plotter workflow already behaves today. Measure a load at the default 18 km. If it is too slow, open a follow-up change (a preview-only simplification, for example) rather than keeping the raster path.
- [Display names in non-Latin scripts lose characters] → Accepted scope. The warning stays, and the README says labels must be Latin.
- [Old PNG and PDF files in `posters/` disappear from the web history] → Documented in the README and CHANGELOG. The files themselves are untouched.
- [An example city's cached area is smaller than the distance chosen for its image] → `--cache-only` fails immediately. Pick a smaller distance, and never download for the examples.
- [A spec purpose line still mentions raster output after the sync, because delta specs cannot change a purpose] → A task edits the purposes of `poster-output`, `poster-colors` and `poster-editor` directly.

## Migration Plan

This all lands before 1.0.0. Users of `main` run `uv sync`; the old matplotlib packages are removed from the environment. Docker users rebuild. Rollback: revert the commit.
