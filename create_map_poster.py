#!/usr/bin/env python3
"""
City Map Poster Generator

This module generates beautiful, minimalist map posters for any city in the world.
It fetches OpenStreetMap data using OSMnx, applies customizable themes, and creates
high-quality poster-ready images with roads, water features, and parks.
"""

import argparse
import asyncio
import json
import os
import sys
import time
from datetime import datetime
from typing import cast

import matplotlib.colors as mcolors
import matplotlib.pyplot as plt
import numpy as np
import osmnx as ox
from geopandas import GeoDataFrame
from geopy.geocoders import Nominatim
from lat_lon_parser import parse
from font_management import load_fonts
import osm_cache
import overpass_servers
import plotter_svg
from matplotlib.font_manager import FontProperties
from networkx import MultiDiGraph
from osm_cache import CacheError, cache_get, cache_set
from osmnx._errors import InsufficientResponseError
from shapely.geometry import Point
from tqdm import tqdm


# OpenStreetMap server: 'auto' (health check + fallback) or an Overpass API base URL
OVERPASS_CHOICE = overpass_servers.AUTO
_overpass_order = None  # Servers to try, resolved on the first download

THEMES_DIR = "themes"
FONTS_DIR = "fonts"
POSTERS_DIR = "posters"

FONTS = load_fonts()

# Poster size in mm
DEFAULT_WIDTH_MM = 300
DEFAULT_HEIGHT_MM = 400
MAX_SIZE_MM = 500  # Limit for png/svg/pdf output; plotter output is not limited

# Base font sizes in points (at the reference size plotter_svg.REFERENCE_SIZE_MM)
BASE_MAIN = 60
BASE_SUB = 22
BASE_COORDS = 14
BASE_ATTR = 8


# Font loading now handled by font_management.py module


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


def generate_output_filename(city, theme_name, output_format):
    """
    Generate unique output filename with city, theme, and datetime.
    """
    if not os.path.exists(POSTERS_DIR):
        os.makedirs(POSTERS_DIR)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    city_slug = city.lower().replace(" ", "_")
    ext = output_format.lower()
    if ext == "plotter":
        ext = "svg"
    filename = f"{city_slug}_{theme_name}_{timestamp}.{ext}"
    return os.path.join(POSTERS_DIR, filename)


def get_available_themes():
    """
    Scans the themes directory and returns a list of available theme names.
    """
    if not os.path.exists(THEMES_DIR):
        os.makedirs(THEMES_DIR)
        return []

    themes = []
    for file in sorted(os.listdir(THEMES_DIR)):
        if file.endswith(".json"):
            theme_name = file[:-5]  # Remove .json extension
            themes.append(theme_name)
    return themes


def load_theme(theme_name="terracotta"):
    """
    Load theme from JSON file in themes directory.
    """
    theme_file = os.path.join(THEMES_DIR, f"{theme_name}.json")

    if not os.path.exists(theme_file):
        print(f"⚠ Theme file '{theme_file}' not found. Using default terracotta theme.")
        # Fallback to embedded terracotta theme
        return {
            "name": "Terracotta",
            "description": "Mediterranean warmth - burnt orange and clay tones on cream",
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

    with open(theme_file, "r") as f:
        theme = json.load(f)
        print(f"✓ Loaded theme: {theme.get('name', theme_name)}")
        if "description" in theme:
            print(f"  {theme['description']}")
        return theme


# Load theme (can be changed via command line or input)
THEME = dict[str, str]()  # Will be loaded later


def create_gradient_fade(ax, color, location="bottom", zorder=10):
    """
    Creates a fade effect at the top or bottom of the map.
    """
    vals = np.linspace(0, 1, 256).reshape(-1, 1)
    gradient = np.hstack((vals, vals))

    rgb = mcolors.to_rgb(color)
    my_colors = np.zeros((256, 4))
    my_colors[:, 0] = rgb[0]
    my_colors[:, 1] = rgb[1]
    my_colors[:, 2] = rgb[2]

    if location == "bottom":
        my_colors[:, 3] = np.linspace(1, 0, 256)
        extent_y_start = 0
        extent_y_end = 0.25
    else:
        my_colors[:, 3] = np.linspace(0, 1, 256)
        extent_y_start = 0.75
        extent_y_end = 1.0

    custom_cmap = mcolors.ListedColormap(my_colors)

    xlim = ax.get_xlim()
    ylim = ax.get_ylim()
    y_range = ylim[1] - ylim[0]

    y_bottom = ylim[0] + y_range * extent_y_start
    y_top = ylim[0] + y_range * extent_y_end

    ax.imshow(
        gradient,
        extent=[xlim[0], xlim[1], y_bottom, y_top],
        aspect="auto",
        cmap=custom_cmap,
        zorder=zorder,
        origin="lower",
    )


def get_edge_colors_by_type(g):
    """
    Assigns colors to edges based on road type hierarchy.
    Returns a list of colors corresponding to each edge in the graph.
    """
    edge_colors = []

    for _u, _v, data in g.edges(data=True):
        # Get the highway type (can be a list or string)
        highway = data.get('highway', 'unclassified')

        # Handle list of highway types (take the first one)
        if isinstance(highway, list):
            highway = highway[0] if highway else 'unclassified'

        # Assign color based on road type
        if highway in ["motorway", "motorway_link"]:
            color = THEME["road_motorway"]
        elif highway in ["trunk", "trunk_link", "primary", "primary_link"]:
            color = THEME["road_primary"]
        elif highway in ["secondary", "secondary_link"]:
            color = THEME["road_secondary"]
        elif highway in ["tertiary", "tertiary_link"]:
            color = THEME["road_tertiary"]
        elif highway in ["residential", "living_street", "unclassified"]:
            color = THEME["road_residential"]
        else:
            color = THEME['road_default']

        edge_colors.append(color)

    return edge_colors


def get_edge_widths_by_type(g):
    """
    Assigns line widths to edges based on road type.
    Major roads get thicker lines.
    """
    edge_widths = []

    for _u, _v, data in g.edges(data=True):
        highway = data.get('highway', 'unclassified')

        if isinstance(highway, list):
            highway = highway[0] if highway else 'unclassified'

        # Assign width based on road importance
        if highway in ["motorway", "motorway_link"]:
            width = 1.2
        elif highway in ["trunk", "trunk_link", "primary", "primary_link"]:
            width = 1.0
        elif highway in ["secondary", "secondary_link"]:
            width = 0.8
        elif highway in ["tertiary", "tertiary_link"]:
            width = 0.6
        else:
            width = 0.4

        edge_widths.append(width)

    return edge_widths


def get_coordinates(city, country):
    """
    Fetches coordinates for a given city and country using geopy.
    Includes rate limiting to be respectful to the geocoding service.
    """
    coords = f"coords_{city.lower()}_{country.lower()}"
    cached = cache_get(coords)
    if cached:
        print(f"✓ Using cached coordinates for {city}, {country}")
        return cached

    print("Looking up coordinates...")
    geolocator = Nominatim(user_agent="city_map_poster", timeout=10)

    # Add a small delay to respect Nominatim's usage policy
    time.sleep(1)

    try:
        location = geolocator.geocode(f"{city}, {country}")
    except Exception as e:
        raise ValueError(f"Geocoding failed for {city}, {country}: {e}") from e

    # If geocode returned a coroutine in some environments, run it to get the result.
    if asyncio.iscoroutine(location):
        try:
            location = asyncio.run(location)
        except RuntimeError as exc:
            # If an event loop is already running, try using it to complete the coroutine.
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # Running event loop in the same thread; raise a clear error.
                raise RuntimeError(
                    "Geocoder returned a coroutine while an event loop is already running. "
                    "Run this script in a synchronous environment."
                ) from exc
            location = loop.run_until_complete(location)

    if location:
        # Use getattr to safely access address (helps static analyzers)
        addr = getattr(location, "address", None)
        if addr:
            print(f"✓ Found: {addr}")
        else:
            print("✓ Found location (address not available)")
        print(f"✓ Coordinates: {location.latitude}, {location.longitude}")
        try:
            cache_set(coords, (location.latitude, location.longitude))
        except CacheError as e:
            print(e)
        return (location.latitude, location.longitude)

    raise ValueError(f"Could not find coordinates for {city}, {country}")


def get_crop_limits(g_proj, center_lat_lon, aspect, dist):
    """
    Crop inward to preserve aspect ratio (width / height) while guaranteeing
    full coverage of the requested radius.
    """
    lat, lon = center_lat_lon

    # Project center point into graph CRS
    center = (
        ox.projection.project_geometry(
            Point(lon, lat),
            crs="EPSG:4326",
            to_crs=g_proj.graph["crs"]
        )[0]
    )
    center_x, center_y = center.x, center.y

    # Start from the *requested* radius
    half_x = dist
    half_y = dist

    # Cut inward to match aspect
    if aspect > 1:  # landscape → reduce height
        half_y = half_x / aspect
    else:  # portrait → reduce width
        half_x = half_y * aspect

    return (
        (center_x - half_x, center_x + half_x),
        (center_y - half_y, center_y + half_y),
    )


def overpass_download(call):
    """
    Run an OSMnx download against the configured OpenStreetMap server(s).

    In 'auto' mode the servers are health-checked once, then tried in order with
    fallback. Messages go through tqdm.write so the progress bar cannot hide them.
    """
    global _overpass_order
    if _overpass_order is None:
        overpass_servers.limit_retries(log=tqdm.write)
        _overpass_order = overpass_servers.candidates(OVERPASS_CHOICE, log=tqdm.write)
    result, url = overpass_servers.run(call, _overpass_order, log=tqdm.write)
    # Keep using the server that answered for the remaining downloads
    _overpass_order = [url] + [u for u in _overpass_order if u != url]
    return result


def fetch_graph(point, dist) -> MultiDiGraph:
    """
    Fetch street network graph from OpenStreetMap.

    Uses caching to avoid redundant downloads. Fetches all network types
    within the specified distance from the center point.

    Args:
        point: (latitude, longitude) tuple for center point
        dist: Distance in meters from center point

    Returns:
        MultiDiGraph of street network

    Raises:
        RuntimeError: If the street network cannot be downloaded (message includes the cause)
    """
    lat, lon = point

    def download(fetch_dist):
        g = overpass_download(
            lambda: ox.graph_from_point(
                point, dist=fetch_dist, dist_type='bbox', network_type='all', truncate_by_edge=True
            )
        )
        # Rate limit between requests
        time.sleep(0.5)
        return g

    try:
        g, cached = osm_cache.load_area(
            f"graph_{lat}_{lon}", "", dist, download, lambda g, d: osm_cache.crop_graph(g, point, d)
        )
    except overpass_servers.OverpassError as e:
        raise RuntimeError(f"Failed to retrieve street network data from OpenStreetMap: {e}") from e
    except Exception as e:
        raise RuntimeError(f"Failed to retrieve street network data: {e}") from e
    if cached:
        print("✓ Using cached street network")
    return cast(MultiDiGraph, g)


def fetch_features(point, dist, tags, name) -> GeoDataFrame | None:
    """
    Fetch geographic features (water, parks, etc.) from OpenStreetMap.

    Uses caching to avoid redundant downloads. Fetches features matching
    the specified OSM tags within distance from center point.

    Args:
        point: (latitude, longitude) tuple for center point
        dist: Distance in meters from center point
        tags: Dictionary of OSM tags to filter features
        name: Name for this feature type (for caching and logging)

    Returns:
        GeoDataFrame of features, or None if there are none or the fetch fails
    """
    lat, lon = point
    tag_str = "_".join(tags.keys())

    def download(fetch_dist):
        try:
            data = overpass_download(lambda: ox.features_from_point(point, tags=tags, dist=fetch_dist))
        except InsufficientResponseError:
            data = None
        # Rate limit between requests
        time.sleep(0.3)
        return data

    try:
        data, cached = osm_cache.load_area(
            f"{name}_{lat}_{lon}", f"_{tag_str}", dist, download,
            lambda gdf, d: osm_cache.crop_features(gdf, point, d),
        )
    except Exception as e:
        tqdm.write(f"⚠ Could not download {name} ({e}); the poster is drawn without them")
        return None
    if cached:
        print(f"✓ Using cached {name}")
    if data is None:
        tqdm.write(f"  No {name} in this area")
    return cast(GeoDataFrame | None, data)


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


def create_plotter_poster(g, water, parks, point, compensated_dist, output_file,
                          display_city, display_country, plotter_settings):
    """
    Render the fetched map data as a plotter-ready SVG.

    Args:
        g: Street network graph (unprojected)
        water: Water features GeoDataFrame or None
        parks: Park features GeoDataFrame or None
        point: (latitude, longitude) map center
        compensated_dist: Fetch radius in meters (used for cropping)
        output_file: Destination .svg path
        display_city: City text for the poster
        display_country: Country text for the poster
        plotter_settings: plotter_svg.PlotterSettings
    """
    print("Rendering plotter paths...")
    width_mm, height_mm = plotter_settings.width_mm, plotter_settings.height_mm
    g_proj = ox.project_graph(g)
    edges = ox.graph_to_gdfs(g_proj, nodes=False)
    crop_xlim, crop_ylim = get_crop_limits(g_proj, point, width_mm / height_mm, compensated_dist)

    scale_factor = min(width_mm, height_mm) / plotter_svg.REFERENCE_SIZE_MM
    spaced_city, city_size = format_city_title(display_city, scale_factor)
    texts = {
        "city": (spaced_city, city_size),
        "country": (display_country.upper(), BASE_SUB * scale_factor),
        "coords": (format_coordinates(*point), BASE_COORDS * scale_factor),
        "attribution": ("© OpenStreetMap contributors", BASE_ATTR),
    }

    plotter_svg.render(
        output_file, edges, water, parks, crop_xlim, crop_ylim, THEME, texts, plotter_settings
    )
    print(f"✓ Done! Plotter SVG saved as {output_file}")


def create_poster(
    city,
    country,
    point,
    dist,
    output_file,
    output_format,
    width_mm=DEFAULT_WIDTH_MM,
    height_mm=DEFAULT_HEIGHT_MM,
    country_label=None,
    name_label=None,
    display_city=None,
    display_country=None,
    fonts=None,
    plotter_settings=None,
):
    """
    Generate a complete map poster with roads, water, parks, and typography.

    Creates a high-quality poster by fetching OSM data, rendering map layers,
    applying the current theme, and adding text labels with coordinates.

    Args:
        city: City name for display on poster
        country: Country name for display on poster
        point: (latitude, longitude) tuple for map center
        dist: Map radius in meters
        output_file: Path where poster will be saved
        output_format: File format ('png', 'svg', 'pdf', or 'plotter')
        width_mm: Poster width in mm (default: 300, CLI --width)
        height_mm: Poster height in mm (default: 400, CLI --height)
        country_label: Optional override for country text on poster
        _name_label: Optional override for city name (unused, reserved for future use)
        plotter_settings: plotter_svg.PlotterSettings, required for the 'plotter' format

    Raises:
        RuntimeError: If street network data cannot be retrieved
    """
    # Handle display names for i18n support
    # Priority: display_city/display_country > name_label/country_label > city/country
    display_city = display_city or name_label or city
    display_country = display_country or country_label or country

    print(f"\nGenerating map for {city}, {country}...")

    # Progress bar for data fetching
    with tqdm(
        total=3,
        desc="Fetching map data",
        unit="step",
        bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt}",
    ) as pbar:
        # 1. Fetch Street Network
        pbar.set_description("Downloading street network")
        # To compensate for viewport crop
        compensated_dist = dist * (max(height_mm, width_mm) / min(height_mm, width_mm)) / 4
        g = fetch_graph(point, compensated_dist)
        if g is None:
            raise RuntimeError("Failed to retrieve street network data.")
        pbar.update(1)

        # 2. Fetch Water Features
        pbar.set_description("Downloading water features")
        water = fetch_features(
            point,
            compensated_dist,
            tags={"natural": "water", "waterway": "riverbank"},
            name="water",
        )
        pbar.update(1)

        # 3. Fetch Parks
        pbar.set_description("Downloading parks/green spaces")
        parks = fetch_features(
            point,
            compensated_dist,
            tags={"leisure": "park", "landuse": "grass"},
            name="parks",
        )
        pbar.update(1)

    print("✓ All data retrieved successfully!")

    if output_format.lower() == "plotter":
        create_plotter_poster(
            g, water, parks, point, compensated_dist, output_file,
            display_city, display_country, plotter_settings,
        )
        return

    # 2. Setup Plot
    print("Rendering map...")
    # matplotlib sizes figures in inches
    fig, ax = plt.subplots(figsize=(width_mm / 25.4, height_mm / 25.4), facecolor=THEME["bg"])
    ax.set_facecolor(THEME["bg"])
    ax.set_position((0.0, 0.0, 1.0, 1.0))

    # Project graph to a metric CRS so distances and aspect are linear (meters)
    g_proj = ox.project_graph(g)

    # 3. Plot Layers
    # Layer 1: Polygons (filter to only plot polygon/multipolygon geometries, not points)
    if water is not None and not water.empty:
        # Filter to only polygon/multipolygon geometries to avoid point features showing as dots
        water_polys = water[water.geometry.type.isin(["Polygon", "MultiPolygon"])]
        if not water_polys.empty:
            # Project water features in the same CRS as the graph
            try:
                water_polys = ox.projection.project_gdf(water_polys)
            except Exception:
                water_polys = water_polys.to_crs(g_proj.graph['crs'])
            water_polys.plot(ax=ax, facecolor=THEME['water'], edgecolor='none', zorder=0.5)

    if parks is not None and not parks.empty:
        # Filter to only polygon/multipolygon geometries to avoid point features showing as dots
        parks_polys = parks[parks.geometry.type.isin(["Polygon", "MultiPolygon"])]
        if not parks_polys.empty:
            # Project park features in the same CRS as the graph
            try:
                parks_polys = ox.projection.project_gdf(parks_polys)
            except Exception:
                parks_polys = parks_polys.to_crs(g_proj.graph['crs'])
            parks_polys.plot(ax=ax, facecolor=THEME['parks'], edgecolor='none', zorder=0.8)
    # Layer 2: Roads with hierarchy coloring
    print("Applying road hierarchy colors...")
    edge_colors = get_edge_colors_by_type(g_proj)
    edge_widths = get_edge_widths_by_type(g_proj)

    # Determine cropping limits to maintain the poster aspect ratio
    fig_width, fig_height = fig.get_size_inches()
    crop_xlim, crop_ylim = get_crop_limits(g_proj, point, fig_width / fig_height, compensated_dist)
    # Plot the projected graph and then apply the cropped limits
    ox.plot_graph(
        g_proj, ax=ax, bgcolor=THEME['bg'],
        node_size=0,
        edge_color=edge_colors,
        edge_linewidth=edge_widths,
        show=False,
        close=False,
    )
    ax.set_aspect("equal", adjustable="box")
    ax.set_xlim(crop_xlim)
    ax.set_ylim(crop_ylim)

    # Layer 3: Gradients (Top and Bottom)
    create_gradient_fade(ax, THEME['gradient_color'], location='bottom', zorder=10)
    create_gradient_fade(ax, THEME['gradient_color'], location='top', zorder=10)

    # Calculate scale factor based on smaller dimension relative to the reference size
    # This ensures text scales properly for both portrait and landscape orientations
    scale_factor = min(height_mm, width_mm) / plotter_svg.REFERENCE_SIZE_MM

    # 4. Typography - use custom fonts if provided, otherwise use default FONTS
    active_fonts = fonts or FONTS
    if active_fonts:
        # font_main is calculated dynamically later based on length
        font_sub = FontProperties(
            fname=active_fonts["light"], size=BASE_SUB * scale_factor
        )
        font_coords = FontProperties(
            fname=active_fonts["regular"], size=BASE_COORDS * scale_factor
        )
        font_attr = FontProperties(
            fname=active_fonts["light"], size=BASE_ATTR * scale_factor
        )
    else:
        # Fallback to system fonts
        font_sub = FontProperties(
            family="monospace", weight="normal", size=BASE_SUB * scale_factor
        )
        font_coords = FontProperties(
            family="monospace", size=BASE_COORDS * scale_factor
        )
        font_attr = FontProperties(family="monospace", size=BASE_ATTR * scale_factor)

    spaced_city, adjusted_font_size = format_city_title(display_city, scale_factor)

    if active_fonts:
        font_main_adjusted = FontProperties(
            fname=active_fonts["bold"], size=adjusted_font_size
        )
    else:
        font_main_adjusted = FontProperties(
            family="monospace", weight="bold", size=adjusted_font_size
        )

    # --- BOTTOM TEXT ---
    ax.text(
        0.5,
        0.14,
        spaced_city,
        transform=ax.transAxes,
        color=THEME["text"],
        ha="center",
        fontproperties=font_main_adjusted,
        zorder=11,
    )

    ax.text(
        0.5,
        0.10,
        display_country.upper(),
        transform=ax.transAxes,
        color=THEME["text"],
        ha="center",
        fontproperties=font_sub,
        zorder=11,
    )

    coords = format_coordinates(*point)

    ax.text(
        0.5,
        0.07,
        coords,
        transform=ax.transAxes,
        color=THEME["text"],
        alpha=0.7,
        ha="center",
        fontproperties=font_coords,
        zorder=11,
    )

    ax.plot(
        [0.4, 0.6],
        [0.125, 0.125],
        transform=ax.transAxes,
        color=THEME["text"],
        linewidth=1 * scale_factor,
        zorder=11,
    )

    # --- ATTRIBUTION (bottom right) ---
    if FONTS:
        font_attr = FontProperties(fname=FONTS["light"], size=8)
    else:
        font_attr = FontProperties(family="monospace", size=8)

    ax.text(
        0.98,
        0.02,
        "© OpenStreetMap contributors",
        transform=ax.transAxes,
        color=THEME["text"],
        alpha=0.5,
        ha="right",
        va="bottom",
        fontproperties=font_attr,
        zorder=11,
    )

    # 5. Save
    print(f"Saving to {output_file}...")

    fmt = output_format.lower()
    # Save the full figure so the output is exactly --width x --height mm
    save_kwargs = dict(facecolor=THEME["bg"])

    # DPI matters mainly for raster formats
    if fmt == "png":
        save_kwargs["dpi"] = 300

    plt.savefig(output_file, format=fmt, **save_kwargs)

    plt.close()
    print(f"✓ Done! Poster saved as {output_file}")


def print_examples():
    """Print usage examples."""
    print("""
City Map Poster Generator
=========================

Usage:
  python create_map_poster.py --city <city> --country <country> [options]

Examples:
  # Iconic grid patterns
  python create_map_poster.py -c "New York" -C "USA" -t noir -d 12000           # Manhattan grid
  python create_map_poster.py -c "Barcelona" -C "Spain" -t warm_beige -d 8000   # Eixample district grid

  # Waterfront & canals
  python create_map_poster.py -c "Venice" -C "Italy" -t blueprint -d 4000       # Canal network
  python create_map_poster.py -c "Amsterdam" -C "Netherlands" -t ocean -d 6000  # Concentric canals
  python create_map_poster.py -c "Dubai" -C "UAE" -t midnight_blue -d 15000     # Palm & coastline

  # Radial patterns
  python create_map_poster.py -c "Paris" -C "France" -t pastel_dream -d 10000   # Haussmann boulevards
  python create_map_poster.py -c "Moscow" -C "Russia" -t noir -d 12000          # Ring roads

  # Organic old cities
  python create_map_poster.py -c "Tokyo" -C "Japan" -t japanese_ink -d 15000    # Dense organic streets
  python create_map_poster.py -c "Marrakech" -C "Morocco" -t terracotta -d 5000 # Medina maze
  python create_map_poster.py -c "Rome" -C "Italy" -t warm_beige -d 8000        # Ancient street layout

  # Coastal cities
  python create_map_poster.py -c "San Francisco" -C "USA" -t sunset -d 10000    # Peninsula grid
  python create_map_poster.py -c "Sydney" -C "Australia" -t ocean -d 12000      # Harbor city
  python create_map_poster.py -c "Mumbai" -C "India" -t contrast_zones -d 18000 # Coastal peninsula

  # River cities
  python create_map_poster.py -c "London" -C "UK" -t noir -d 15000              # Thames curves
  python create_map_poster.py -c "Budapest" -C "Hungary" -t copper_patina -d 8000  # Danube split

  # Pen plotter SVG (A3, 0.3 mm pen)
  python create_map_poster.py -c "Venice" -C "Italy" -d 3000 -f plotter -W 297 -H 420

  # List themes
  python create_map_poster.py --list-themes

Options:
  --city, -c        City name (required)
  --country, -C     Country name (required)
  --country-label   Override country text displayed on poster
  --theme, -t       Theme name (default: terracotta)
  --all-themes      Generate posters for all themes
  --distance, -d    Map radius in meters (default: 18000)
  --list-themes     List all available themes
  --width, -W       Poster width in mm (default: 300)
  --height, -H      Poster height in mm (default: 400)
  --format, -f      Output format: png, svg, pdf or plotter (default: png)
  --overpass-url    OpenStreetMap server URL or 'auto' (default: $OVERPASS_URL or auto)
  --pen-width       Plotter pen width in mm (default: 0.3)
  --hatch-spacing   Plotter hatch spacing for water/parks in mm (default: pen width)

Distance guide:
  4000-6000m   Small/dense cities (Venice, Amsterdam old center)
  8000-12000m  Medium cities, focused downtown (Paris, Barcelona)
  15000-20000m Large metros, full city view (Tokyo, Mumbai)

Available themes can be found in the 'themes/' directory.
Generated posters are saved to 'posters/' directory.
""")


def list_themes():
    """List all available themes with descriptions."""
    available_themes = get_available_themes()
    if not available_themes:
        print("No themes found in 'themes/' directory.")
        return

    print("\nAvailable Themes:")
    print("-" * 60)
    for theme_name in available_themes:
        theme_path = os.path.join(THEMES_DIR, f"{theme_name}.json")
        try:
            with open(theme_path, "r") as f:
                theme_data = json.load(f)
                display_name = theme_data.get('name', theme_name)
                description = theme_data.get('description', '')
        except (OSError, json.JSONDecodeError):
            display_name = theme_name
            description = ""
        print(f"  {theme_name}")
        print(f"    {display_name}")
        if description:
            print(f"    {description}")
        print()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Generate beautiful map posters for any city",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python create_map_poster.py --city "New York" --country "USA"
  python create_map_poster.py --city "New York" --country "USA" -l 40.776676 -73.971321 --theme neon_cyberpunk
  python create_map_poster.py --city Tokyo --country Japan --theme midnight_blue
  python create_map_poster.py --city Paris --country France --theme noir --distance 15000
  python create_map_poster.py --city Venice --country Italy --format plotter --width 297 --height 420
  python create_map_poster.py --list-themes
        """,
    )

    parser.add_argument("--city", "-c", type=str, help="City name")
    parser.add_argument("--country", "-C", type=str, help="Country name")
    parser.add_argument(
        "--latitude",
        "-lat",
        dest="latitude",
        type=str,
        help="Override latitude center point",
    )
    parser.add_argument(
        "--longitude",
        "-long",
        dest="longitude",
        type=str,
        help="Override longitude center point",
    )
    parser.add_argument(
        "--country-label",
        dest="country_label",
        type=str,
        help="Override country text displayed on poster",
    )
    parser.add_argument(
        "--theme",
        "-t",
        type=str,
        default="terracotta",
        help="Theme name (default: terracotta)",
    )
    parser.add_argument(
        "--all-themes",
        "--All-themes",
        dest="all_themes",
        action="store_true",
        help="Generate posters for all themes",
    )
    parser.add_argument(
        "--distance",
        "-d",
        type=int,
        default=18000,
        help="Map radius in meters (default: 18000)",
    )
    parser.add_argument(
        "--width",
        "-W",
        type=float,
        default=DEFAULT_WIDTH_MM,
        help=f"Poster width in mm (default: {DEFAULT_WIDTH_MM}, max: {MAX_SIZE_MM} except for plotter)",
    )
    parser.add_argument(
        "--height",
        "-H",
        type=float,
        default=DEFAULT_HEIGHT_MM,
        help=f"Poster height in mm (default: {DEFAULT_HEIGHT_MM}, max: {MAX_SIZE_MM} except for plotter)",
    )
    parser.add_argument(
        "--list-themes", action="store_true", help="List all available themes"
    )
    parser.add_argument(
        "--display-city",
        "-dc",
        type=str,
        help="Custom display name for city (for i18n support)",
    )
    parser.add_argument(
        "--display-country",
        "-dC",
        type=str,
        help="Custom display name for country (for i18n support)",
    )
    parser.add_argument(
        "--font-family",
        type=str,
        help='Google Fonts family name (e.g., "Noto Sans JP", "Open Sans"). If not specified, uses local Roboto fonts.',
    )
    parser.add_argument(
        "--format",
        "-f",
        default="png",
        choices=["png", "svg", "pdf", "plotter"],
        help="Output format for the poster (default: png). 'plotter' writes a pen-plotter-ready SVG",
    )
    parser.add_argument(
        "--overpass-url",
        default=os.environ.get("OVERPASS_URL", overpass_servers.AUTO),
        help="OpenStreetMap (Overpass API) server, e.g. https://lz4.overpass-api.de/api, or 'auto' to check "
             "the known servers and fall back automatically (default: $OVERPASS_URL or auto)",
    )
    parser.add_argument(
        "--pen-width",
        type=float,
        default=0.3,
        help="Plotter pen (stroke) width in mm (default: 0.3)",
    )
    parser.add_argument(
        "--hatch-spacing",
        type=float,
        help="Plotter hatch line spacing in mm for water/parks (default: pen width)",
    )

    args = parser.parse_args()

    # If no arguments provided, show examples
    if len(sys.argv) == 1:
        print_examples()
        sys.exit(0)

    # List themes if requested
    if args.list_themes:
        list_themes()
        sys.exit(0)

    # Validate required arguments
    if not args.city or not args.country:
        print("Error: --city and --country are required.\n")
        print_examples()
        sys.exit(1)

    try:
        OVERPASS_CHOICE = overpass_servers.normalize(args.overpass_url)
    except ValueError as e:
        print(f"Error: --overpass-url: {e}")
        sys.exit(1)

    # Validate sizes and plotter options
    for name in ("width", "height", "pen_width", "hatch_spacing"):
        value = getattr(args, name)
        if value is not None and value <= 0:
            print(f"Error: --{name.replace('_', '-')} must be greater than 0.")
            sys.exit(1)

    # Enforce maximum dimensions for matplotlib output
    if args.format != "plotter":
        for name in ("width", "height"):
            if getattr(args, name) > MAX_SIZE_MM:
                print(f"⚠ --{name.replace('_', '-')} {getattr(args, name):g} exceeds the maximum of "
                      f"{MAX_SIZE_MM} mm. It's enforced as {MAX_SIZE_MM} mm.")
                setattr(args, name, float(MAX_SIZE_MM))

    plotter_settings = None
    hatch_spacing = args.hatch_spacing if args.hatch_spacing is not None else args.pen_width
    if hatch_spacing < args.pen_width:
        print(f"Error: --hatch-spacing ({hatch_spacing}) must not be less than --pen-width ({args.pen_width}).")
        sys.exit(1)
    if args.format == "plotter":
        plotter_settings = plotter_svg.PlotterSettings(args.width, args.height, args.pen_width, hatch_spacing)
    elif args.hatch_spacing is not None:
        print("⚠ --hatch-spacing only applies to --format plotter; ignoring.")

    available_themes = get_available_themes()
    if not available_themes:
        print("No themes found in 'themes/' directory.")
        sys.exit(1)

    if args.all_themes:
        themes_to_generate = available_themes
    else:
        if args.theme not in available_themes:
            print(f"Error: Theme '{args.theme}' not found.")
            print(f"Available themes: {', '.join(available_themes)}")
            sys.exit(1)
        themes_to_generate = [args.theme]

    print("=" * 50)
    print("City Map Poster Generator")
    print("=" * 50)

    # Load custom fonts if specified
    custom_fonts = None
    if args.font_family:
        custom_fonts = load_fonts(args.font_family)
        if not custom_fonts:
            print(f"⚠ Failed to load '{args.font_family}', falling back to Roboto")

    # Get coordinates and generate poster
    try:
        if args.latitude and args.longitude:
            lat = parse(args.latitude)
            lon = parse(args.longitude)
            coords = [lat, lon]
            print(f"✓ Coordinates: {', '.join([str(i) for i in coords])}")
        else:
            coords = get_coordinates(args.city, args.country)

        for theme_name in themes_to_generate:
            THEME = load_theme(theme_name)
            output_file = generate_output_filename(args.city, theme_name, args.format)
            create_poster(
                args.city,
                args.country,
                coords,
                args.distance,
                output_file,
                args.format,
                args.width,
                args.height,
                country_label=args.country_label,
                display_city=args.display_city,
                display_country=args.display_country,
                fonts=custom_fonts,
                plotter_settings=plotter_settings,
            )

        print("\n" + "=" * 50)
        print("✓ Poster generation complete!")
        print("=" * 50)

    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
