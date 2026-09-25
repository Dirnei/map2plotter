"""
Poster Colours

Theme colour keys and parsing of single-colour overrides (--color KEY=#RRGGBB),
shared by the CLI and the web interface.
"""

import re

# Theme colour keys that may be overridden
THEME_COLOR_KEYS = (
    "bg", "text", "gradient_color", "water", "parks",
    "road_motorway", "road_primary", "road_secondary", "road_tertiary", "road_residential", "road_default",
)
_HEX_COLOR = re.compile(r"#[0-9a-fA-F]{6}")


def check_color(key, color):
    """Validate one override; return the colour in lowercase."""
    if key not in THEME_COLOR_KEYS:
        raise ValueError(f"unknown colour key '{key}' (expected one of {', '.join(THEME_COLOR_KEYS)})")
    if not isinstance(color, str) or not _HEX_COLOR.fullmatch(color):
        raise ValueError(f"'{color}' for {key} is not a #RRGGBB colour")
    return color.lower()


def parse_color_overrides(values):
    """
    Parse --color KEY=#RRGGBB values into {key: '#rrggbb'} (last value per key wins).

    Raises:
        ValueError: for a malformed value, an unknown key or an invalid colour
    """
    overrides = {}
    for value in values or []:
        key, sep, color = value.partition("=")
        if not sep:
            raise ValueError(f"'{value}' must look like KEY=#RRGGBB")
        overrides[key.strip()] = check_color(key.strip(), color.strip())
    return overrides
