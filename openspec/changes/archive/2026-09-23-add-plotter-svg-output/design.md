# Design

## Context

`create_poster()` in `create_map_poster.py` does three things. It fetches OSM data: a street graph plus water and park GeoDataFrames, cached in `cache/`. It projects the graph, then draws everything through matplotlib and ends with `plt.savefig`. The crop window comes from `get_crop_limits(g_proj, point, fig, dist)`. That function reads the aspect ratio from the matplotlib figure. Road colours come from `get_edge_colors_by_type`, and road widths in points from `get_edge_widths_by_type` (1.2 / 1.0 / 0.8 / 0.6 / 0.4 pt at a 12-inch reference). Text is placed in axes fractions: city at y=0.14, country at 0.10, coords at 0.07, divider at 0.125 spanning x 0.4–0.6, and attribution at the bottom right (0.98, 0.02). The repo has no Python test suite; `test/` only holds a shell script. For motivation see proposal.md. For the behaviour contract see `specs/plotter-svg-export/spec.md`.

## Goals / Non-Goals

**Goals:**
- Reuse the existing data fetching, caching, projection and crop logic unchanged. Plotter rendering is a separate back-end.
- Keep the geometry pipeline in pure functions (shapely in, lists of mm polylines out) so it can be unit-tested without network access.
- Produce output that opens correctly in Inkscape and in vpype/AxiDraw tooling as delivered.

**Non-Goals:**
- Full plot-path optimisation (TSP ordering, line merging across layers). We do a cheap greedy ordering only and document `vpype linemerge linesort` for users who want more.
- Pen-specific output such as G-code or HPGL. SVG only.
- Separate pen widths per layer. There is one global `--pen-width`.
- Plotter rendering of the gradient fades or the background. Paper is the background.

## Decisions

### D1: New module `plotter_svg.py`, dispatched from `create_poster`
`create_poster` keeps doing the fetch phase. When `output_format == "plotter"`, it calls `plotter_svg.render(...)` with the projected graph, the water/park GDFs, the crop box, the theme, the text strings and a `PlotterSettings(width_mm, height_mm, pen_width, hatch_spacing)` dataclass, and returns before any matplotlib code runs. `get_crop_limits` gets an `aspect` parameter so it no longer needs a figure. The matplotlib path passes `fig_width / fig_height` and the plotter path passes `width_mm / height_mm`.
*Alternative:* post-process the matplotlib SVG. Rejected because matplotlib writes filled paths, raster images and stroke widths in points. Converting those back into pen geometry is harder than building the geometry directly.

### D2: Work in projected metres, convert to mm at the end
Features are first cropped to the crop box in the graph's projected CRS. A single uniform affine transform, `s = width_mm / (xmax - xmin)`, `x_mm = (x - xmin)·s`, `y_mm = (ymax - y)·s` (SVG y points down), then maps them to page mm. All boolean operations (buffer, union, difference, hatching) run in mm afterwards. Because the transform is a uniform scale plus a reflection, this is equivalent to working in metres, and it lets pen widths, road widths and text all use the same unit. Water and park GDFs are always reprojected with `to_crs(g_proj.graph["crs"])`, so all layers share one CRS. The matplotlib path currently uses `project_gdf` with a fallback, and we do not change it.

### D3: Road target widths
The existing pt widths are converted to mm (`pt × 25.4/72`) and scaled by `min(width_mm, height_mm) / 304.8`. That matches the existing `scale_factor` that the raster output uses for text. Motorway then comes to about 0.42 mm on a 30 cm-wide poster. The class order is motorway > primary (incl. trunk) > secondary > tertiary > residential/default. `road_residential` and `road_default` share a width but may differ in colour, so they are processed as separate colour buckets with the same rank.

### D4: Multi-stroke fill by concentric offset contours + centerline
For each class, from highest rank to lowest:
1. `area = unary_union(lines.buffer(w/2, cap_style=round, join_style=round))`, minus the union of the higher-ranked class areas, minus the text knockout, intersected with the page box.
2. If `w <= pen`, emit the class centerlines clipped to that same area (via `linemerge`) as single strokes.
3. Otherwise, emit contours: take `area.buffer(-pen/2)` and output its exterior and interior rings. Repeat with an extra `-pen` each step until the result is empty. Also emit the clipped centerlines. They fill the core that remains when the width is not an exact multiple of the pen, which guarantees gaps ≤ pen.

Concentric contours handle junctions and curves cleanly because the union has no overlaps. The alternative, parallel `offset_curve` per edge, overlaps and leaves spikes at every intersection. The accumulated higher-rank area is also subtracted from the hatch areas (D5).

### D5: Hatching
`hatch(polygon, spacing, angle)` rotates the polygon by `-angle` around its centroid. It intersects it with horizontal lines at `spacing` intervals across its bounds, then rotates the resulting segments back. Holes are handled by the shapely intersection. Water uses 45° and parks use −45°. The area hatched is `(polys ∩ page) − all road areas − text knockout`. The spacing defaults to the pen width, which gives solid coverage. Values below the pen width are rejected in CLI validation.

### D6: Single-stroke text via `Hershey-Fonts`
We use the `Hershey-Fonts` PyPI package (pure Python, no native dependencies). It returns line segments per glyph, and we chain the segments into polylines. The city name uses `futuram` (double-stroke, bolder). All other text uses `futural`. The font size in mm comes from the same base pt sizes and `scale_factor` as the raster layout (60 / 22 / 14 / 8 pt × 25.4/72). The text is placed at the same axes-fraction anchors, converted to page mm, and centred or right-aligned by measuring the rendered width.
- Glyph coverage: Hershey covers ASCII. Before rendering, we run NFKD decomposition and drop combining marks (`Zürich` → `ZURICH`). `°` and `©` are drawn as synthesised glyphs: a small circle, and a circle with a `c`. Any other unsupported code point is skipped, with one warning per string (per the spec).
- Knockout: the text knockout is the union of each rendered line's bounding box, padded by `max(2 mm, 3 × pen)`. That union is subtracted from all map geometry (roads and hatches).
*Alternative:* outline TTF glyphs. Rejected by the user, because outlines draw hollow letters.

### D7: SVG writer and layers
The writer is a hand-rolled `xml.etree.ElementTree`, with no new dependency. The root has `width="{W}mm" height="{H}mm" viewBox="0 0 W H"` plus the `inkscape` namespace. Paths are bucketed by lower-cased theme colour hex. Each bucket becomes `<g inkscape:groupmode="layer" id="layer{n}" inkscape:label="{n} {hex} {keys}" stroke="{hex}" fill="none" stroke-width="{pen}" stroke-linecap="round" stroke-linejoin="round">` with one `<path d="M… L…">` per polyline. Coordinates are rounded to 0.001 mm. Layer order is area hatches, then roads from low to high rank, then text. A plotter with pen swaps then draws light fills first. Inside a layer, polylines get greedy nearest-endpoint ordering, reversing a polyline when that helps, to cut pen-up travel.

### D8: CLI
The `--format` choices gain `plotter`. New args: `--pen-width` (float, default 0.3), `--width-mm` and `--height-mm` (float, optional), `--hatch-spacing` (float, default = pen width). Validation runs in `__main__` before any fetching: values must be > 0, and hatch spacing must be ≥ pen width. A failure prints an error and calls `sys.exit(1)`. When the mm size is omitted, it is derived from the (already clamped) inch values. When it is given, the inch values passed to `create_poster` are recomputed from it, so that `compensated_dist` and the fetch radius follow the mm aspect ratio. `generate_output_filename` maps `plotter` → `.svg`.

### D9: Tests
Add `pytest` to `requirements.txt` and create `test/test_plotter_svg.py` with synthetic shapely inputs and no network. The tests cover the stroke count and coverage for a straight wide road, a single stroke for a thin road, knockout of a higher class, hatch spacing and hole handling, the mm transform and page bounds, SVG root attributes, layer grouping, the absence of forbidden elements, and text fallback warnings.

## Risks / Trade-offs

- [Big radius (e.g. 18 km) → `unary_union` of tens of thousands of buffers is slow] → Buffer and union per class with shapely 2's vectorised `buffer` and `union_all`. Simplify centerlines with a tolerance of `pen/4` in metres before buffering. Print progress with tqdm as the existing code does.
- [Thin default road widths (≤0.42 mm) mean most roads are single strokes at a 0.3 mm pen] → This matches the raster look. If users want bolder roads, a `--road-scale` multiplier can be added later without changing this design.
- [Concentric contours can leave small slivers or tiny rings at junction corners] → Drop rings shorter than `2 × pen` in mm.
- [Hershey lacks non-Latin scripts] → Handled by the spec'd warning-and-skip. Users can pass `--display-city` with a Latin transliteration.
- [The `Hershey-Fonts` package is small and not heavily maintained] → The API surface we use is tiny (load the font, get line segments). If needed, the font data can be vendored into `fonts/` later.
- [Plot time: dense hatching of large water bodies can take a long time to draw] → `--hatch-spacing` lets users thin it out. The README documents this.

## Migration Plan

This change is purely additive. Existing formats and defaults are untouched, and rolling back means removing the `plotter` choice. The Docker image needs `plotter_svg.py` copied in and the updated `requirements.txt`.

## Open Questions

- The exact hatch angles and knockout padding values may be tuned after the first real plots. They are constants, not part of the CLI.
