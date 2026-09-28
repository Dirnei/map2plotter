"""Tests for the poster CLI: output control, cache-only mode, edits (no network access)."""

import json
import xml.etree.ElementTree as ET

import networkx as nx
import numpy as np
import pytest

import map2plotter.poster as cmp
from map2plotter import osm_cache

LAT, LON = 48.0, 11.0
THEME = {
    "name": "Test",
    "bg": "#FFFFFF",  # Not a pen colour: ignored (older themes still have it)
    "text": "#FF0000",
    "gradient_color": "#FFFFFF",
    "water": "#0000FF",
    "parks": "#00FF00",
    "road_motorway": "#000000",
    "road_primary": "#000000",
    "road_secondary": "#000000",
    "road_tertiary": "#000000",
    "road_residential": "#000000",
    "road_default": "#000000",
}


def make_graph():
    """A tiny street network: a grid of roads around the centre."""
    g = nx.MultiDiGraph(crs="EPSG:4326")
    d = 0.02
    n = 0
    for i, off in enumerate(np.linspace(-d, d, 9)):
        hw = "motorway" if i == 4 else "residential"
        g.add_node(n, x=LON - d, y=LAT + off)
        g.add_node(n + 1, x=LON + d, y=LAT + off)
        g.add_edge(n, n + 1, highway=hw)
        g.add_node(n + 2, x=LON + off, y=LAT - d)
        g.add_node(n + 3, x=LON + off, y=LAT + d)
        g.add_edge(n + 2, n + 3, highway="primary" if i == 4 else "residential")
        n += 4
    return g


@pytest.fixture
def cli(tmp_path, monkeypatch):
    """Run main() offline with a test theme and a fake street network."""
    themes = tmp_path / "themes"
    themes.mkdir()
    (themes / "test.json").write_text(json.dumps(THEME), encoding="utf-8")
    monkeypatch.setattr(cmp, "THEMES_DIR", str(themes))
    monkeypatch.setattr(cmp, "POSTERS_DIR", str(tmp_path / "posters"))
    monkeypatch.setattr(osm_cache, "CACHE_DIR", tmp_path / "cache")
    monkeypatch.setattr(cmp, "CACHE_ONLY", False)
    calls = []

    def fake_graph(point, dist):
        calls.append(("graph", dist))
        return make_graph()

    monkeypatch.setattr(cmp, "fetch_graph", fake_graph)
    monkeypatch.setattr(cmp, "fetch_features", lambda *a, **k: None)

    def run(*args):
        base = ["-c", "Test", "-C", "Land", "-t", "test", "--latitude", str(LAT), "--longitude", str(LON), "-d", "1500"]
        cmp.main(base + list(args))

    run.calls = calls
    run.tmp = tmp_path
    return run


def exit_code(fn, *args):
    with pytest.raises(SystemExit) as e:
        fn(*args)
    return e.value.code


SVG_NS = "{http://www.w3.org/2000/svg}"


# --- Output --------------------------------------------------------------------


def test_output_path(cli):
    out = cli.tmp / "previews" / "p.svg"
    cli("--output", str(out))
    assert ET.parse(out).getroot().tag == f"{SVG_NS}svg"
    assert not (cli.tmp / "posters").exists() or not any((cli.tmp / "posters").iterdir())


def test_default_output_is_svg_in_posters(cli):
    cli()
    files = list((cli.tmp / "posters").iterdir())
    assert len(files) == 1 and files[0].suffix == ".svg" and files[0].name.startswith("test_test_")


def test_large_size_not_clamped(cli):
    out = cli.tmp / "big.svg"
    cli("-W", "841", "-H", "1189", "--output", str(out))
    root = ET.parse(out).getroot()
    assert (root.get("width"), root.get("height")) == ("841mm", "1189mm")


@pytest.mark.parametrize("args", [("--format", "png"), ("-f", "plotter"), ("--dpi", "300"), ("--font-family", "X")])
def test_print_options_rejected(cli, args):
    assert exit_code(cli, *args) == 2  # argparse: unknown option
    assert cli.calls == []


@pytest.mark.parametrize(
    "args",
    [
        ("--output", "out.png"),
        ("--output", "out.pdf"),
        ("--all-themes", "--output", "out.svg"),
        ("--pen-width", "0"),
        ("--pen-width", "0.5", "--parks-spacing", "0.3"),
        ("--pen-width", "0.5", "--water-spacing", "0.2"),
    ],
)
def test_invalid_options_rejected_before_download(cli, args):
    assert exit_code(cli, *args) not in (0, None)
    assert cli.calls == []


def test_png_output_error_message(cli, capsys):
    assert exit_code(cli, "--output", "out.png") == 1
    assert "must be an .svg file" in capsys.readouterr().out


def test_invalid_fill_mode_rejected(cli):
    assert exit_code(cli, "--water-fill", "spiral") == 2


def test_broken_edits_file_rejected(cli):
    bad = cli.tmp / "broken.json"
    bad.write_text("{nope", encoding="utf-8")
    assert exit_code(cli, "--edits", str(bad)) == 1
    assert cli.calls == []


def test_plotter_fill_options(cli):
    out = cli.tmp / "p.svg"
    cli("--water-fill", "concentric", "--water-spacing", "1", "--water-outline", "--output", str(out))
    assert out.read_text(encoding="utf-8").startswith("<?xml")


# --- Cache-only ---------------------------------------------------------------


@pytest.fixture
def offline(tmp_path, monkeypatch):
    monkeypatch.setattr(osm_cache, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(cmp, "CACHE_ONLY", True)

    def no_network(*a, **k):
        pytest.fail("network access in cache-only mode")

    monkeypatch.setattr(cmp, "overpass_download", no_network)
    monkeypatch.setattr(cmp, "Nominatim", no_network)
    return tmp_path


def test_cache_only_uses_cached_graph(offline):
    g = make_graph()
    osm_cache.cache_set(f"graph_{LAT}_{LON}_1000", g)
    assert cmp.fetch_graph((LAT, LON), 1000).number_of_edges() == g.number_of_edges()


def test_cache_only_missing_graph_fails(offline):
    with pytest.raises(RuntimeError, match="not cached"):
        cmp.fetch_graph((LAT, LON), 1000)


def test_cache_only_missing_water_warns(offline, capsys):
    assert cmp.fetch_features((LAT, LON), 1000, {"natural": "water"}, "water") is None
    assert "water" in capsys.readouterr().out


def test_downloads_and_geocoding_identify_map2plotter(tmp_path, monkeypatch):
    monkeypatch.setattr(osm_cache, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(cmp, "CACHE_ONLY", False)
    monkeypatch.setattr(cmp.time, "sleep", lambda s: None)
    agents = []

    class FakeNominatim:
        def __init__(self, user_agent, timeout):
            agents.append(user_agent)

        def geocode(self, query):
            return type("Location", (), {"latitude": 38.7, "longitude": -9.1, "address": query})()

    monkeypatch.setattr(cmp, "Nominatim", FakeNominatim)
    assert cmp.get_coordinates("Lisbon", "Portugal") == (38.7, -9.1)
    assert agents == [cmp.USER_AGENT]
    assert cmp.ox.settings.http_user_agent == cmp.USER_AGENT
    assert "city_map_poster" not in cmp.USER_AGENT and "originalankur" not in cmp.USER_AGENT


def test_cache_only_coordinates(offline):
    with pytest.raises(osm_cache.NotCachedError):
        cmp.get_coordinates("Lisbon", "Portugal")
    osm_cache.cache_set("coords_lisbon_portugal", (38.7, -9.1))
    assert cmp.get_coordinates("Lisbon", "Portugal") == (38.7, -9.1)


def test_cache_only_main_exits_nonzero(offline, monkeypatch):
    monkeypatch.setattr(cmp, "THEMES_DIR", cmp.paths.THEMES_DIR)
    code = exit_code(cmp.main, ["-c", "Lisbon", "-C", "Portugal", "--cache-only", "-o", str(offline / "x.svg")])
    assert code == 1


# --- Colour overrides -------------------------------------------------------------


@pytest.mark.parametrize("value, fragment", [
    ("buildings=#000000", "buildings"),
    ("bg=#000000", "bg"),
    ("gradient_color=#000000", "gradient_color"),
    ("water=blue", "blue"),
    ("water", "KEY=#RRGGBB"),
    ("water=#12345", "#12345"),
])
def test_invalid_color_rejected_before_download(cli, capsys, value, fragment):
    assert exit_code(cli, "--color", value) == 1
    assert fragment in capsys.readouterr().out
    assert cli.calls == []


def test_color_last_value_wins():
    assert cmp.parse_color_overrides(["water=#111111", "water=#ABCDEF"]) == {"water": "#abcdef"}


def test_color_override_in_plotter_svg(cli, monkeypatch):
    import geopandas as gpd
    from shapely.geometry import box

    water = gpd.GeoDataFrame({"geometry": [box(LON - 0.005, LAT - 0.005, LON + 0.005, LAT + 0.005)]}, crs="EPSG:4326")
    monkeypatch.setattr(cmp, "fetch_features", lambda point, dist, tags, name: water if name == "water" else None)
    out = cli.tmp / "p.svg"
    cli("--color", "water=#1F5FA8", "--output", str(out))
    layers = {
        g.get("stroke"): [k.get("data-key") for k in g.findall(f"{SVG_NS}g")]
        for g in ET.parse(out).getroot().findall(f"{SVG_NS}g")
    }
    assert "water" in layers["#1f5fa8"]
    assert "text" in layers[THEME["text"].lower()]  # others keep the theme colour


# --- Dependencies -------------------------------------------------------------------


def test_matplotlib_not_imported():
    """Plotter-only: neither the CLI nor the web server needs matplotlib (a fresh interpreter proves it)."""
    import subprocess
    import sys

    code = "import sys, map2plotter.poster, map2plotter.web; print('matplotlib' in sys.modules)"
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True).stdout
    assert out.strip() == "False"
