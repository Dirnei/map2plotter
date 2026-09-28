"""
Paths

Built-in data is found next to the package; the map data cache and the posters
are relative to the current working directory.
"""

import os
from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent
THEMES_DIR = PACKAGE_DIR / "data" / "themes"
STATIC_DIR = PACKAGE_DIR / "static"

CACHE_DIR = Path(os.environ.get("CACHE_DIR", "cache"))
POSTERS_DIR = Path("posters")
