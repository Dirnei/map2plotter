"""
OpenStreetMap Area Cache

Pickle cache for downloaded OpenStreetMap data. Areas are downloaded in a few
fixed sizes (buckets) and a cached area is reused for any smaller request around
the same center by cropping it, so posters of the same place in different sizes
share one download. Areas without any data are cached too.
"""

import glob
import math
import os
import pickle
import re
from pathlib import Path

import osmnx as ox
from shapely.geometry import box


class CacheError(Exception):
    """Raised when a cache operation fails."""

    pass


CACHE_DIR = Path(os.environ.get("CACHE_DIR", "cache"))
CACHE_DIR.mkdir(exist_ok=True)

# Smallest download radius in meters; larger ones grow in steps of 2^(1/4) (~19%)
BASE_DIST = 250
# Stored for areas where OpenStreetMap has no matching data
NO_DATA = "__osm_cache_no_data__"

_DIST_RE = re.compile(r"\d+(\.\d+)?")


def _cache_path(key: str) -> str:
    """
    Generate a safe cache file path from a cache key.

    Args:
        key: Cache key identifier

    Returns:
        Path to cache file with .pkl extension
    """
    safe = key.replace(os.sep, "_")
    return os.path.join(CACHE_DIR, f"{safe}.pkl")


def cache_get(key: str):
    """
    Retrieve a cached object by key.

    Args:
        key: Cache key identifier

    Returns:
        Cached object if found, None otherwise

    Raises:
        CacheError: If cache read operation fails
    """
    try:
        path = _cache_path(key)
        if not os.path.exists(path):
            return None
        with open(path, "rb") as f:
            return pickle.load(f)
    except Exception as e:
        raise CacheError(f"Cache read failed: {e}") from e


def cache_set(key: str, value):
    """
    Store an object in the cache.

    Args:
        key: Cache key identifier
        value: Object to cache (must be picklable)

    Raises:
        CacheError: If cache write operation fails
    """
    try:
        if not os.path.exists(CACHE_DIR):
            os.makedirs(CACHE_DIR)
        path = _cache_path(key)
        with open(path, "wb") as f:
            pickle.dump(value, f, protocol=pickle.HIGHEST_PROTOCOL)
    except Exception as e:
        raise CacheError(f"Cache write failed: {e}") from e


def bucket_dist(dist: float) -> int:
    """Round a radius up to the next download size (at most ~19% larger)."""
    if dist <= BASE_DIST:
        return BASE_DIST
    steps = math.ceil(4 * math.log2(dist / BASE_DIST) - 1e-9)
    return math.ceil(BASE_DIST * 2 ** (steps / 4) - 1e-6)


def _covering_entry(prefix: str, suffix: str, dist: float):
    """Find the smallest cached area '<prefix>_<dist><suffix>' that covers dist."""
    pattern = os.path.join(glob.escape(str(CACHE_DIR)), f"{glob.escape(prefix)}_*{glob.escape(suffix)}.pkl")
    best = None
    for path in glob.glob(pattern):
        key = Path(path).stem
        dist_str = key[len(prefix) + 1:len(key) - len(suffix)]
        if not _DIST_RE.fullmatch(dist_str):
            continue
        cached_dist = float(dist_str)
        if cached_dist >= dist and (best is None or cached_dist < best[1]):
            best = (key, cached_dist)
    return best


def _cropped(data, area_dist, dist, crop):
    if data is None or (isinstance(data, str) and data == NO_DATA):
        return None
    return crop(data, dist) if area_dist > dist else data


def load_area(prefix: str, suffix: str, dist: float, download, crop):
    """
    Load the data within dist of a center point, from the cache if possible.

    Args:
        prefix: Cache key before the radius, e.g. 'graph_<lat>_<lon>'
        suffix: Cache key after the radius, e.g. '_natural_waterway' (or '')
        dist: Requested radius in meters
        download: Function(radius) returning the data, or None if there is none.
            Errors it raises are passed on and not cached.
        crop: Function(data, radius) cutting a larger area down to the radius

    Returns:
        (data or None, True if it came from the cache)
    """
    hit = _covering_entry(prefix, suffix, dist)
    if hit is not None:
        key, cached_dist = hit
        return _cropped(cache_get(key), cached_dist, dist, crop), True

    fetch_dist = bucket_dist(dist)
    data = download(fetch_dist)
    try:
        cache_set(f"{prefix}_{fetch_dist}{suffix}", NO_DATA if data is None else data)
    except CacheError as e:
        print(e)
    return _cropped(data, fetch_dist, dist, crop), False


def crop_graph(g, point, dist):
    """Cut a street network down to what graph_from_point(point, dist, dist_type='bbox') returns."""
    bbox = ox.utils_geo.bbox_from_point(point, dist)
    g = ox.truncate.truncate_graph_bbox(g, bbox, truncate_by_edge=True)
    return ox.truncate.largest_component(g)


def crop_features(gdf, point, dist):
    """Keep the features that features_from_point(point, dist) returns; None if none are left."""
    area = box(*ox.utils_geo.bbox_from_point(point, dist))
    gdf = gdf[gdf.intersects(area)]
    return gdf if len(gdf) else None
