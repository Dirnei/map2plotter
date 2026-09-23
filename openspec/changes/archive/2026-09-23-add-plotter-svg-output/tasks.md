# Tasks

## 1. Setup

- [x] 1.1 Add `Hershey-Fonts` to `pyproject.toml` dependencies and `requirements.txt`, and add `pytest` to `requirements.txt`. Verify that `uv sync` succeeds and that `python -c "from HersheyFonts import HersheyFonts"` works
- [x] 1.2 Create an empty `plotter_svg.py` module containing a `PlotterSettings` dataclass (`width_mm`, `height_mm`, `pen_width`, `hatch_spacing`). Add it to `pyproject.toml` `py-modules` and to the `Dockerfile` `COPY` lines. Verify that `python -c "import plotter_svg"` works
- [x] 1.3 Create `test/test_plotter_svg.py` with a smoke test that imports the module. Verify that `pytest test/` passes

## 2. Geometry primitives (plotter_svg.py)

- [x] 2.1 Implement the metres→mm page transform (D2) and the page-box clipping. Verify with a test that crop-box corners map to `(0,0)` and `(W,H)`, with y flipped
- [x] 2.2 Implement `hatch(polygon, spacing, angle)` (D5). Verify with tests that the lines stay inside the polygon, that adjacent spacing equals `spacing`, and that a polygon with a hole gets no lines inside the hole
- [x] 2.3 Implement the multi-stroke area fill: concentric insets plus centerline, dropping rings shorter than `2×pen` (D4). Verify with a test that a straight 1.2 mm road with a 0.3 mm pen is fully covered: sample points across its width, each within `pen/2` of some stroke
- [x] 2.4 Implement the single-stroke centerline path for `w <= pen`. Verify with a test that a 0.25 mm road with a 0.3 mm pen yields exactly the merged centerline
- [x] 2.5 Implement greedy nearest-endpoint polyline ordering with reversal (D7). Verify with a test that total pen-up travel on a shuffled input is not greater than on the unordered input

## 3. Roads, areas and knockouts

- [x] 3.1 Implement road classification into rank/colour buckets that reuse the existing highway→class mapping, with target widths per D3. Verify with a test that motorway width at 304.8 mm min-dimension ≈ 0.423 mm, and that it scales linearly with size
- [x] 3.2 Implement the rank-ordered road rendering with higher-class knockout (D4). Verify with a test that a residential line crossing a primary line has no strokes inside the primary area
- [x] 3.3 Implement the water and park hatching, with road and text areas subtracted and GDFs reprojected to the graph CRS (D2, D5). Verify with a test that a road crossing a park polygon leaves no hatch inside the road buffer

## 4. Typography

- [x] 4.1 Implement Hershey text rendering to mm polylines with measured width, centre/right alignment, `futuram` for the city and `futural` for the rest (D6). Verify with a test that rendered "PARIS" is centred on the requested x within 0.01 mm
- [x] 4.2 Implement glyph fallback: NFKD accent stripping, synthesised `°`/`©`, and skip-with-warning for other code points. Verify with tests that `Zürich` renders, that `©` produces paths, and that Japanese text prints a warning and returns without raising
- [x] 4.3 Implement the poster text layout (city with the Latin spacing rule, country, coords, divider, attribution) at the existing axes-fraction anchors and scaled font sizes, plus the padded text knockout polygon. Verify with a test that the knockout contains every text polyline

## 5. SVG output

- [x] 5.1 Implement the ElementTree SVG writer: mm root size and viewBox, inkscape namespace, and one layer per distinct colour with stroke, `fill="none"`, `stroke-width=pen`, round caps and joins, and coordinates rounded to 0.001 (D7). Verify with tests that parse the output and check root attributes, the layer count, that shared colours are merged, and that there is no `image`/`text`/gradient/`font` element and no non-`none` fill
- [x] 5.2 Implement `plotter_svg.render(...)` to tie the roads, areas, text, layer ordering and writing together. Verify with an end-to-end test on a small synthetic graph and GDFs that every coordinate lies within `[0,W]×[0,H]`

## 6. CLI integration (create_map_poster.py)

- [x] 6.1 Add an `aspect` parameter to `get_crop_limits` and update the matplotlib call site. Verify that a `--format png` run still produces a poster identical in layout to before
- [x] 6.2 Add `plotter` to the `--format` choices and add the `--pen-width`, `--width-mm`, `--height-mm` and `--hatch-spacing` args, with validation (> 0, hatch ≥ pen) and mm↔inch derivation (D8). Verify manually that `--pen-width 0`, `--width-mm -1` and `--pen-width 0.5 --hatch-spacing 0.2` each exit non-zero with an error
- [x] 6.3 Make `generate_output_filename` map `plotter` to a `.svg` extension, and dispatch to `plotter_svg.render` in `create_poster` after the fetch phase. Verify by running `python create_map_poster.py -c Venice -C Italy -d 3000 --format plotter --width-mm 300 --height-mm 400 --pen-width 0.3`, checking that it writes an `.svg` with `width="300mm"`, and that it opens in Inkscape with per-colour layers
- [x] 6.4 Update the help text in `print_examples()` and the argparse epilog. Verify that `python create_map_poster.py --help` lists the new options

## 7. Docs and checks

- [x] 7.1 Update README with the plotter format, the new options, an example and a tip on `vpype linemerge linesort` post-processing. Verify that the README renders and that the options table matches `--help`
- [x] 7.2 Add a plotter example to `test/all_variations.sh`. Verify that the script line runs successfully
- [x] 7.3 Run `flake8` and `pytest test/`. Verify that both pass cleanly
