"""
Poster Edits

Manual adjustments to a poster, stored as data so that every re-render applies
them again: erase regions, text offsets / hidden text lines, and hidden layers.
All positions are page millimetres with the origin at the top-left corner and
y pointing down.
"""

import json
from dataclasses import dataclass, field

import shapely
from shapely.geometry import Polygon, box

VERSION = 1
TEXT_KEYS = ("city", "country", "coords", "divider")
LAYERS = (
    "water",
    "parks",
    "road_motorway",
    "road_primary",
    "road_secondary",
    "road_tertiary",
    "road_residential",
    "road_default",
)
_MEMBERS = {"version", "erase", "text", "hidden_layers"}
_TEXT_MEMBERS = {"dx", "dy", "hidden"}


class EditsError(ValueError):
    """Raised for an invalid edit list."""


@dataclass
class TextEdit:
    """Offset (mm) and visibility of one text line."""

    dx: float = 0.0
    dy: float = 0.0
    hidden: bool = False


@dataclass
class Edits:
    """A validated edit list."""

    erase: list = field(default_factory=list)  # list of [(x, y), ...] polygons in page mm
    text: dict = field(default_factory=dict)  # {text key: TextEdit}
    hidden_layers: set = field(default_factory=set)

    def text_edit(self, key):
        """The edit for a text line (a no-op edit if none is set)."""
        return self.text.get(key, TextEdit())

    def layer_hidden(self, key):
        return key in self.hidden_layers

    def erase_area(self, width_mm, height_mm):
        """Union of the erase polygons, clipped to the page (empty Polygon if none)."""
        if not self.erase:
            return Polygon()
        polys = [shapely.make_valid(Polygon(points)) for points in self.erase]
        return shapely.union_all(polys).intersection(box(0, 0, width_mm, height_mm))

    def is_empty(self):
        return not self.erase and not self.hidden_layers and all(
            t == TextEdit() for t in self.text.values()
        )

    def to_dict(self):
        return {
            "version": VERSION,
            "erase": [[list(p) for p in poly] for poly in self.erase],
            "text": {k: {"dx": t.dx, "dy": t.dy, "hidden": t.hidden} for k, t in self.text.items()},
            "hidden_layers": sorted(self.hidden_layers),
        }


def _number(value, where):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise EditsError(f"{where} must be a number")
    return float(value)


def parse_edits(obj):
    """
    Validate an edit list (parsed JSON) and return Edits.

    Raises:
        EditsError: with a message naming the offending member
    """
    if not isinstance(obj, dict):
        raise EditsError("Edit list must be a JSON object")
    unknown = set(obj) - _MEMBERS
    if unknown:
        raise EditsError(f"Unknown edit list member(s): {', '.join(sorted(unknown))}")
    if "version" in obj and obj["version"] != VERSION:
        raise EditsError(f"Unsupported edit list version {obj['version']!r} (expected {VERSION})")

    erase = []
    raw_erase = obj.get("erase", [])
    if not isinstance(raw_erase, list):
        raise EditsError("erase must be a list of polygons")
    for i, poly in enumerate(raw_erase):
        if not isinstance(poly, list) or len(poly) < 3:
            raise EditsError(f"erase[{i}] must be a list of at least 3 points")
        points = []
        for j, pt in enumerate(poly):
            if not isinstance(pt, list) or len(pt) != 2:
                raise EditsError(f"erase[{i}][{j}] must be an [x, y] pair")
            points.append((_number(pt[0], f"erase[{i}][{j}]"), _number(pt[1], f"erase[{i}][{j}]")))
        erase.append(points)

    text = {}
    raw_text = obj.get("text", {})
    if not isinstance(raw_text, dict):
        raise EditsError("text must be an object")
    for key, entry in raw_text.items():
        if key not in TEXT_KEYS:
            raise EditsError(f"Unknown text entry '{key}' (expected one of {', '.join(TEXT_KEYS)})")
        if not isinstance(entry, dict):
            raise EditsError(f"text.{key} must be an object")
        unknown = set(entry) - _TEXT_MEMBERS
        if unknown:
            raise EditsError(f"Unknown member(s) in text.{key}: {', '.join(sorted(unknown))}")
        hidden = entry.get("hidden", False)
        if not isinstance(hidden, bool):
            raise EditsError(f"text.{key}.hidden must be true or false")
        text[key] = TextEdit(
            dx=_number(entry.get("dx", 0), f"text.{key}.dx"),
            dy=_number(entry.get("dy", 0), f"text.{key}.dy"),
            hidden=hidden,
        )

    raw_layers = obj.get("hidden_layers", [])
    if not isinstance(raw_layers, list):
        raise EditsError("hidden_layers must be a list")
    for name in raw_layers:
        if name not in LAYERS:
            raise EditsError(f"Unknown layer '{name}' in hidden_layers (expected one of {', '.join(LAYERS)})")

    return Edits(erase=erase, text=text, hidden_layers=set(raw_layers))


def load_edits(path):
    """Read and validate an edit list file."""
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except OSError as e:
        raise EditsError(f"Cannot read edit list '{path}': {e}") from e
    except json.JSONDecodeError as e:
        raise EditsError(f"Edit list '{path}' is not valid JSON: {e}") from e
    return parse_edits(data)
