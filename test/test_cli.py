"""Tests for the poster CLI: output control, cache-only mode, edits (no network access)."""

import json

import matplotlib

matplotlib.use("Agg")

import networkx as nx  # noqa: E402
import numpy as np  # noqa: E402
import pytest  # noqa: E402
from PIL import Image  # noqa: E402

import create_map_poster as cmp  # noqa: E402
import osm_cache  # noqa: E402

LAT, LON = 48.0, 11.0
THEME = {
    "name": "Test",
    "bg": "#FFFFFF",
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


# --- Output path and dpi ------------------------------------------------------


def test_output_path_and_dpi(cli):
    out = cli.tmp / "previews" / "p.png"
    cli("-f", "png", "-W", "254", "-H", "254", "--dpi", "50", "--output", str(out))
    assert Image.open(out).size == (500, 500)
    assert not (cli.tmp / "posters").exists() or not any((cli.tmp / "posters").iterdir())


@pytest.mark.parametrize(
    "args",
    [
        ("-f", "pdf", "--output", "out.png"),
        ("-f", "plotter", "--output", "out.png"),
        ("--all-themes", "--output", "out.png"),
        ("--dpi", "0"),
        ("-f", "plotter", "--pen-width", "0.5", "--parks-spacing", "0.3"),
        ("-f", "plotter", "--pen-width", "0.5", "--water-spacing", "0.2"),
    ],
)
def test_invalid_options_rejected_before_download(cli, args):
    assert exit_code(cli, *args) not in (0, None)
    assert cli.calls == []


def test_invalid_fill_mode_rejected(cli):
    assert exit_code(cli, "-f", "plotter", "--water-fill", "spiral") == 2


def test_broken_edits_file_rejected(cli):
    bad = cli.tmp / "broken.json"
    bad.write_text("{nope", encoding="utf-8")
    assert exit_code(cli, "--edits", str(bad)) == 1
    assert cli.calls == []


def test_plotter_fill_options(cli):
    out = cli.tmp / "p.svg"
    cli("-f", "plotter", "--water-fill", "concentric", "--water-spacing", "1", "--water-outline", "--output", str(out))
    assert out.read_text(encoding="utf-8").startswith("<?xml")


# --- Raster edits --------------------------------------------------------------


def render_png(cli, name, edits=None):
    args = ["-f", "png", "-W", "254", "-H", "254", "--dpi", "50", "--output", str(cli.tmp / name)]
    if edits is not None:
        path = cli.tmp / f"{name}.json"
        path.write_text(json.dumps(edits), encoding="utf-8")
        args += ["--edits", str(path)]
    cli(*args)
    return np.asarray(Image.open(cli.tmp / name).convert("RGB")).astype(int)


def red_rows(img, top, bottom):
    """Rows (in [top, bottom)) that contain text-coloured pixels."""
    band = img[top:bottom]
    mask = (band[:, :, 0] - band[:, :, 1] > 40) & (band[:, :, 0] - band[:, :, 2] > 40)
    return np.nonzero(mask.any(axis=1))[0] + top


def test_raster_erase_shows_background(cli):
    base = render_png(cli, "base.png")
    region = (slice(160, 284), slice(160, 333))  # inside rows/cols 80..145 mm / 80..170 mm at 50 dpi
    assert (base[region] != 255).any(), "fixture must draw roads inside the erase region"
    edits = {"erase": [[[80, 80], [170, 80], [170, 145], [80, 145]]]}
    img = render_png(cli, "erased.png", edits)
    assert (img[region] == 255).all()
    assert (img[:, 400:] == base[:, 400:]).all()  # outside the region unchanged


def test_raster_move_city(cli):
    base = render_png(cli, "base.png")
    moved = render_png(cli, "moved.png", {"text": {"city": {"dy": -10}}})
    rows_base = red_rows(base, 360, 450)
    rows_moved = red_rows(moved, 300, 450)
    assert len(rows_base) and len(rows_moved)
    assert rows_moved.min() - rows_base.min() == pytest.approx(-20, abs=2)  # 10 mm at 50 dpi


def test_raster_hide_coords_keeps_attribution(cli):
    base = render_png(cli, "base.png")
    img = render_png(cli, "hidden.png", {"text": {"coords": {"hidden": True}}})
    coords_band = (slice(452, 475), slice(100, 400))
    assert len(red_rows(base[coords_band], 0, 23))
    assert not len(red_rows(img[coords_band], 0, 23))
    attribution = (slice(480, 500), slice(330, 500))
    assert (img[attribution] == base[attribution]).all()
    assert (img[attribution] != 255).any()


def test_raster_hidden_road_class(cli):
    base = render_png(cli, "base.png")
    hidden = render_png(
        cli, "noroads.png",
        {"hidden_layers": ["road_motorway", "road_primary", "road_residential", "road_default"]},
    )
    middle = (slice(150, 300), slice(100, 400))
    assert (base[middle] != 255).any()
    assert (hidden[middle] == 255).all()


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


def test_cache_only_coordinates(offline):
    with pytest.raises(osm_cache.NotCachedError):
        cmp.get_coordinates("Lisbon", "Portugal")
    osm_cache.cache_set("coords_lisbon_portugal", (38.7, -9.1))
    assert cmp.get_coordinates("Lisbon", "Portugal") == (38.7, -9.1)


def test_cache_only_main_exits_nonzero(offline, monkeypatch):
    monkeypatch.setattr(cmp, "THEMES_DIR", "themes")
    code = exit_code(cmp.main, ["-c", "Lisbon", "-C", "Portugal", "--cache-only", "-o", str(offline / "x.png")])
    assert code == 1
