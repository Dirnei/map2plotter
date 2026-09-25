"""Generate beautiful, minimalist map posters for any city in the world."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("map2plotter")
except PackageNotFoundError:  # Running from a source tree that is not installed
    __version__ = "0+unknown"

PROJECT_URL = "https://github.com/Dirnei/map2plotter"
# map2plotter continues this project (MIT licensed, no longer maintained)
ORIGINAL_PROJECT_URL = "https://github.com/originalankur/maptoposter"
# Sent to Overpass and Nominatim, whose usage policies ask clients to identify themselves
USER_AGENT = f"map2plotter/{__version__} (+{PROJECT_URL})"
