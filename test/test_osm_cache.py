"""Tests for the OpenStreetMap area cache (no network access)."""

import geopandas as gpd
import networkx as nx
import pytest
from shapely.geometry import Point

from maptoposter import osm_cache

CENTER = (47.0, 12.0)


@pytest.fixture(autouse=True)
def cache_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(osm_cache, "CACHE_DIR", tmp_path)
    return tmp_path


def no_download(dist):
    pytest.fail(f"unexpected download ({dist} m)")


def keep(data, dist):
    return data


@pytest.mark.parametrize("dist", [100, 250, 612.5, 1000, 1333.3, 4000, 12345])
def test_bucket_dist_rounds_up_by_at_most_a_fourth_octave(dist):
    bucket = osm_cache.bucket_dist(dist)
    assert isinstance(bucket, int)
    assert bucket >= dist
    assert bucket <= max(250, dist * 2 ** 0.25) + 1


def test_bucket_dist_keeps_exact_steps():
    assert osm_cache.bucket_dist(1000) == 1000
    assert osm_cache.bucket_dist(2000) == 2000


def test_nearby_sizes_share_a_bucket():
    assert osm_cache.bucket_dist(900) == osm_cache.bucket_dist(990)


def test_downloads_the_bucket_and_crops_to_the_request():
    downloads, crops = [], []

    def download(dist):
        downloads.append(dist)
        return f"area {dist}"

    def crop(data, dist):
        crops.append((data, dist))
        return "cropped"

    data, cached = osm_cache.load_area("graph_1_2", "", 900, download, crop)
    bucket = osm_cache.bucket_dist(900)
    assert (data, cached) == ("cropped", False)
    assert downloads == [bucket]
    assert crops == [(f"area {bucket}", 900)]


def test_smaller_request_reuses_a_larger_cached_area():
    osm_cache.cache_set("graph_1_2_4000", "big")
    crops = []

    def crop(data, dist):
        crops.append((data, dist))
        return "cropped"

    assert osm_cache.load_area("graph_1_2", "", 500, no_download, crop) == ("cropped", True)
    assert crops == [("big", 500)]


def test_exact_cached_area_is_not_cropped():
    osm_cache.cache_set("graph_1_2_1000.0", "exact")  # key format of older versions
    crop = lambda data, dist: pytest.fail("no crop")  # noqa: E731
    assert osm_cache.load_area("graph_1_2", "", 1000, no_download, crop) == ("exact", True)


def test_smallest_covering_area_is_used():
    for dist in (500, 2000, 8000):
        osm_cache.cache_set(f"water_1_2_{dist}_natural", f"water {dist}")
    data, _ = osm_cache.load_area("water_1_2", "_natural", 1500, no_download, lambda d, _: d)
    assert data == "water 2000"


def test_other_places_and_tags_are_not_reused():
    osm_cache.cache_set("water_1_2_8000_natural", "other tags")
    osm_cache.cache_set("water_1_3_8000_natural_waterway", "other place")
    osm_cache.cache_set("water_1_2_100_natural_waterway", "too small")
    data, cached = osm_cache.load_area("water_1_2", "_natural_waterway", 500, lambda d: "fresh", keep)
    assert (data, cached) == ("fresh", False)


def test_no_data_is_cached():
    data, _ = osm_cache.load_area("parks_1_2", "_leisure", 500, lambda d: None, keep)
    assert data is None
    assert osm_cache.load_area("parks_1_2", "_leisure", 500, no_download, keep) == (None, True)
    assert osm_cache.load_area("parks_1_2", "_leisure", 300, no_download, keep) == (None, True)


def test_failed_download_is_not_cached():
    def fail(dist):
        raise RuntimeError("server down")

    with pytest.raises(RuntimeError):
        osm_cache.load_area("graph_1_2", "", 500, fail, keep)
    assert osm_cache.load_area("graph_1_2", "", 500, lambda d: "fresh", keep) == ("fresh", False)


def test_crop_graph_keeps_bbox_plus_edge_neighbors_in_largest_component():
    g = nx.MultiDiGraph(crs="epsg:4326")
    lons = {1: 12.0, 2: 12.005, 3: 12.01, 4: 12.05, 5: 12.06, 6: 12.002}
    for node, lon in lons.items():
        g.add_node(node, x=lon, y=47.0)
    for u, v in [(1, 2), (2, 3), (3, 4), (4, 5)]:
        g.add_edge(u, v)
    # node 6 is inside the bbox but not connected to the rest

    cropped = osm_cache.crop_graph(g, CENTER, 1000)
    assert set(cropped.nodes) == {1, 2, 3, 4}


def test_crop_features_keeps_intersecting_geometries():
    gdf = gpd.GeoDataFrame(
        {"name": ["in", "out"]},
        geometry=[Point(12.001, 47.001), Point(12.1, 47.1)],
        crs="epsg:4326",
    )
    cropped = osm_cache.crop_features(gdf, CENTER, 1000)
    assert list(cropped["name"]) == ["in"]


def test_crop_features_returns_none_when_nothing_is_left():
    gdf = gpd.GeoDataFrame(geometry=[Point(12.1, 47.1)], crs="epsg:4326")
    assert osm_cache.crop_features(gdf, CENTER, 1000) is None
