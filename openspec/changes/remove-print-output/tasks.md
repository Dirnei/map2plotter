# Tasks

## 1. CLI: plotter-only

- [x] 1.1 Move `is_latin_script`, `format_city_title`, `format_coordinates` and `BASE_*` into `plotter.py`, and add `poster_texts(...)` (design Decision 3). Use it in `poster.py`'s plotter branch and in `web /api/layout`, which then imports only `plotter`. Verify that `test_plotter_svg.py` and the layout test pass, and that the SVG for the `cli` fixture is byte-identical before and after (diff of one rendered file).
- [x] 1.2 Reduce `poster.py` to the plotter pipeline (design Decisions 1 and 2):
  - remove `--format`, `--dpi` and `--font-family`, and require `--output` to end in `.svg`
  - delete the matplotlib rendering and helpers, `FONTS`/`load_fonts` and the PNG check
  - trim `print_examples`, the epilog and the help texts

  Verify that `map2plotter --help` shows none of `--format`, `--dpi`, `--font-family`, `png` or `pdf`, and that `map2plotter -c X -C Y --format png` exits with code 2.
- [x] 1.3 Delete `fonts.py`, `size.py`, `data/fonts/` and `paths.FONTS_DIR`. Set `colors.THEME_COLOR_KEYS` to the pen keys, remove `bg`/`gradient_color` from the 17 themes and the `load_theme` fallback, and make theme loading ignore extra keys (design Decision 4). Verify that `--list-themes` lists 17 themes, that `--color bg=#000000` fails naming `bg`, and that a theme file with an extra `bg` key still loads.
- [x] 1.4 Update `test_cli.py`: delete the 9 print tests and the `render_png`/`red_rows`/matplotlib/PIL/`poster_size` imports, adapt the tests using `-f`/`.png`, and add tests for `--format` rejected, `.png` output rejected and `--color bg` rejected. Verify that `pytest test/test_cli.py test/test_plotter_svg.py test/test_edits.py` passes.

## 2. Web interface: plotter-only

- [x] 2.1 Server (design Decision 5):
  - remove `mode`, `font_family`, `format` and `dpi` from the configs
  - remove the mode/format coupling, the PNG limit, `export`, `preview_size`/`preview_dpi`, `PREVIEW_*`, the width/height overrides of `location_args` and `MPLBACKEND`
  - always render `rendering.svg`
  - make `POSTER_TYPES` SVG only
  - `get_themes` returns pen keys only

  Verify with `test_web_app.py` after task 2.3.
- [x] 2.2 Page:
  - remove the mode fieldset, theme grid, font family, format/dpi/`#png-size` fieldset, `#layer-toggles-panel`, `#preview-img` and `#mode-badge`
  - move the hidden `theme` input into the pens fieldset
  - remove `applyMode`/`currentMode`/`MODE_NAMES`, the PNG section, the raster branch of `showPreview` and the `saved.format` migration from `app.js`
  - remove the `layerToggles` option from `editor.js`
  - make `posterCard` SVG only, and remove the unused CSS (`.modes`, `.mode-card`, `.mode-badge`, `.png-size`, `.stage img`, `.card .preview.doc`)
  - set the form storage key to `map2plotter-form-v2`

  Verify in the browser at desktop and phone width: load Hallstatt (cached) at 1000 m, then check the pens list and the preset, the colour change without a render, erase/move/hide, export, and the history showing only SVGs. The console must show no errors.
- [x] 2.3 Update `test_web_app.py`:
  - delete the 4 print tests
  - adapt the tests using `mode`, `format`, the `bg` key or png names (the fake CLI writes `.svg`)
  - add tests: old print fields ignored, history lists only `.svg`, `/api/posters/x.png` rejected

  Verify that `pytest test/test_web_app.py` passes.

## 3. Dependencies and packaging

- [x] 3.1 Remove `matplotlib` from `pyproject.toml`, run `uv lock` and `uv sync`, and regenerate `requirements.txt`. Add a test that runs a fresh interpreter importing `map2plotter.poster` and `map2plotter.web` and asserts `"matplotlib" not in sys.modules`. Verify that `requirements.txt` no longer lists matplotlib, contourpy, cycler, fonttools, kiwisolver, pillow or pyparsing, that the full `pytest` suite passes (report the count), and that `flake8 src test` is clean.
- [x] 3.2 Run `docker compose up -d --build`. Verify that the container is healthy, that a web load and preview (Hallstatt 1000 m) and an export produce SVGs, that `docker compose run --rm map2plotter --list-themes` works, and that the image is smaller than before (`docker image ls map2plotter`, before and after).

## 4. Documentation

- [x] 4.1 Render 4-5 example SVGs from the cached cities with `--cache-only`, rasterize them to PNG on white paper, about 1000 px on the long side, and put them in `docs/images/` (design Decision 7). Verify that no network request was made (use `--cache-only`), and that every PNG is under 400 KB and shows the whole poster, text included.
- [x] 4.2 Rewrite the README around pen plotting, as a short page (pitch, attribution, gallery, quick start, a few examples, plotting tips) that links to `docs/reference.md` for the details:
  - intro and attribution
  - an example gallery with commands
  - installation (uv, pip, Docker Compose, Docker)
  - CLI usage and options
  - the web interface (Location → Customize, pens and layers, editor, zoom, history)
  - fills and pen width
  - Inkscape/vpype workflow
  - OpenStreetMap servers and cache
  - edit lists
  - themes (now pen colour presets) and custom themes
  - Latin-only labels
  - project structure
  - releases

  Remove the print gallery, the resolution guide, the i18n/font sections and the matplotlib Hacker's Guide. Update `test/all_variations.sh` to plotter commands (no `--font-family`, no `-f`). Verify that `grep -n -i "png\|pdf\|dpi\|font-family\|matplotlib\|--format\|print poster" README.md` finds only intended mentions (for example the example image files), and that every image path in the README exists.
- [x] 4.3 Add a "Removed" section to the CHANGELOG's "Changes since maptoposter 0.3.0" notes: print output, `--format`, `--dpi`, `--font-family`, Google Fonts, `bg`/`gradient_color`, the web print workflow, and the PNG/PDF history. Edit the Purpose lines of the main specs `poster-output`, `poster-colors` and `poster-editor`, so they no longer mention raster output or formats. Verify with `openspec validate --specs`.

## 5. Final check

- [x] 5.1 Check the remaining code: `grep -rn -i "matplotlib\|dpi\|font_family\|load_fonts\|poster_size\|output_format\|\"png\"\|\.pdf" src test` finds nothing, except SVG-specific uses that are intended. Also: `flake8 src test` is clean, the full `pytest` suite passes, and `openspec validate remove-print-output --strict` passes.
