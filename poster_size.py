"""
Poster Size Limits

Only PNG output has a size limit, and it is in pixels (memory and renderer
limits), not millimetres. SVG, PDF and plotter output accept any size.
Shared by the CLI and the web interface.
"""

import math

MAX_PNG_PIXELS = 200_000_000  # A0 at 300 dpi is ~140 MP
MAX_PNG_SIDE = 65_535  # Matplotlib's Agg renderer limit per side


def png_pixels(width_mm, height_mm, dpi):
    """Pixel size (width, height) of a PNG poster, rounded as the renderer does."""
    return round(width_mm / 25.4 * dpi), round(height_mm / 25.4 * dpi)


def png_fits(width_mm, height_mm, dpi):
    w, h = png_pixels(width_mm, height_mm, dpi)
    return w * h <= MAX_PNG_PIXELS and max(w, h) <= MAX_PNG_SIDE


def max_png_dpi(width_mm, height_mm):
    """Highest whole dpi at which a PNG of this size fits the limits (0 if none)."""
    area_in2 = width_mm * height_mm / 25.4 ** 2
    dpi = int(min(math.sqrt(MAX_PNG_PIXELS / area_in2), MAX_PNG_SIDE * 25.4 / max(width_mm, height_mm))) + 1
    while dpi > 0 and not png_fits(width_mm, height_mm, dpi):
        dpi -= 1
    return dpi


def png_limit_error(width_mm, height_mm, dpi):
    """Error message if the PNG is over the limits, else None."""
    if png_fits(width_mm, height_mm, dpi):
        return None
    w, h = png_pixels(width_mm, height_mm, dpi)
    best = max_png_dpi(width_mm, height_mm)
    return (
        f"a {width_mm:g} × {height_mm:g} mm PNG at {dpi} dpi would be {w} × {h} px ({w * h / 1e6:.0f} MP); "
        f"PNG is limited to {MAX_PNG_PIXELS // 1_000_000} MP and {MAX_PNG_SIDE} px per side. "
        f"Use at most {best} dpi, or SVG/PDF (no size limit)"
    )
