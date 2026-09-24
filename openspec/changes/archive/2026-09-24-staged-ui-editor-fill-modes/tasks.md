# Tasks

## 1. CLI output control and cache-only mode

- [x] 1.1 Add `--output` and `--dpi` to `create_map_poster.py`: validate the extension against the format, reject `--output` with `--all-themes` and reject `--dpi` ≤ 0 before any download, create parent directories, and pass the dpi to the PNG `savefig`. Verify with CLI arg tests (mismatch, all-themes, dpi 0) and a test that a 254×254 mm PNG at `--dpi 50` is 500×500 px.
- [x] 1.2 Add `NotCachedError` and cache-only handling: `--cache-only` swaps the downloaders in `fetch_graph`/`fetch_features` for ones that raise. The graph error is fatal ("map data is not cached"), features fall back to the existing warning, and `get_coordinates` raises when there is no cached geocode. Verify with `test/test_osm_cache.py` tests: cached/cropped area loads, missing graph exits non-zero, missing water warns, and no Overpass/Nominatim call is made (monkeypatched to fail).

## 2. Edit list

- [x] 2.1 Create `poster_edits.py` with the edit-list dataclasses and `parse_edits(obj)` / `load_edits(path)`, implementing every validation rule of the "Edit list format" requirement (version, polygons ≥ 3 numeric points, known text entries and layers, unknown members rejected). Verify with the new `test/test_edits.py` covering the valid example, unknown layer, 2-point polygon, bad JSON and the empty object.
- [x] 2.2 Add `--edits <file>` to the CLI, loaded and validated before coordinates or download, with a non-zero exit on error. Verify with a CLI test using a broken file.

## 3. Plotter fills and edits

- [x] 3.1 Extract `concentric(area, spacing, pen)` from `fill_area` (which keeps its behaviour by calling it with `spacing=pen`), and add a `render_areas` mode dispatch (`hatch`/`concentric`) with per-area spacing. Verify in `test_plotter_svg.py`: concentric rings are closed, lie inside the area, are `spacing` apart and follow holes, and the existing road-fill tests still pass.
- [x] 3.2 Extend `PlotterSettings` and the CLI with `--water-fill`, `--parks-fill`, `--water-spacing`, `--parks-spacing` (defaulting to the hatch spacing, each ≥ pen width) and `--water-outline`. Verify the CLI rejects `--water-fill spiral` and `--parks-spacing` below the pen width.
- [x] 3.3 Implement the water outline (boundary of `water ∩ page` minus roads/text, in the water layer; the fill inset by the spacing when on). Verify with tests: a lake plus island yields closed outline strokes, no outline stroke lies inside a crossing road buffer, and no outline appears when the option is off.
- [x] 3.4 Apply edits in `plotter_svg.render`: erase polygons join the road knockout and the area/outline exclusion, `layout_text` supports per-line `dx`/`dy`/`hidden` (knockout follows), and hidden layers are skipped. Verify with tests: no road/water/park stroke inside an erase rectangle, text and attribution intact, the city moved by `dy=-10` shifts its polylines by −10 mm, and a hidden parks layer is absent from the SVG.

## 4. Raster edits

- [x] 4.1 Apply edits in `create_poster` (matplotlib): hidden layers are skipped (road classes filtered), erase polygons are drawn as background-colour patches at zorder 9, and text anchors are offset or hidden. Verify with a PNG render test on the fixture graph: pixels inside the erase rectangle equal the theme background, and a hidden coords line leaves its region background-only while the attribution pixels remain.
- [x] 4.2 Update `print_examples`, `--help` texts and the README CLI options table for all new options. Verify that `python create_map_poster.py --help` lists them.

## 5. Web server: sessions and job kinds

- [x] 5.1 Split `PosterConfig` into `LocationConfig` and `CustomizeConfig` (adding fill modes, per-area spacings, water outline and edits via `poster_edits`), and extend `validate_config` with the new rules. Verify with updated `test_web_app.py` validation tests (per-area spacing, invalid fill mode, invalid edits).
- [x] 5.2 Add the `Session` (working dir `cache/web/<id>/`, cleared on startup) and give `Job` a `kind`. Implement the arbitration rules: a preview replaces a preview, load/export are exclusive, and a preview during load/export gets 409. Verify with tests for "newer preview wins", "concurrent request rejected" and "cancel".
- [x] 5.3 Add `POST /api/load`, `POST /api/preview`, `POST /api/export`, `GET /api/preview` and `GET /api/layout`, and remove `POST /api/jobs`. Build the arguments with `--cache-only`, `--output`, `--dpi` and `--edits` as the spec requires. Verify with tests: the load command has `--output`/`--dpi` but no `--cache-only`, preview/export commands contain `--cache-only`, preview before load is rejected, previews do not appear in `/api/posters`, and the export command matches the "Command built from form" scenario.

## 6. Web frontend

- [x] 6.1 Restructure `index.html`/`style.css` into the Location and Customize steps with a step indicator and the new plotter inputs (fill modes, spacings, outline), with "Back to location" and the Customize step locked until loaded. Verify manually in the browser: defaults match the spec and the plotter inputs toggle with the format.
- [x] 6.2 Split `app.js` into `form.js` (field helpers) and `app.js` (step state machine, load/preview/export calls, debounced auto-preview, busy/outdated preview states, a "reload location" prompt on not-cached errors). Verify manually: loading Paris opens Customize, a theme change shows a new preview and the log shows `--cache-only`, and export adds exactly one history entry.
- [x] 6.3 Build `editor.js`: an SVG overlay in page mm, rectangle/freehand erase, select + delete, dragging text handles from `/api/layout`, text and layer toggles, undo/redo/reset, and a confirm-and-clear when location or size changes. Verify manually against the editor scenarios (erase a region, drag the city 20 mm, undo, theme change keeps edits, new location clears edits).

## 7. Integration

- [x] 7.1 Run the full test suite (`uv run pytest`) and `flake8`, and fix any failures. Verify both pass cleanly.
- [x] 7.2 End-to-end check with the running web UI (`python web_app.py`): load a real city, switch across three themes, switch to plotter with concentric water, outline and custom spacing, erase a region, move the city, and export PNG and plotter. Confirm that no Overpass requests appear in the log after the load, and that both exported files show the edits.
- [x] 7.3 Update the README "Web interface" section for the two-step flow and the editor, and add a CHANGELOG entry. Verify that the README renders and that the documented options match `--help`.

## 8. Workflow choice, zoom and preview errors (review feedback)

- [x] 8.1 Add `mode` (`print`/`plotter`) to the Location config. Validate the 500 mm limit for print in Location. In `validate_customize`, force format `plotter` in plotter mode and reject `plotter` in print mode. Load renders the plotter SVG in plotter mode. Print previews use about 2000 px. Verify with web tests: print 600 mm rejected, plotter 600 × 900 load has `--format plotter` and an svg preview, and in plotter mode a preview with format `png` still renders as plotter.
- [x] 8.2 In the frontend: workflow cards in Location, a Customize header (mode, place, size), options per workflow (format and font family vs pen options, with "Pen colours" wording), and preview errors shown on the preview. Verify in the browser that a 600 × 900 plotter session previews and that theme changes re-render.
- [x] 8.3 Add zoom and pan: +/−/fit, zoom percentage, Ctrl+wheel zoom around the pointer, a Pan tool and middle-mouse panning. Editor tools keep working when zoomed. Verify in the browser that an erase drawn at 400 % zoom is stored in page mm at the expected position.
- [x] 8.4 Rebuild and restart the Docker Compose container, and verify that the new UI is served on port 8001.

