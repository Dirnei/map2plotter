"""Unit tests for plotter_svg (no network access required)."""

import math
import random
import xml.etree.ElementTree as ET

import geopandas as gpd
import numpy as np
import pytest
from shapely.geometry import LineString, MultiLineString, Point, Polygon, box

import plotter_svg as ps

SVG = "{http://www.w3.org/2000/svg}"
INK = "{http://www.inkscape.org/namespaces/inkscape}"

THEME = {
    "bg": "#F5EDE4",
    "text": "#8B4513",
    "gradient_color": "#F5EDE4",
    "water": "#A8C4C4",
    "parks": "#E8E0D0",
    "road_motorway": "#A0522D",
    "road_primary": "#B8653A",
    "road_secondary": "#C9846A",
    "road_tertiary": "#D9A08A",
    "road_residential": "#E5C4B0",
    "road_default": "#D9A08A",
}

TEXTS = {
    "city": ("P  A  R  I  S", 60),
    "country": ("FRANCE", 22),
    "coords": ("48.8566° N / 2.3522° E", 14),
    "attribution": ("© OpenStreetMap contributors", 8),
}


def all_points(polylines):
    return [pt for p in polylines for pt in p]


def test_module_imports():
    settings = ps.PlotterSettings(300, 400, 0.3, 0.3)
    assert settings.width_mm == 300


# --- 2.1 page transform -----------------------------------------------------


def test_page_transform_maps_corners_with_y_flip():
    xlim, ylim = (1000, 1300), (5000, 5400)
    line = LineString([(1000, 5400), (1300, 5000)])
    out = ps.page_transform(line, xlim, ylim, 300)
    (x0, y0), (x1, y1) = out.coords
    assert (x0, y0) == pytest.approx((0, 0))
    assert (x1, y1) == pytest.approx((300, 400))


# --- 2.2 hatch --------------------------------------------------------------


def test_hatch_lines_inside_polygon_and_spaced():
    square = box(0, 0, 10, 10)
    lines = ps.hatch(square, 1.0, 0)
    assert lines
    for p in lines:
        assert square.buffer(1e-9).contains(LineString(p))
    ys = sorted({round(p[0][1], 6) for p in lines})
    assert np.allclose(np.diff(ys), 1.0)


def test_hatch_angled_spacing():
    lines = ps.hatch(box(0, 0, 20, 20), 1.5, 45)
    # Perpendicular distance between adjacent parallel lines equals spacing
    offsets = sorted({round((p[0][1] - p[0][0]) / math.sqrt(2), 6) for p in lines})
    assert np.allclose(np.diff(offsets), 1.5)


def test_hatch_skips_holes():
    donut = Polygon(box(0, 0, 10, 10).exterior.coords, [box(3, 3, 7, 7).exterior.coords])
    hole = box(3.01, 3.01, 6.99, 6.99)
    for p in ps.hatch(donut, 0.5, 30):
        assert not hole.intersects(LineString(p))


# --- 2.3 / 2.4 road strokes -------------------------------------------------


def test_wide_road_fully_covered():
    pen, width = 0.3, 1.2
    center = LineString([(0, 5), (50, 5)])
    area = center.buffer(width / 2)
    strokes = ps.fill_area(area, pen, center)
    ink = MultiLineString(strokes)
    assert len(strokes) > 1
    for x in np.linspace(5, 45, 9):
        for y in np.linspace(5 - width / 2, 5 + width / 2, 25):
            assert ink.distance(Point(x, y)) <= pen / 2 + 1e-6


def test_thin_road_is_single_centerline():
    pen = 0.3
    line = LineString([(0, 0), (30, 0), (30, 20)])
    strokes, _ = ps.render_roads(
        {"road_residential": MultiLineString([line])}, pen, box(-10, -10, 100, 100), Polygon(), 150, 150
    )
    assert ps.road_width_mm("road_residential", 150, 150) <= pen
    assert len(strokes["road_residential"]) == 1
    assert LineString(strokes["road_residential"][0]).equals(line)


def test_thicker_pen_uses_fewer_strokes():
    center = LineString([(0, 5), (50, 5)])
    area = center.buffer(0.6)
    assert len(ps.fill_area(area, 0.6, center)) < len(ps.fill_area(area, 0.3, center))


# --- 2.5 ordering -----------------------------------------------------------


def test_ordering_reduces_travel():
    rng = random.Random(1)
    polys = []
    for _ in range(200):
        x, y = rng.uniform(0, 100), rng.uniform(0, 100)
        polys.append([(x, y), (x + rng.uniform(-2, 2), y + rng.uniform(-2, 2))])
    ordered = ps.order_polylines(polys)
    assert len(ordered) == len(polys)
    assert ps.travel_distance(ordered) <= ps.travel_distance(polys)


# --- 3.x roads, areas -------------------------------------------------------


def test_road_width_scaling():
    assert ps.road_width_mm("road_motorway", 304.8, 406.4) == pytest.approx(1.2 * 25.4 / 72)
    assert ps.road_width_mm("road_motorway", 609.6, 812.8) == pytest.approx(2 * 1.2 * 25.4 / 72)


def test_classify_highway():
    assert ps.classify_highway("motorway_link") == "road_motorway"
    assert ps.classify_highway(["trunk", "primary"]) == "road_primary"
    assert ps.classify_highway("living_street") == "road_residential"
    assert ps.classify_highway("footway") == "road_default"


def test_higher_class_knocks_out_lower():
    pen = 0.3
    primary = LineString([(0, 50), (100, 50)])
    residential = LineString([(50, 0), (50, 100)])
    size = 1000  # large poster so the primary road is several strokes wide
    strokes, _ = ps.render_roads(
        {"road_primary": MultiLineString([primary]), "road_residential": MultiLineString([residential])},
        pen, box(0, 0, 100, 100), Polygon(), size, size,
    )
    w = ps.road_width_mm("road_primary", size, size)
    primary_area = primary.buffer(w / 2 - 1e-6)
    for p in strokes["road_residential"]:
        assert not LineString(p).intersects(primary_area)
    assert len(strokes["road_primary"]) > 1


def test_road_not_hatched_over():
    park = box(0, 0, 50, 50)
    road = LineString([(0, 25), (50, 25)]).buffer(1)
    lines = ps.render_areas(park, 0.3, -45, road, box(0, 0, 100, 100))
    assert lines
    inner = LineString([(0, 25), (50, 25)]).buffer(0.99)
    for p in lines:
        assert not LineString(p).intersects(inner)


# --- 4.x typography ---------------------------------------------------------


def test_text_centered():
    _, (x0, x1) = ps.text_polylines("PARIS", "futuram", 60, 150, 300, "center")
    assert (x0 + x1) / 2 == pytest.approx(150, abs=0.01)


def test_text_right_aligned():
    _, (x0, x1) = ps.text_polylines("ABC", "futural", 8, 290, 390, "right")
    assert x1 == pytest.approx(290, abs=0.01)


def test_accents_and_symbols_render(capsys):
    lines, _ = ps.text_polylines("Zürich", "futural", 22, 0, 0, "left")
    assert ps.prepare_text("Zürich", "futural") == ("Zurich", [])
    assert lines
    copyright_lines, _ = ps.text_polylines("©", "futural", 8, 0, 0, "left")
    assert copyright_lines
    assert "⚠" not in capsys.readouterr().out


def test_unsupported_glyphs_warn(capsys):
    lines, _ = ps.text_polylines("東京 Tokyo", "futural", 22, 0, 0, "left")
    assert lines  # Latin part still drawn
    assert "⚠" in capsys.readouterr().out
    ps.text_polylines("東京", "futural", 22, 0, 0, "left")  # nothing drawable, must not raise


def test_layout_knockout_contains_text():
    lines, knockout = ps.layout_text(TEXTS, 300, 400, 0.3)
    assert lines
    for p in lines:
        assert knockout.contains(LineString(p))


# --- 5.x SVG ----------------------------------------------------------------


def _parse(path):
    return ET.parse(path).getroot()


def test_write_svg_structure(tmp_path):
    settings = ps.PlotterSettings(300, 400, 0.5, 0.5)
    entries = [
        ("road_tertiary", "#D9A08A", [[(0, 0), (10, 10)]]),
        ("road_default", "#d9a08a", [[(5, 5), (6, 6)]]),
        ("text", "#8B4513", [[(1, 1), (2, 2), (3, 1)]]),
    ]
    out = tmp_path / "t.svg"
    ps.write_svg(out, ps.build_layers(entries), settings)
    root = _parse(out)
    assert root.get("width") == "300mm"
    assert root.get("height") == "400mm"
    assert root.get("viewBox") == "0 0 300 400"
    layers = root.findall(f"{SVG}g")
    assert len(layers) == 2  # shared colour merged
    assert "road_tertiary,road_default" in layers[0].get(f"{INK}label")
    for g in layers:
        assert g.get(f"{INK}groupmode") == "layer"
        assert g.get("stroke-width") == "0.5"
        assert g.get("fill") == "none"


def test_fractional_mm_size_formatting(tmp_path):
    settings = ps.PlotterSettings(304.8, 406.4, 0.3, 0.3)
    out = tmp_path / "t.svg"
    ps.write_svg(out, [], settings)
    root = _parse(out)
    assert root.get("width") == "304.8mm"
    assert root.get("height") == "406.4mm"


def _synthetic_inputs():
    crs = "EPSG:32631"
    x0, y0 = 500000, 5000000
    roads = gpd.GeoDataFrame(
        {
            "highway": ["motorway", "primary", "residential", "residential", "footway"],
            "geometry": [
                LineString([(x0 - 2000, y0), (x0 + 2000, y0)]),
                LineString([(x0, y0 - 2000), (x0, y0 + 2000)]),
                LineString([(x0 - 900, y0 - 900), (x0 + 900, y0 + 900)]),
                LineString([(x0 + 900, y0 - 900), (x0 - 900, y0 + 900)]),
                LineString([(x0 - 500, y0 + 300), (x0 + 500, y0 + 300)]),
            ],
        },
        crs=crs,
    )
    water = gpd.GeoDataFrame(
        {"geometry": [box(x0 - 800, y0 + 200, x0 - 200, y0 + 700), Point(x0, y0)]}, crs=crs
    ).to_crs("EPSG:4326")
    parks = gpd.GeoDataFrame({"geometry": [box(x0 + 200, y0 - 700, x0 + 800, y0 - 200)]}, crs=crs)
    xlim, ylim = (x0 - 750, x0 + 750), (y0 - 1000, y0 + 1000)
    return roads, water, parks, xlim, ylim


def test_render_end_to_end(tmp_path):
    roads, water, parks, xlim, ylim = _synthetic_inputs()
    settings = ps.PlotterSettings(300, 400, 0.3, 0.3)
    out = tmp_path / "poster.svg"
    ps.render(out, roads, water, parks, xlim, ylim, THEME, TEXTS, settings)
    root = _parse(out)

    for tag in ("image", "text", "linearGradient", "radialGradient", "font", "rect", "circle"):
        assert root.find(f".//{SVG}{tag}") is None
    for el in root.iter():
        assert el.get("fill") in (None, "none")

    labels = [g.get(f"{INK}label") for g in root.findall(f"{SVG}g")]
    for key in ("water", "parks", "road_motorway", "road_primary", "road_residential", "text"):
        assert any(key in label for label in labels), key

    coords = []
    for path in root.iter(f"{SVG}path"):
        for token in path.get("d").replace("M", "").replace("L", "").split():
            x, y = map(float, token.split(","))
            coords.append((x, y))
    xs, ys = zip(*coords)
    assert min(xs) >= 0 and max(xs) <= 300
    assert min(ys) >= 0 and max(ys) <= 400


def test_render_text_block_free_of_map(tmp_path):
    roads, water, parks, xlim, ylim = _synthetic_inputs()
    settings = ps.PlotterSettings(300, 400, 0.3, 0.3)
    out = tmp_path / "poster.svg"
    ps.render(out, roads, water, parks, xlim, ylim, THEME, TEXTS, settings)
    _, knockout = ps.layout_text(TEXTS, 300, 400, 0.3)
    inner = knockout.buffer(-0.01)
    root = _parse(out)
    for g in root.findall(f"{SVG}g"):
        if "text" in g.get(f"{INK}label"):
            continue
        for path in g.iter(f"{SVG}path"):
            pts = [tuple(map(float, t.split(","))) for t in path.get("d").replace("M", "").replace("L", "").split()]
            assert not LineString(pts).intersects(inner)


def test_long_text_fits_page():
    texts = dict(TEXTS, city=("  ".join("KAPSTADTWESTKAP"), 60), attribution=("", 8))
    lines, _ = ps.layout_text(texts, 200, 250, 0.3)
    xs = [x for p in lines for x, _ in p]
    assert min(xs) >= 200 * 0.05 - 0.5 and max(xs) <= 200 * 0.95 + 0.5


# --- Fill modes, water outline, edits ----------------------------------------

import poster_edits  # noqa: E402


def test_concentric_rings_closed_inside_and_spaced():
    area = box(0, 0, 20, 10)
    rings = ps.concentric(area, 1.0, 0.3)
    assert len(rings) >= 4
    for ring in rings:
        assert ring[0] == ring[-1]
        assert area.buffer(1e-9).contains(LineString(ring))
    # First ring at half a pen width, next ones one spacing further in
    first, second = LineString(rings[0]), LineString(rings[1])
    assert first.distance(area.exterior) == pytest.approx(0.15, abs=1e-6)
    assert second.distance(first) == pytest.approx(1.0, abs=1e-6)


def test_concentric_follows_holes():
    area = box(0, 0, 20, 20).difference(box(8, 8, 12, 12))
    rings = ps.concentric(area, 1.0, 0.3)
    hole = box(8, 8, 12, 12)
    near_hole = [r for r in rings if LineString(r).distance(hole) == pytest.approx(0.15, abs=1e-2)]
    assert near_hole, "expected a contour around the hole"


def test_fill_area_unchanged_by_refactor():
    area = box(0, 0, 3, 1)
    rings = ps.fill_area(area, 0.3)
    assert rings == ps.concentric(area, 0.3, 0.3)


def test_render_areas_concentric_mode_and_spacing():
    area = box(10, 10, 60, 40)
    lines = ps.render_areas(area, 2.0, 45, Polygon(), box(0, 0, 100, 100), mode="concentric", pen=0.3)
    assert all(ln[0] == ln[-1] for ln in lines)  # closed contours, no straight hatch lines
    assert LineString(lines[1]).distance(LineString(lines[0])) == pytest.approx(2.0, abs=1e-6)


def test_render_areas_concentric_excludes_roads():
    area = box(10, 10, 60, 40)
    road = box(30, 0, 32, 100)
    lines = ps.render_areas(area, 1.0, 45, road, box(0, 0, 100, 100), mode="concentric", pen=0.3)
    inner = road.buffer(-1e-6)
    assert lines and not any(LineString(ln).intersects(inner) for ln in lines if len(ln) >= 2)


def test_per_area_spacing_settings():
    s = ps.PlotterSettings(300, 400, 0.3, 0.5, water_spacing=0.6)
    assert s.spacing("water") == 0.6 and s.spacing("parks") == 0.5
    assert s.fill_mode("water") == "hatch"


def test_water_outline_includes_island():
    lake = box(10, 10, 60, 60).difference(box(30, 30, 40, 40))
    lines = ps.render_areas(lake, 1.0, 45, Polygon(), box(0, 0, 100, 100), pen=0.3, outline=True)
    outer = [ln for ln in lines if LineString(ln).equals(box(10, 10, 60, 60).exterior)]
    island = [ln for ln in lines if LineString(ln).equals(box(30, 30, 40, 40).exterior)]
    assert outer and island
    # Fill keeps one spacing away from the outline
    fill = [ln for ln in lines if ln not in outer + island]
    assert min(LineString(ln).distance(lake.boundary) for ln in fill) >= 1.0 - 1e-2


def test_water_outline_not_through_roads():
    lake = box(10, 10, 60, 60)
    bridge = box(30, 0, 33, 100)
    lines = ps.render_areas(lake, 1.0, 45, bridge, box(0, 0, 100, 100), pen=0.3, outline=True)
    inner = bridge.buffer(-1e-6)
    assert not any(LineString(ln).intersects(inner) for ln in lines)


def test_no_outline_by_default():
    lake = box(10, 10, 60, 60)
    lines = ps.render_areas(lake, 1.0, 45, Polygon(), box(0, 0, 100, 100), pen=0.3)
    assert not any(LineString(ln).equals(lake.exterior) for ln in lines)


def _paths_by_label(root):
    out = {}
    for g in root.findall(f"{SVG}g"):
        pts = []
        for path in g.iter(f"{SVG}path"):
            tokens = path.get("d").replace("M", "").replace("L", "").split()
            pts.append([tuple(map(float, t.split(","))) for t in tokens])
        out[g.get(f"{INK}label")] = pts
    return out


def test_render_erase_region(tmp_path):
    roads, water, parks, xlim, ylim = _synthetic_inputs()
    settings = ps.PlotterSettings(300, 400, 0.3, 0.3)
    region = box(20, 20, 280, 300)
    edits = poster_edits.parse_edits({"erase": [[list(p) for p in region.exterior.coords[:-1]]]})
    out = tmp_path / "poster.svg"
    ps.render(out, roads, water, parks, xlim, ylim, THEME, TEXTS, settings, edits)
    inner = region.buffer(-0.01)
    layers = _paths_by_label(_parse(out))
    text_layer = [paths for label, paths in layers.items() if "text" in label][0]
    assert text_layer, "text must not be erased"
    for label, paths in layers.items():
        if "text" in label:
            continue
        for pts in paths:
            assert not LineString(pts).intersects(inner), label


def test_render_hidden_parks_layer(tmp_path):
    roads, water, parks, xlim, ylim = _synthetic_inputs()
    settings = ps.PlotterSettings(300, 400, 0.3, 0.3)
    edits = poster_edits.parse_edits({"hidden_layers": ["parks"]})
    out = tmp_path / "poster.svg"
    ps.render(out, roads, water, parks, xlim, ylim, THEME, TEXTS, settings, edits)
    labels = [g.get(f"{INK}label") for g in _parse(out).findall(f"{SVG}g")]
    assert not any("parks" in label for label in labels)
    assert any("water" in label for label in labels)


def test_text_offset_moves_city():
    base, _ = ps._layout(TEXTS, 300, 400, 0.3)
    edits = poster_edits.parse_edits({"text": {"city": {"dy": -10, "dx": 5}}})
    moved_lines, moved_boxes = ps._layout(TEXTS, 300, 400, 0.3, edits)
    _, base_boxes = ps._layout(TEXTS, 300, 400, 0.3)
    bx, by = base_boxes["city"].bounds[:2]
    mx, my = moved_boxes["city"].bounds[:2]
    assert mx - bx == pytest.approx(5) and my - by == pytest.approx(-10)
    assert moved_boxes["country"].equals(base_boxes["country"])


def test_hidden_coords_keeps_attribution():
    edits = poster_edits.parse_edits({"text": {"coords": {"hidden": True}}})
    _, boxes = ps._layout(TEXTS, 300, 400, 0.3, edits)
    assert "coords" not in boxes and "attribution" in boxes
    _, knockout = ps.layout_text(TEXTS, 300, 400, 0.3, edits)
    _, full = ps.layout_text(TEXTS, 300, 400, 0.3)
    assert knockout.area < full.area


def test_text_boxes_default_positions():
    boxes = ps.text_boxes(TEXTS, 300, 400)
    assert set(boxes) >= {"city", "country", "coords", "divider", "attribution"}
    minx, miny, maxx, maxy = boxes["city"]
    assert minx < 150 < maxx and miny < 400 * (1 - ps.CITY_Y) < maxy
