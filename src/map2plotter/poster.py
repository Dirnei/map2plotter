#!/usr/bin/env python3
"""
map2plotter

Generates minimalist map posters of any city in the world as pen-plotter SVGs.
It fetches OpenStreetMap data using OSMnx and draws roads, water, parks and the
poster text as stroke-only paths, one Inkscape layer per pen colour.
"""

import argparse
import asyncio
import json
import os
import sys
import time
from datetime import datetime
from typing import cast

import osmnx as ox
from geopandas import GeoDataFrame
from geopy.geocoders import Nominatim
from lat_lon_parser import parse
from networkx import MultiDiGraph
from osmnx._errors import InsufficientResponseError
from shapely.geometry import Point
from tqdm import tqdm

from . import USER_AGENT
from . import edits as poster_edits
from . import osm_cache, overpass, paths, plotter
from .colors import THEME_COLOR_KEYS, parse_color_overrides
from .osm_cache import CacheError, NotCachedError, cache_get, cache_set


# Identify map2plotter to Overpass (OSMnx downloads) and Nominatim (geocoding)
ox.settings.http_user_agent = USER_AGENT

# OpenStreetMap server: 'auto' (health check + fallback) or an Overpass API base URL
OVERPASS_CHOICE = overpass.AUTO
_overpass_order = None  # Servers to try, resolved on the first download
# --cache-only: never download map data or geocode; fail if it is not cached
CACHE_ONLY = False

THEMES_DIR = paths.THEMES_DIR
POSTERS_DIR = paths.POSTERS_DIR


# Poster size in mm
DEFAULT_WIDTH_MM = 300
DEFAULT_HEIGHT_MM = 400


def generate_output_filename(city, theme_name):
    """
    Generate unique output filename with city, theme, and datetime.
    """
    if not os.path.exists(POSTERS_DIR):
        os.makedirs(POSTERS_DIR)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    city_slug = city.lower().replace(" ", "_")
    filename = f"{city_slug}_{theme_name}_{timestamp}.svg"
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
            "text": "#8B4513",
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
        # Keep only the pen colours (older themes may still have e.g. 'bg')
        return {k: v for k, v in theme.items() if k in ("name", "description", *THEME_COLOR_KEYS)}


# Load theme (can be changed via command line or input)
THEME = dict[str, str]()  # Will be loaded later


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
    if CACHE_ONLY:
        raise NotCachedError(
            f"Coordinates for {city}, {country} are not cached; run without --cache-only "
            "or pass --latitude/--longitude"
        )

    print("Looking up coordinates...")
    geolocator = Nominatim(user_agent=USER_AGENT, timeout=10)

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
        overpass.limit_retries(log=tqdm.write)
        _overpass_order = overpass.candidates(OVERPASS_CHOICE, log=tqdm.write)
    result, url = overpass.run(call, _overpass_order, log=tqdm.write)
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
        if CACHE_ONLY:
            raise NotCachedError("street network")
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
    except NotCachedError as e:
        raise RuntimeError(
            "Map data for this area is not cached; run without --cache-only to download it"
        ) from e
    except overpass.OverpassError as e:
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
        if CACHE_ONLY:
            raise NotCachedError(f"{name} data is not cached")
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


def create_plotter_poster(g, water, parks, point, compensated_dist, output_file,
                          display_city, display_country, plotter_settings, edits=None):
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
        plotter_settings: plotter.PlotterSettings
        edits: Optional poster_edits.Edits
    """
    print("Rendering plotter paths...")
    width_mm, height_mm = plotter_settings.width_mm, plotter_settings.height_mm
    g_proj = ox.project_graph(g)
    edges = ox.graph_to_gdfs(g_proj, nodes=False)
    crop_xlim, crop_ylim = get_crop_limits(g_proj, point, width_mm / height_mm, compensated_dist)

    texts = plotter.poster_texts(display_city, display_country, *point, width_mm, height_mm)

    plotter.render(
        output_file, edges, water, parks, crop_xlim, crop_ylim, THEME, texts, plotter_settings, edits
    )
    print(f"✓ Done! Plotter SVG saved as {output_file}")


def create_poster(
    city,
    country,
    point,
    dist,
    output_file,
    plotter_settings,
    width_mm=DEFAULT_WIDTH_MM,
    height_mm=DEFAULT_HEIGHT_MM,
    country_label=None,
    name_label=None,
    display_city=None,
    display_country=None,
    edits=None,
):
    """
    Generate a plotter SVG poster with roads, water, parks, and typography.

    Fetches the OSM data (or reads it from the cache), then renders it as
    stroke-only pen paths with the current theme's colours.

    Args:
        city: City name for display on poster
        country: Country name for display on poster
        point: (latitude, longitude) tuple for map center
        dist: Map radius in meters
        output_file: Path of the .svg to write
        plotter_settings: plotter.PlotterSettings (size, pen width, fills)
        width_mm: Poster width in mm (default: 300, CLI --width)
        height_mm: Poster height in mm (default: 400, CLI --height)
        country_label: Optional override for country text on poster
        _name_label: Optional override for city name (unused, reserved for future use)
        edits: Optional poster_edits.Edits (erase regions, text offsets, hidden layers)

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

    create_plotter_poster(
        g, water, parks, point, compensated_dist, output_file,
        display_city, display_country, plotter_settings, edits,
    )


def print_examples():
    """Print usage examples."""
    print("""
map2plotter
===========

Usage:
  map2plotter --city <city> --country <country> [options]

Examples:
  # Iconic grid patterns
  map2plotter -c "New York" -C "USA" -t noir -d 12000           # Manhattan grid
  map2plotter -c "Barcelona" -C "Spain" -t warm_beige -d 8000   # Eixample district grid

  # Waterfront & canals
  map2plotter -c "Venice" -C "Italy" -t blueprint -d 4000       # Canal network
  map2plotter -c "Amsterdam" -C "Netherlands" -t ocean -d 6000  # Concentric canals
  map2plotter -c "Dubai" -C "UAE" -t midnight_blue -d 15000     # Palm & coastline

  # Radial patterns
  map2plotter -c "Paris" -C "France" -t pastel_dream -d 10000   # Haussmann boulevards
  map2plotter -c "Moscow" -C "Russia" -t noir -d 12000          # Ring roads

  # Organic old cities
  map2plotter -c "Tokyo" -C "Japan" -t japanese_ink -d 15000    # Dense organic streets
  map2plotter -c "Marrakech" -C "Morocco" -t terracotta -d 5000 # Medina maze
  map2plotter -c "Rome" -C "Italy" -t warm_beige -d 8000        # Ancient street layout

  # Coastal cities
  map2plotter -c "San Francisco" -C "USA" -t sunset -d 10000    # Peninsula grid
  map2plotter -c "Sydney" -C "Australia" -t ocean -d 12000      # Harbor city
  map2plotter -c "Mumbai" -C "India" -t contrast_zones -d 18000 # Coastal peninsula

  # River cities
  map2plotter -c "London" -C "UK" -t noir -d 15000              # Thames curves
  map2plotter -c "Budapest" -C "Hungary" -t copper_patina -d 8000  # Danube split

  # A3 poster for a 0.3 mm pen
  map2plotter -c "Venice" -C "Italy" -d 3000 -W 297 -H 420

  # Outlined, concentric water
  map2plotter -c "Venice" -C "Italy" -d 3000 --water-outline --water-fill concentric

  # Re-render from cached data only (no downloads)
  map2plotter -c "Venice" -C "Italy" -d 3000 --cache-only -o venice.svg

  # List themes
  map2plotter --list-themes

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
  --overpass-url    OpenStreetMap server URL or 'auto' (default: $OVERPASS_URL or auto)
  --pen-width       Pen width in mm (default: 0.3)
  --hatch-spacing   Fill line spacing for water/parks in mm (default: pen width)
  --water-fill      Water fill: hatch or concentric (default: hatch)
  --parks-fill      Parks fill: hatch or concentric (default: hatch)
  --water-spacing   Line spacing for water in mm (default: hatch spacing)
  --parks-spacing   Line spacing for parks in mm (default: hatch spacing)
  --water-outline   Stroke the outline of water areas
  --cache-only      Never download map data or geocode; fail if not cached
  --output, -o      Write the poster to this .svg file
  --edits           JSON edit list (erase regions, text offsets, hidden layers)
  --color           Override a pen colour, e.g. --color water=#1f5fa8 (repeatable)

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


def build_parser():
    """The command-line interface."""
    parser = argparse.ArgumentParser(
        prog="map2plotter",
        description="Generate pen-plotter map posters (SVG) for any city",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  map2plotter --city "New York" --country "USA"
  map2plotter --city "New York" --country "USA" -l 40.776676 -73.971321 --theme neon_cyberpunk
  map2plotter --city Tokyo --country Japan --theme midnight_blue
  map2plotter --city Paris --country France --theme noir --distance 15000
  map2plotter --city Venice --country Italy --width 297 --height 420 --pen-width 0.5
  map2plotter --list-themes
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
        help=f"Poster width in mm (default: {DEFAULT_WIDTH_MM})",
    )
    parser.add_argument(
        "--height",
        "-H",
        type=float,
        default=DEFAULT_HEIGHT_MM,
        help=f"Poster height in mm (default: {DEFAULT_HEIGHT_MM})",
    )
    parser.add_argument(
        "--list-themes", action="store_true", help="List all available themes"
    )
    parser.add_argument(
        "--display-city",
        "-dc",
        type=str,
        help="Custom display name for the city (Latin script; other characters are skipped)",
    )
    parser.add_argument(
        "--display-country",
        "-dC",
        type=str,
        help="Custom display name for the country (Latin script; other characters are skipped)",
    )
    parser.add_argument(
        "--overpass-url",
        default=os.environ.get("OVERPASS_URL", overpass.AUTO),
        help="OpenStreetMap (Overpass API) server, e.g. https://lz4.overpass-api.de/api, or 'auto' to check "
             "the known servers and fall back automatically (default: $OVERPASS_URL or auto)",
    )
    parser.add_argument(
        "--pen-width",
        type=float,
        default=0.3,
        help="Pen (stroke) width in mm (default: 0.3)",
    )
    parser.add_argument(
        "--hatch-spacing",
        type=float,
        help="Fill line spacing in mm for water/parks (default: pen width)",
    )
    parser.add_argument(
        "--water-fill",
        choices=plotter.FILL_MODES,
        default="hatch",
        help="Fill for water: 'hatch' (parallel lines) or 'concentric' (contours) (default: hatch)",
    )
    parser.add_argument(
        "--parks-fill",
        choices=plotter.FILL_MODES,
        default="hatch",
        help="Fill for parks: 'hatch' or 'concentric' (default: hatch)",
    )
    parser.add_argument(
        "--water-spacing",
        type=float,
        help="Line spacing in mm for water (default: hatch spacing)",
    )
    parser.add_argument(
        "--parks-spacing",
        type=float,
        help="Line spacing in mm for parks (default: hatch spacing)",
    )
    parser.add_argument(
        "--water-outline",
        action="store_true",
        help="Also stroke the outline of water areas",
    )
    parser.add_argument(
        "--cache-only",
        action="store_true",
        help="Never download map data or geocode; fail if the data is not cached",
    )
    parser.add_argument(
        "--output",
        "-o",
        help="Write the poster to this .svg file instead of posters/<city>_<theme>_<timestamp>.svg",
    )
    parser.add_argument(
        "--color",
        action="append",
        metavar="KEY=#RRGGBB",
        help="Override one pen colour, e.g. --color water=#1f5fa8 (repeatable; keys: "
             + ", ".join(THEME_COLOR_KEYS) + ")",
    )
    parser.add_argument(
        "--edits",
        help="JSON edit list (erase regions, text offsets, hidden layers) to apply",
    )
    return parser


def main(argv=None):
    """Run the poster generator CLI."""
    global THEME, OVERPASS_CHOICE, CACHE_ONLY
    argv = sys.argv[1:] if argv is None else argv
    parser = build_parser()
    args = parser.parse_args(argv)

    # If no arguments provided, show examples
    if not argv:
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
        OVERPASS_CHOICE = overpass.normalize(args.overpass_url)
    except ValueError as e:
        print(f"Error: --overpass-url: {e}")
        sys.exit(1)
    CACHE_ONLY = args.cache_only

    # Validate sizes and plotter options
    for name in ("width", "height", "pen_width", "hatch_spacing", "water_spacing", "parks_spacing"):
        value = getattr(args, name)
        if value is not None and value <= 0:
            print(f"Error: --{name.replace('_', '-')} must be greater than 0.")
            sys.exit(1)

    hatch_spacing = args.hatch_spacing if args.hatch_spacing is not None else args.pen_width
    for flag, value in (
        ("--hatch-spacing", hatch_spacing),
        ("--water-spacing", args.water_spacing),
        ("--parks-spacing", args.parks_spacing),
    ):
        if value is not None and value < args.pen_width:
            print(f"Error: {flag} ({value}) must not be less than --pen-width ({args.pen_width}).")
            sys.exit(1)
    plotter_settings = plotter.PlotterSettings(
        args.width, args.height, args.pen_width, hatch_spacing,
        water_fill=args.water_fill,
        parks_fill=args.parks_fill,
        water_spacing=args.water_spacing,
        parks_spacing=args.parks_spacing,
        water_outline=args.water_outline,
    )

    if args.output:
        if args.all_themes:
            print("Error: --output cannot be combined with --all-themes.")
            sys.exit(1)
        if os.path.splitext(args.output)[1].lower() != ".svg":
            print("Error: --output must be an .svg file.")
            sys.exit(1)

    try:
        color_overrides = parse_color_overrides(args.color)
    except ValueError as e:
        print(f"Error: --color: {e}")
        sys.exit(1)

    edits = None
    if args.edits:
        try:
            edits = poster_edits.load_edits(args.edits)
        except poster_edits.EditsError as e:
            print(f"Error: --edits: {e}")
            sys.exit(1)

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
    print("map2plotter")
    print("=" * 50)

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
            THEME = {**load_theme(theme_name), **color_overrides}
            if args.output:
                output_file = args.output
                os.makedirs(os.path.dirname(os.path.abspath(output_file)), exist_ok=True)
            else:
                output_file = generate_output_filename(args.city, theme_name)
            create_poster(
                args.city,
                args.country,
                coords,
                args.distance,
                output_file,
                plotter_settings,
                args.width,
                args.height,
                country_label=args.country_label,
                display_city=args.display_city,
                display_country=args.display_country,
                edits=edits,
            )

        print("\n" + "=" * 50)
        print("✓ Poster generation complete!")
        print("=" * 50)

    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
