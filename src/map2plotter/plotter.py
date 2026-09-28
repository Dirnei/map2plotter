"""
Plotter SVG Output

Turns projected map geometry into a pen-plotter-ready SVG: stroked paths only,
sized in millimetres, with wide roads filled by parallel pen strokes, areas
hatch-filled, single-stroke (Hershey) text, and one Inkscape layer per colour.
"""

import math
import unicodedata
import xml.etree.ElementTree as ET
from dataclasses import dataclass

import numpy as np
import shapely
from HersheyFonts import HersheyFonts
from scipy.spatial import cKDTree
from shapely import affinity
from shapely.geometry import LineString, MultiLineString, Polygon, box
from shapely.ops import linemerge, unary_union

MM_PER_PT = 25.4 / 72  # Typographic point
REFERENCE_SIZE_MM = 304.8  # Shorter poster side at which the base font sizes and road widths apply

WATER_HATCH_ANGLE = 45
PARKS_HATCH_ANGLE = -45

# Road classes from highest to lowest rank: (theme key, highway types, width in pt at reference size)
ROAD_CLASSES = [
    ("road_motorway", {"motorway", "motorway_link"}, 1.2),
    ("road_primary", {"trunk", "trunk_link", "primary", "primary_link"}, 1.0),
    ("road_secondary", {"secondary", "secondary_link"}, 0.8),
    ("road_tertiary", {"tertiary", "tertiary_link"}, 0.6),
    ("road_residential", {"residential", "living_street", "unclassified"}, 0.4),
    ("road_default", None, 0.4),
]

# Text anchors as fractions of the page (x, y measured from the bottom)
CITY_Y = 0.14
COUNTRY_Y = 0.10
COORDS_Y = 0.07
DIVIDER_Y = 0.125
DIVIDER_X = (0.4, 0.6)
ATTRIBUTION_POS = (0.98, 0.02)

# Base font sizes in points (at the reference size REFERENCE_SIZE_MM)
BASE_MAIN = 60
BASE_SUB = 22
BASE_COORDS = 14
BASE_ATTR = 8


def is_latin_script(text):
    """
    Check if text is primarily Latin script.
    Used to determine if letter-spacing should be applied to city names.

    :param text: Text to analyze
    :return: True if text is primarily Latin script, False otherwise
    """
    if not text:
        return True

    latin_count = 0
    total_alpha = 0

    for char in text:
        if char.isalpha():
            total_alpha += 1
            # Latin Unicode ranges:
            # - Basic Latin: U+0000 to U+007F
            # - Latin-1 Supplement: U+0080 to U+00FF
            # - Latin Extended-A: U+0100 to U+017F
            # - Latin Extended-B: U+0180 to U+024F
            if ord(char) < 0x250:
                latin_count += 1

    # If no alphabetic characters, default to Latin (numbers, symbols, etc.)
    if total_alpha == 0:
        return True

    # Consider it Latin if >80% of alphabetic characters are Latin
    return (latin_count / total_alpha) > 0.8


def format_city_title(display_city, scale_factor):
    """
    Format the city name and pick its font size.

    Latin scripts are uppercased with letter spacing (e.g. "P  A  R  I  S");
    other scripts are kept as-is. Long names get a smaller font to avoid truncation.

    Returns:
        (formatted city text, font size in points)
    """
    if is_latin_script(display_city):
        spaced_city = "  ".join(list(display_city.upper()))
    else:
        spaced_city = display_city

    base_adjusted_main = BASE_MAIN * scale_factor
    city_char_count = len(display_city)

    # Heuristic: If length is > 10, start reducing.
    if city_char_count > 10:
        length_factor = 10 / city_char_count
        adjusted_font_size = max(base_adjusted_main * length_factor, 10 * scale_factor)
    else:
        adjusted_font_size = base_adjusted_main

    return spaced_city, adjusted_font_size


def format_coordinates(lat, lon):
    """Format a lat/lon pair for display, e.g. '48.8566° N / 2.3522° E'."""
    coords = (
        f"{lat:.4f}° N / {lon:.4f}° E"
        if lat >= 0
        else f"{abs(lat):.4f}° S / {lon:.4f}° E"
    )
    if lon < 0:
        coords = coords.replace("E", "W")
    return coords


def poster_texts(display_city, display_country, lat, lon, width_mm, height_mm):
    """The poster's text lines as {key: (text, size_pt)}, scaled to the page size."""
    scale_factor = min(width_mm, height_mm) / REFERENCE_SIZE_MM
    spaced_city, city_size = format_city_title(display_city, scale_factor)
    return {
        "city": (spaced_city, city_size),
        "country": (display_country.upper(), BASE_SUB * scale_factor),
        "coords": (format_coordinates(lat, lon), BASE_COORDS * scale_factor),
        "attribution": ("© OpenStreetMap contributors", BASE_ATTR),
    }


# Hershey font metrics (font units, y pointing down)
HERSHEY_CAP = -12
HERSHEY_BASE = 9
HERSHEY_BOTTOM = 16
CAP_HEIGHT_PER_EM = 0.7
# Hershey's space is ~0.5 em; use a TTF-like word space so letter-spaced titles keep their width
SPACE_ADVANCE = 8
MAX_TEXT_WIDTH = 0.9  # Fraction of the page width a text line may use

INKSCAPE_NS = "http://www.inkscape.org/namespaces/inkscape"
SVG_NS = "http://www.w3.org/2000/svg"


FILL_MODES = ("hatch", "concentric")


@dataclass
class PlotterSettings:
    """Physical output parameters for the plotter SVG (all values in mm)."""

    width_mm: float
    height_mm: float
    pen_width: float
    hatch_spacing: float
    water_fill: str = "hatch"
    parks_fill: str = "hatch"
    water_spacing: float | None = None  # Defaults to hatch_spacing
    parks_spacing: float | None = None  # Defaults to hatch_spacing
    water_outline: bool = False

    def fill_mode(self, kind):
        """Fill mode ('hatch' or 'concentric') for 'water' or 'parks'."""
        return getattr(self, f"{kind}_fill")

    def spacing(self, kind):
        """Line spacing in mm for 'water' or 'parks'."""
        value = getattr(self, f"{kind}_spacing")
        return self.hatch_spacing if value is None else value


# ---------------------------------------------------------------------------
# Geometry helpers
# ---------------------------------------------------------------------------


def page_transform(geom, xlim, ylim, width_mm):
    """
    Map geometry from projected metres to page millimetres (y flipped for SVG).

    Args:
        geom: Shapely geometry (or GeoSeries) in projected metres
        xlim: (xmin, xmax) crop limits in metres
        ylim: (ymin, ymax) crop limits in metres
        width_mm: Page width in mm

    Returns:
        Geometry in page millimetres
    """
    s = width_mm / (xlim[1] - xlim[0])
    matrix = [s, 0, 0, -s, -xlim[0] * s, ylim[1] * s]
    if hasattr(geom, "affine_transform"):
        return geom.affine_transform(matrix)
    return affinity.affine_transform(geom, matrix)


def to_polylines(geom):
    """
    Flatten any shapely geometry into a list of coordinate lists.

    Polygons contribute their exterior and interior rings.
    """
    if geom is None or geom.is_empty:
        return []
    if isinstance(geom, LineString):
        return [list(geom.coords)]
    if isinstance(geom, Polygon):
        return [list(geom.exterior.coords)] + [list(r.coords) for r in geom.interiors]
    if hasattr(geom, "geoms"):
        out = []
        for part in geom.geoms:
            out.extend(to_polylines(part))
        return out
    return []


def polyline_length(polyline):
    """Return the length of a coordinate list."""
    pts = np.asarray(polyline)
    if len(pts) < 2:
        return 0.0
    return float(np.hypot(*np.diff(pts, axis=0).T).sum())


def hatch(geom, spacing, angle):
    """
    Fill a (multi)polygon with parallel lines.

    Lines are aligned to a global grid so neighbouring polygons hatch seamlessly.

    Args:
        geom: Polygon or MultiPolygon to fill
        spacing: Distance between adjacent lines
        angle: Line angle in degrees

    Returns:
        List of polylines clipped to the polygon (holes excluded)
    """
    if geom is None or geom.is_empty:
        return []
    rotated = affinity.rotate(geom, -angle, origin=(0, 0))
    minx, miny, maxx, maxy = rotated.bounds
    start = math.ceil(miny / spacing) * spacing
    ys = np.arange(start, maxy, spacing)
    if len(ys) == 0:
        return []
    lines = MultiLineString([[(minx - 1, y), (maxx + 1, y)] for y in ys])
    clipped = rotated.intersection(lines)
    return to_polylines(affinity.rotate(clipped, angle, origin=(0, 0)))


def concentric(area, spacing, pen, start=None):
    """
    Fill an area with closed contours that follow its outline and holes.

    Args:
        area: Polygon/MultiPolygon to fill
        spacing: Distance between adjacent contours
        pen: Pen width; contours shorter than two pen widths are dropped
        start: Inset of the first contour (default: half a pen width)

    Returns:
        List of polylines
    """
    out = []
    inset = area.buffer(-(pen / 2 if start is None else start))
    while not inset.is_empty:
        out.extend(p for p in to_polylines(inset) if polyline_length(p) >= 2 * pen)
        inset = inset.buffer(-spacing)
    return out


def fill_area(area, pen, centerlines=None):
    """
    Cover an area with pen strokes: concentric inset contours spaced one pen
    width apart, plus the centerlines to close the remaining core.

    Args:
        area: Polygon/MultiPolygon to cover
        pen: Pen width
        centerlines: Optional line geometry to add, clipped to the area

    Returns:
        List of polylines
    """
    out = concentric(area, pen, pen)
    if centerlines is not None and not centerlines.is_empty:
        out.extend(to_polylines(merge_lines(centerlines.intersection(area))))
    return out


def merge_lines(geom):
    """Dissolve duplicate/overlapping linework and merge it into continuous lines."""
    lines = to_shapely_lines(geom)
    if not lines:
        return MultiLineString()
    return linemerge(to_shapely_lines(unary_union(lines)))


def order_polylines(polylines):
    """
    Greedy nearest-endpoint ordering to reduce pen-up travel. Polylines are
    reversed when their end point is closer than their start point.
    """
    n = len(polylines)
    if n < 2:
        return list(polylines)
    starts = np.array([p[0] for p in polylines], dtype=float)
    ends = np.array([p[-1] for p in polylines], dtype=float)
    tree = cKDTree(np.vstack([starts, ends]))
    visited = np.zeros(n, dtype=bool)

    ordered = []
    idx, reverse = 0, False
    for _ in range(n):
        visited[idx] = True
        poly = polylines[idx][::-1] if reverse else polylines[idx]
        ordered.append(poly)
        if len(ordered) == n:
            break
        pos = poly[-1]
        k = 16
        while True:
            k_eff = min(k, 2 * n)
            _, hits = tree.query(pos, k=k_eff)
            hits = np.atleast_1d(hits)
            candidates = [h for h in hits if h < 2 * n and not visited[h % n]]
            if candidates:
                hit = candidates[0]
                idx, reverse = hit % n, hit >= n
                break
            if k_eff >= 2 * n:
                raise RuntimeError("No unvisited polyline found")  # pragma: no cover
            k *= 4
    return ordered


def travel_distance(polylines):
    """Total pen-up travel between consecutive polylines."""
    return sum(
        math.dist(a[-1], b[0]) for a, b in zip(polylines, polylines[1:])
    )


# ---------------------------------------------------------------------------
# Roads and areas
# ---------------------------------------------------------------------------


def classify_highway(highway):
    """Return the theme key of the road class for an OSM highway value."""
    if isinstance(highway, list):
        highway = highway[0] if highway else "unclassified"
    for key, types, _ in ROAD_CLASSES:
        if types is not None and highway in types:
            return key
    return "road_default"


def road_width_mm(key, width_mm, height_mm):
    """Target ink width in mm for a road class, scaled with the poster size."""
    width_pt = next(w for k, _, w in ROAD_CLASSES if k == key)
    return width_pt * MM_PER_PT * min(width_mm, height_mm) / REFERENCE_SIZE_MM


def render_roads(roads_by_class, pen, page, knockout, width_mm, height_mm):
    """
    Turn road centerlines (in mm) into pen strokes, highest class first.
    Each class is knocked out of every class below it.

    Args:
        roads_by_class: {theme key: line geometry in mm}
        pen: Pen width in mm
        page: Page polygon in mm
        knockout: Area (mm) to keep free of roads, e.g. the text block
        width_mm, height_mm: Page size

    Returns:
        ({theme key: polylines}, union of all road ink areas)
    """
    strokes = {}
    covered = knockout
    ink_areas = []
    for key, _, _ in ROAD_CLASSES:
        lines = roads_by_class.get(key)
        if lines is None or lines.is_empty:
            continue
        w = road_width_mm(key, width_mm, height_mm)
        lines = lines.simplify(pen / 4)
        ink = _buffer_union(lines, max(w, pen) / 2).intersection(page)
        visible = ink.difference(covered)
        if w <= pen:
            strokes[key] = to_polylines(merge_lines(lines.intersection(visible)))
        else:
            area = _buffer_union(lines, w / 2).intersection(visible)
            strokes[key] = fill_area(area, pen, lines)
        covered = covered.union(ink)
        ink_areas.append(ink)
    return strokes, unary_union(ink_areas) if ink_areas else Polygon()


def to_shapely_lines(geom):
    """Return a list of LineStrings for any line geometry."""
    return [LineString(p) for p in to_polylines(geom) if len(p) >= 2]


def _buffer_union(lines, radius):
    """Buffer each line with round caps/joins and dissolve the result."""
    return shapely.union_all(shapely.buffer(to_shapely_lines(lines), radius, quad_segs=4))


def _clip_lines(polylines, exclude):
    """Remove the parts of polylines that lie inside the excluded area."""
    lines = to_shapely_lines(MultiLineString(polylines)) if polylines else []
    if not lines or exclude is None or exclude.is_empty:
        return [list(ln.coords) for ln in lines]
    return to_polylines(shapely.difference(MultiLineString(lines), exclude))


def render_areas(polygons, spacing, angle, exclude, page, mode="hatch", pen=None, outline=False):
    """
    Fill polygons (mm) inside the page, leaving out the excluded area.

    Args:
        polygons: Area geometry in page mm (or None)
        spacing: Distance between fill lines
        angle: Hatch angle in degrees (hatch mode)
        exclude: Area to keep free (roads, text, erase regions)
        page: Page polygon
        mode: 'hatch' (parallel lines) or 'concentric' (inset contours)
        pen: Pen width (defaults to the spacing)
        outline: Also stroke the area boundary; the fill then keeps one spacing away from it

    Returns:
        List of polylines
    """
    if polygons is None or polygons.is_empty:
        return []
    pen = spacing if pen is None else pen
    area = polygons.intersection(page)
    out = []
    if outline:
        out.extend(_clip_lines(to_polylines(area.boundary), exclude))
    if mode == "concentric":
        area = area.simplify(pen / 4)
        rings = concentric(area, spacing, pen, start=spacing if outline else None)
        out.extend(p for p in _clip_lines(rings, exclude) if len(p) >= 2)
    else:
        fill = area.buffer(-spacing) if outline else area
        out.extend(hatch(fill.difference(exclude), spacing, angle))
    return out


# ---------------------------------------------------------------------------
# Typography
# ---------------------------------------------------------------------------

_FONTS = {}


def _font(name):
    """Load and cache a Hershey font by name."""
    if name not in _FONTS:
        font = HersheyFonts()
        font.load_default_font(name)
        _FONTS[name] = font
    return _FONTS[name]


def _circle(cx, cy, r, start=0.0, end=360.0, segments=32):
    steps = max(4, int(segments * (end - start) / 360))
    return [
        (cx + r * math.cos(math.radians(a)), cy + r * math.sin(math.radians(a)))
        for a in np.linspace(start, end, steps + 1)
    ]


# Synthesised glyphs for characters Hershey lacks: (left offset, advance, strokes)
SYNTHETIC_GLYPHS = {
    "°": (-5, 10, [_circle(0, -9, 3)]),
    "©": (-13, 26, [_circle(0, -1.5, 11), _circle(0, -1.5, 5, 45, 315, 24)]),
}


def prepare_text(text, font_name):
    """
    Map text onto characters the stroke font can draw.

    Accented Latin characters are reduced to their base letter; characters that
    cannot be drawn are dropped.

    Returns:
        (drawable text, list of unsupported characters)
    """
    glyphs = _font(font_name).all_glyphs
    out, unsupported = [], []
    for ch in text:
        if ch in glyphs or ch in SYNTHETIC_GLYPHS:
            out.append(ch)
            continue
        base = "".join(
            c for c in unicodedata.normalize("NFKD", ch) if not unicodedata.combining(c)
        )
        if base and all(c in glyphs for c in base):
            out.append(base)
        else:
            unsupported.append(ch)
    return "".join(out), unsupported


def text_polylines(text, font_name, size_pt, x, baseline, align="center", warn=True):
    """
    Render text as stroked polylines in page mm.

    Args:
        text: Text to render
        font_name: Hershey font name (e.g. 'futural', 'futuram')
        size_pt: Font size in points (same scale as the raster layout)
        x: Anchor x in mm
        baseline: Baseline y in mm (SVG coordinates, y down)
        align: 'left', 'center' or 'right'
        warn: Print a warning for characters that cannot be drawn

    Returns:
        (polylines, (x0, x1)) where x0/x1 are the text's advance extents
    """
    drawable, unsupported = prepare_text(text, font_name)
    if unsupported and warn:
        print(f"⚠ Stroke font cannot draw {''.join(unsupported)!r} in {text!r}; skipping those characters")
    font = _font(font_name)
    scale = size_pt * MM_PER_PT * CAP_HEIGHT_PER_EM / (HERSHEY_BASE - HERSHEY_CAP)

    glyphs = []
    advance = 0.0
    for ch in drawable:
        if ch == " ":
            left, width, strokes = -SPACE_ADVANCE / 2, SPACE_ADVANCE, []
        elif ch in SYNTHETIC_GLYPHS:
            left, width, strokes = SYNTHETIC_GLYPHS[ch]
        else:
            g = font.all_glyphs[ch]
            left, width, strokes = g.left_offset, g.char_width, g.strokes
        glyphs.append((advance - left, strokes))
        advance += width
    total = advance * scale

    x0 = {"left": x, "center": x - total / 2, "right": x - total}[align]
    polylines = []
    for origin, strokes in glyphs:
        for stroke in strokes:
            pts = [
                (x0 + (origin + px) * scale, baseline + (py - HERSHEY_BASE) * scale)
                for px, py in stroke
            ]
            if len(pts) >= 2:
                polylines.append(pts)
    return polylines, (x0, x0 + total)


def text_box(extent, baseline, size_pt):
    """Bounding box (mm) of a text line from cap line to descender line."""
    scale = size_pt * MM_PER_PT * CAP_HEIGHT_PER_EM / (HERSHEY_BASE - HERSHEY_CAP)
    top = baseline + (HERSHEY_CAP - HERSHEY_BASE) * scale
    bottom = baseline + (HERSHEY_BOTTOM - HERSHEY_BASE) * scale
    return box(extent[0], top, extent[1], bottom)


def _layout(texts, width_mm, height_mm, pen, edits=None):
    """
    Place poster text as in the raster layout, applying text edits.

    Returns:
        (polylines, {key: bounding polygon in mm})
    """
    W, H = width_mm, height_mm
    polylines, boxes = [], {}

    def text_edit(key):
        return edits.text_edit(key) if edits is not None else None

    def place(key, font, x, y_frac, align="center", bottom_anchor=False):
        text, size = texts[key]
        edit = text_edit(key)
        if not text or (edit is not None and edit.hidden):
            return
        dx, dy = (edit.dx, edit.dy) if edit is not None else (0.0, 0.0)
        baseline = H * (1 - y_frac) + dy
        _, (x0, x1) = text_polylines(text, font, size, 0, 0, align, warn=False)
        if x1 - x0 > W * MAX_TEXT_WIDTH:
            size *= W * MAX_TEXT_WIDTH / (x1 - x0)
        if bottom_anchor:
            scale = size * MM_PER_PT * CAP_HEIGHT_PER_EM / (HERSHEY_BASE - HERSHEY_CAP)
            baseline -= (HERSHEY_BOTTOM - HERSHEY_BASE) * scale
        lines, extent = text_polylines(text, font, size, x + dx, baseline, align)
        polylines.extend(lines)
        boxes[key] = text_box(extent, baseline, size)

    place("city", "futuram", W / 2, CITY_Y)
    place("country", "futural", W / 2, COUNTRY_Y)
    place("coords", "futural", W / 2, COORDS_Y)
    place("attribution", "futural", W * ATTRIBUTION_POS[0], ATTRIBUTION_POS[1], "right", True)

    edit = text_edit("divider")
    if edit is None or not edit.hidden:
        dx, dy = (edit.dx, edit.dy) if edit is not None else (0.0, 0.0)
        y = H * (1 - DIVIDER_Y) + dy
        divider = [(W * DIVIDER_X[0] + dx, y), (W * DIVIDER_X[1] + dx, y)]
        polylines.append(divider)
        boxes["divider"] = LineString(divider).buffer(pen / 2)
    return polylines, boxes


def layout_text(texts, width_mm, height_mm, pen, edits=None):
    """
    Place poster text as in the raster layout.

    Args:
        texts: dict with keys 'city', 'country', 'coords', 'attribution',
               each a (text, size_pt) tuple
        width_mm, height_mm: Page size
        pen: Pen width in mm (sets knockout padding)
        edits: Optional poster_edits.Edits (text offsets and hidden lines)

    Returns:
        (polylines, knockout polygon)
    """
    polylines, boxes = _layout(texts, width_mm, height_mm, pen, edits)
    padding = max(2.0, 3 * pen)
    knockout = unary_union([b.buffer(padding, join_style="mitre") for b in boxes.values()])
    return polylines, knockout


def text_boxes(texts, width_mm, height_mm, pen=0.3):
    """Default bounding boxes (minx, miny, maxx, maxy in mm) of each text line, without edits."""
    _, boxes = _layout(texts, width_mm, height_mm, pen)
    return {key: b.bounds for key, b in boxes.items()}


# ---------------------------------------------------------------------------
# SVG output
# ---------------------------------------------------------------------------


def _fmt(value):
    """Format a number compactly with at most 3 decimals."""
    text = f"{value:.3f}".rstrip("0").rstrip(".")
    return "0" if text in ("-0", "") else text


def build_layers(entries):
    """
    Group polylines into one layer per colour, keeping first-appearance order.
    Inside a layer, each theme key keeps its own polylines.

    Args:
        entries: list of (theme key, colour hex, polylines)

    Returns:
        list of (colour, [(key, polylines), ...])
    """
    layers = {}
    for key, color, polylines in entries:
        if not polylines:
            continue
        groups = layers.setdefault(color.lower(), {})
        groups.setdefault(key, []).extend(polylines)
    return [(color, list(groups.items())) for color, groups in layers.items()]


def write_svg(output_file, layers, settings):
    """
    Write layers of polylines as a millimetre-scaled, stroke-only SVG.

    Each colour becomes an Inkscape layer (one pen); inside it, each element type
    (water, parks, a road class, text) gets its own group labelled with its key.

    Args:
        output_file: Destination path
        layers: list of (colour, [(key, polylines), ...]) from build_layers
        settings: PlotterSettings
    """
    ET.register_namespace("", SVG_NS)
    ET.register_namespace("inkscape", INKSCAPE_NS)
    W, H = _fmt(settings.width_mm), _fmt(settings.height_mm)
    root = ET.Element(f"{{{SVG_NS}}}svg", {
        "version": "1.1",
        "width": f"{W}mm",
        "height": f"{H}mm",
        "viewBox": f"0 0 {W} {H}",
    })
    for n, (color, groups) in enumerate(layers, start=1):
        layer = ET.SubElement(root, f"{{{SVG_NS}}}g", {
            "id": f"layer{n}",
            f"{{{INKSCAPE_NS}}}groupmode": "layer",
            f"{{{INKSCAPE_NS}}}label": f"{n} {color} {','.join(key for key, _ in groups)}",
            "fill": "none",
            "stroke": color,
            "stroke-width": _fmt(settings.pen_width),
            "stroke-linecap": "round",
            "stroke-linejoin": "round",
        })
        for key, polylines in groups:
            group = ET.SubElement(layer, f"{{{SVG_NS}}}g", {f"{{{INKSCAPE_NS}}}label": key, "data-key": key})
            for poly in order_polylines([p for p in polylines if len(p) >= 2]):
                points = " ".join(f"{_fmt(x)},{_fmt(y)}" for x, y in poly)
                first, rest = points.split(" ", 1)
                ET.SubElement(group, f"{{{SVG_NS}}}path", {"d": f"M{first} L{rest}"})
    tree = ET.ElementTree(root)
    ET.indent(tree)
    tree.write(output_file, encoding="utf-8", xml_declaration=True)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def _polygons_mm(gdf, crs, xlim, ylim, width_mm):
    """Reproject, crop and convert polygon features to a single mm geometry."""
    if gdf is None or gdf.empty:
        return None
    polys = gdf[gdf.geometry.type.isin(["Polygon", "MultiPolygon"])]
    if polys.empty:
        return None
    geoms = polys.geometry.to_crs(crs)
    geoms = shapely.clip_by_rect(geoms.values, xlim[0], ylim[0], xlim[1], ylim[1])
    geoms = [shapely.make_valid(page_transform(g, xlim, ylim, width_mm)) for g in geoms if not g.is_empty]
    return unary_union(geoms) if geoms else None


def render(output_file, edges, water, parks, xlim, ylim, theme, texts, settings, edits=None):
    """
    Render a plotter-ready SVG poster.

    Args:
        output_file: Destination .svg path
        edges: GeoDataFrame of projected road edges with 'geometry' and 'highway'
        water: GeoDataFrame of water features (any CRS) or None
        parks: GeoDataFrame of park features (any CRS) or None
        xlim, ylim: Crop limits in the edges' projected CRS (metres)
        theme: Theme colour dict
        texts: Poster text, see layout_text
        settings: PlotterSettings
        edits: Optional poster_edits.Edits
    """
    W, H, pen = settings.width_mm, settings.height_mm, settings.pen_width
    page = box(0, 0, W, H)

    def hidden(key):
        return edits is not None and edits.layer_hidden(key)

    print("Laying out stroke text...")
    text_lines, knockout = layout_text(texts, W, H, pen, edits)
    text_lines = to_polylines(MultiLineString(text_lines).intersection(page))
    if edits is not None:
        # Erase regions clear the map like the text block does (text itself stays)
        knockout = unary_union([knockout, edits.erase_area(W, H)])

    print("Converting roads to pen strokes...")
    keys = edges["highway"].map(classify_highway)
    roads_by_class = {}
    for key in keys.unique():
        if hidden(key):
            continue
        geoms = shapely.clip_by_rect(edges.geometry[keys == key].values, xlim[0], ylim[0], xlim[1], ylim[1])
        lines = [page_transform(g, xlim, ylim, W) for g in geoms if not g.is_empty]
        roads_by_class[key] = MultiLineString(
            [ln for g in lines for ln in to_shapely_lines(g)]
        )
    road_strokes, road_area = render_roads(roads_by_class, pen, page, knockout, W, H)

    print("Filling water and parks...")
    exclude = unary_union([road_area, knockout])
    crs = edges.crs
    water_lines, parks_lines = [], []
    if not hidden("water"):
        water_lines = render_areas(
            _polygons_mm(water, crs, xlim, ylim, W), settings.spacing("water"), WATER_HATCH_ANGLE, exclude, page,
            mode=settings.fill_mode("water"), pen=pen, outline=settings.water_outline,
        )
    if not hidden("parks"):
        parks_lines = render_areas(
            _polygons_mm(parks, crs, xlim, ylim, W), settings.spacing("parks"), PARKS_HATCH_ANGLE, exclude, page,
            mode=settings.fill_mode("parks"), pen=pen,
        )

    entries = [("water", theme["water"], water_lines), ("parks", theme["parks"], parks_lines)]
    for key, _, _ in reversed(ROAD_CLASSES):
        entries.append((key, theme[key], road_strokes.get(key, [])))
    entries.append(("text", theme["text"], text_lines))

    print(f"Writing plotter SVG ({W:g} × {H:g} mm, pen {pen:g} mm)...")
    write_svg(output_file, build_layers(entries), settings)
