"""Tests for the web UI backend (fake CLI scripts, no network access)."""

import json
import os
import sys
import textwrap
import time

import pytest
from fastapi.testclient import TestClient

from map2plotter import web

THEME = {"name": "Noir", "description": "Dark", "bg": "#000000", "text": "#FFFFFF"}
PARIS = {"city": "Paris", "country": "France"}


@pytest.fixture
def env(tmp_path, monkeypatch):
    """Point the app at temporary posters/themes/work directories and a fake CLI."""
    posters = tmp_path / "posters"
    themes = tmp_path / "themes"
    posters.mkdir()
    themes.mkdir()
    (themes / "noir.json").write_text(json.dumps(THEME), encoding="utf-8")
    (themes / "terracotta.json").write_text(
        json.dumps({"name": "Terracotta", "description": "Warm", "bg": "#F5EDE4", "water": "#A8C4C4"}),
        encoding="utf-8",
    )
    monkeypatch.setattr(web, "POSTERS_DIR", posters)
    monkeypatch.setattr(web, "THEMES_DIR", themes)
    monkeypatch.setattr(web, "WORK_DIR", tmp_path / "work")
    monkeypatch.setattr(web, "CURRENT_JOB", None)
    monkeypatch.setattr(web, "_START_LOCK", None)

    def fake_cli(body):
        script = tmp_path / "fake_cli.py"
        script.write_text(
            f"import sys, time, pathlib\nPOSTERS = pathlib.Path({str(posters)!r})\n"
            "OUT = pathlib.Path(sys.argv[sys.argv.index('--output') + 1]) if '--output' in sys.argv else None\n"
            + textwrap.dedent(body),
            encoding="utf-8",
        )
        monkeypatch.setattr(web, "CLI_COMMAND", [sys.executable, "-u", str(script)])

    with TestClient(web.app) as client:
        yield client, posters, fake_cli


SUCCESS = """
print("args:", " ".join(sys.argv[1:]))
print("Downloading street network")
sys.stdout.write("Fetching 50%|#####\\rFetching 100%|##########\\n")
print("✓ Done")
if OUT:
    OUT.write_bytes(b"preview " + " ".join(sys.argv[1:]).encode())
else:
    (POSTERS / "paris_noir_1.png").write_bytes(b"\\x89PNG fake")
"""

FAILURE = """
print("✗ Error: something broke")
sys.exit(1)
"""

NOT_CACHED = """
print("✗ Error: Map data for this area is not cached; run without --cache-only to download it")
sys.exit(1)
"""

SLOW = """
print("started", flush=True)
time.sleep(30)
"""


def run_to_end(client, job_id):
    """Read the SSE stream until the final status event; return (lines, status)."""
    lines, status = [], None
    with client.stream("GET", f"/api/jobs/{job_id}/events") as res:
        for raw in res.iter_lines():
            if not raw.startswith("data: "):
                continue
            msg = json.loads(raw[6:])
            if msg["type"] == "line":
                lines.append(msg["text"])
            else:
                status = msg
                break
    return lines, status


def wait_for_output(timeout=10):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if web.CURRENT_JOB and web.CURRENT_JOB.lines:
            return
        time.sleep(0.05)
    raise AssertionError("no output from job")


def load_paris(client, fake_cli, **extra):
    fake_cli(SUCCESS)
    job = client.post("/api/load", json={**PARIS, **extra}).json()
    lines, status = run_to_end(client, job["id"])
    assert status["status"] == "succeeded", lines
    return job, status


# --- Themes and validation --------------------------------------------------


def test_themes_listed(env):
    client, _, _ = env
    themes = client.get("/api/themes").json()
    assert [t["id"] for t in themes] == ["noir", "terracotta"]
    assert themes[0]["name"] == "Noir"
    assert themes[0]["colors"] == {"bg": "#000000", "text": "#FFFFFF"}


def test_missing_city_rejected(env):
    client, _, _ = env
    res = client.post("/api/load", json={"country": "France"})
    assert res.status_code == 422
    assert "city" in res.json()["errors"]
    assert web.CURRENT_JOB is None


@pytest.mark.parametrize("data, field", [
    ({"latitude": "48.8"}, "longitude"),
    ({"latitude": "abc", "longitude": "2.3"}, "latitude"),
    ({"distance": 0}, "distance"),
    ({"width": 0}, "width"),
    ({"theme": "missing"}, "theme"),
    ({"overpass_url": "not a url"}, "overpass_url"),
])
def test_location_validation(env, data, field):
    client, _, _ = env
    res = client.post("/api/load", json={**PARIS, **data})
    assert res.status_code == 422
    assert field in res.json()["errors"]


@pytest.mark.parametrize("data, field", [
    ({"format": "plotter", "pen_width": 0.5, "hatch_spacing": 0.2}, "hatch_spacing"),
    ({"format": "plotter", "pen_width": 0.5, "water_spacing": 0.3}, "water_spacing"),
    ({"format": "plotter", "pen_width": 0.5, "parks_spacing": 0.3}, "parks_spacing"),
    ({"format": "plotter", "water_fill": "spiral"}, "water_fill"),
    ({"theme": "missing"}, "theme"),
    ({"format": "gif"}, "format"),
    ({"edits": {"hidden_layers": ["buildings"]}}, "edits"),
    ({"colors": {"buildings": "#000000"}}, "colors"),
    ({"colors": {"water": "blue"}}, "colors"),
])
def test_customize_validation(env, data, field):
    _, errors = web.validate_customize(data)
    assert field in errors


def test_unknown_theme_allowed_with_all_themes(env):
    _, errors = web.validate_customize({"theme": "x", "all_themes": True})
    assert not errors


def test_any_positive_print_size_accepted(env):
    loc, errors = web.validate_location({**PARIS, "width": 841, "height": 1189})
    assert not errors and loc.mode == "print"
    _, errors = web.validate_location({**PARIS, "width": 0})
    assert "width" in errors
    loc, errors = web.validate_location({**PARIS, "mode": "plotter", "width": 841, "height": 1189})
    assert not errors and loc.mode == "plotter"


def test_png_export_pixel_limit(env):
    client, _, fake_cli = env
    load_paris(client, fake_cli, width=1000, height=1500)
    res = client.post("/api/export", json={"format": "png"})
    assert res.status_code == 422 and "293 dpi" in res.json()["errors"]["dpi"]
    # Previews are rendered scaled down and are not limited
    job = client.post("/api/preview", json={"format": "png"}).json()
    _, status = run_to_end(client, job["id"])
    assert status["status"] == "succeeded"
    args = web.CURRENT_JOB.args
    assert args[args.index("--dpi") + 1] == str(web.preview_dpi(*web.preview_size(web.SESSION.location)))
    # A fitting dpi, or a vector format, is accepted
    job = client.post("/api/export", json={"format": "png", "dpi": 293}).json()
    run_to_end(client, job["id"])
    assert "--dpi 293" in job["command"]
    job = client.post("/api/export", json={"format": "svg"}).json()
    run_to_end(client, job["id"])
    assert "--format svg" in job["command"] and "--dpi" not in job["command"]


def test_format_follows_workflow(env):
    plotter, _ = web.validate_location({**PARIS, "mode": "plotter", "width": 600, "height": 900})
    custom, errors = web.validate_customize({"format": "png"}, plotter)
    assert not errors and custom.format == "plotter"
    printing, _ = web.validate_location(PARIS)
    _, errors = web.validate_customize({"format": "plotter"}, printing)
    assert "format" in errors


def test_plotter_workflow_load_and_preview(env):
    client, _, fake_cli = env
    job, status = load_paris(client, fake_cli, mode="plotter", width=600, height=900)
    assert "--format plotter" in job["command"] and "--dpi" not in job["command"]
    assert "--width 600 --height 900" in job["command"]
    assert status["preview"]["type"] == "svg"
    assert client.get("/api/session").json()["location"]["mode"] == "plotter"
    job = client.post("/api/preview", json={"format": "png", "theme": "noir"}).json()
    _, status = run_to_end(client, job["id"])
    assert status["status"] == "succeeded" and status["preview"]["type"] == "svg"
    assert "--format plotter" in job["command"]


# --- Command building --------------------------------------------------------


def _loc(**kwargs):
    return web.LocationConfig(**{**PARIS, **kwargs})


def _custom(**kwargs):
    return web.CustomizeConfig(**kwargs)


def test_export_args_basic():
    args = web.location_args(_loc(distance=10000)) + web.customize_args(_custom(theme="noir", format="svg"))
    assert args == [
        "--city", "Paris", "--country", "France", "--distance", "10000", "--width", "300", "--height", "400",
        "--overpass-url", "auto", "--theme", "noir", "--format", "svg",
    ]
    assert web.display_command(args).startswith("map2plotter --city Paris")


def test_args_plotter_and_optional_fields():
    args = web.location_args(_loc(latitude="40.7", longitude="-73.9", width=841, height=1189))
    args += web.customize_args(_custom(
        format="plotter", pen_width=0.5, hatch_spacing=1, display_city="東京", all_themes=True,
        water_fill="concentric", water_spacing=1, water_outline=True,
    ))
    assert "--all-themes" in args and "--theme" not in args
    assert "--longitude=-73.9" in args
    assert args[args.index("--display-city") + 1] == "東京"
    assert args[args.index("--width") + 1] == "841" and args[args.index("--height") + 1] == "1189"
    assert args[args.index("--format"):] == [
        "--format", "plotter", "--pen-width", "0.5", "--hatch-spacing", "1", "--water-spacing", "1",
        "--water-fill", "concentric", "--water-outline",
    ]


def test_plotter_options_omitted_for_other_formats():
    args = web.customize_args(_custom(format="png", hatch_spacing=1, water_outline=True))
    assert "--hatch-spacing" not in args and "--pen-width" not in args and "--water-outline" not in args


def test_no_shell_interpretation():
    args = web.location_args(_loc(city="Paris; rm -rf /"))
    assert args[:2] == ["--city", "Paris; rm -rf /"]


def test_preview_size_and_dpi():
    assert web.preview_size(_loc(width=841, height=1189)) == pytest.approx((500 * 841 / 1189, 500))
    assert web.preview_size(_loc()) == (300, 400)
    assert web.preview_dpi(300, 400) == round(2000 / (400 / 25.4))


# --- Load, preview, export ------------------------------------------------------


def test_load_streams_and_renders_preview(env):
    client, posters, fake_cli = env
    assert client.get("/api/session").json()["loaded"] is False
    job, status = load_paris(client, fake_cli)
    assert job["kind"] == "load"
    assert "--output" in job["command"] and "--dpi" in job["command"]
    assert "--cache-only" not in job["command"]
    assert status["preview"]["type"] == "png"

    session = client.get("/api/session").json()
    assert session["loaded"] and session["location"]["city"] == "Paris"
    res = client.get("/api/preview")
    assert res.status_code == 200 and res.content.startswith(b"preview ")
    assert list(posters.iterdir()) == []  # previews stay out of posters/


def test_load_streams_output(env):
    client, _, fake_cli = env
    fake_cli(SUCCESS)
    job = client.post("/api/load", json=PARIS).json()
    lines, status = run_to_end(client, job["id"])
    assert "Downloading street network" in lines
    assert "Fetching 100%|##########" in lines  # \r-separated progress updates become lines
    replay, _ = run_to_end(client, job["id"])
    assert replay == lines


def test_failed_load_keeps_output_and_stays_locked(env):
    client, _, fake_cli = env
    fake_cli(FAILURE)
    job = client.post("/api/load", json=PARIS).json()
    lines, status = run_to_end(client, job["id"])
    assert status["status"] == "failed" and status["returncode"] == 1
    assert "✗ Error: something broke" in lines
    assert client.get("/api/session").json()["loaded"] is False
    assert client.post("/api/preview", json={}).status_code == 409


def test_preview_before_load_rejected(env):
    client, _, _ = env
    res = client.post("/api/preview", json={"theme": "noir"})
    assert res.status_code == 409
    assert "Load the map" in res.json()["detail"]
    assert client.post("/api/export", json={}).status_code == 409


def test_preview_uses_cache_only_and_edits(env):
    client, _, fake_cli = env
    load_paris(client, fake_cli)
    edits = {"erase": [[[1, 1], [5, 1], [5, 5]]]}
    job = client.post("/api/preview", json={"theme": "noir", "edits": edits}).json()
    _, status = run_to_end(client, job["id"])
    assert status["status"] == "succeeded"
    args = web.CURRENT_JOB.args
    assert "--cache-only" in args and "--output" in args and "--edits" in args
    assert args[args.index("--theme") + 1] == "noir"
    assert args[args.index("--format") + 1] == "png"
    saved = json.loads(open(args[args.index("--edits") + 1], encoding="utf-8").read())
    assert saved["erase"] == edits["erase"]
    assert status["preview"]["url"] != job["preview"]["url"]  # new version


def test_plotter_preview_is_svg(env):
    client, _, fake_cli = env
    load_paris(client, fake_cli, mode="plotter")
    job = client.post("/api/preview", json={"format": "plotter", "water_outline": True}).json()
    _, status = run_to_end(client, job["id"])
    assert status["preview"]["type"] == "svg"
    args = web.CURRENT_JOB.args
    assert "--water-outline" in args and "--dpi" not in args
    assert client.get("/api/preview").headers["content-type"].startswith("image/svg+xml")


def test_empty_edits_not_passed(env):
    client, _, fake_cli = env
    load_paris(client, fake_cli)
    job = client.post("/api/preview", json={"edits": {}}).json()
    run_to_end(client, job["id"])
    assert "--edits" not in web.CURRENT_JOB.args


def test_not_cached_preview_reported(env):
    client, _, fake_cli = env
    load_paris(client, fake_cli)
    fake_cli(NOT_CACHED)
    job = client.post("/api/preview", json={}).json()
    _, status = run_to_end(client, job["id"])
    assert status["status"] == "failed" and status["not_cached"] is True
    assert client.get("/api/preview").status_code == 200  # last good preview kept


def test_export_writes_poster(env):
    client, posters, fake_cli = env
    load_paris(client, fake_cli, distance=10000)
    job = client.post("/api/export", json={"theme": "noir", "format": "svg"}).json()
    lines, status = run_to_end(client, job["id"])
    assert status["status"] == "succeeded"
    assert status["files"] == ["paris_noir_1.png"]
    for part in ["--city Paris", "--country France", "--theme noir", "--distance 10000", "--format svg",
                 "--cache-only", "--width 300", "--height 400"]:
        assert part in job["command"]
    assert "--output" not in job["command"]
    names = [p["name"] for p in client.get("/api/posters").json()]
    assert names == ["paris_noir_1.png"]


def test_newer_preview_replaces_running_preview(env):
    client, _, fake_cli = env
    load_paris(client, fake_cli)
    fake_cli(SLOW)
    first = client.post("/api/preview", json={"theme": "noir"}).json()
    wait_for_output()
    fake_cli(SUCCESS)
    second = client.post("/api/preview", json={"theme": "terracotta"}).json()
    assert second["id"] != first["id"]
    _, status = run_to_end(client, second["id"])
    assert status["status"] == "succeeded"
    assert web.CURRENT_JOB.id == second["id"]


def test_concurrent_request_rejected_then_cancel(env):
    client, _, fake_cli = env
    load_paris(client, fake_cli)
    fake_cli(SLOW)
    first = client.post("/api/export", json={}).json()
    wait_for_output()

    assert client.post("/api/export", json={}).status_code == 409
    assert client.post("/api/preview", json={}).status_code == 409
    assert client.post("/api/load", json=PARIS).status_code == 409
    assert web.CURRENT_JOB.id == first["id"]

    cancelled = client.post(f"/api/jobs/{first['id']}/cancel").json()
    assert cancelled["status"] == "cancelled"

    fake_cli(SUCCESS)
    third = client.post("/api/export", json={})
    assert third.status_code == 200
    run_to_end(client, third.json()["id"])


def test_load_cancels_running_preview(env):
    client, _, fake_cli = env
    load_paris(client, fake_cli)
    fake_cli(SLOW)
    client.post("/api/preview", json={})
    wait_for_output()
    fake_cli(SUCCESS)
    res = client.post("/api/load", json={"city": "Rome", "country": "Italy"})
    assert res.status_code == 200
    run_to_end(client, res.json()["id"])
    assert client.get("/api/session").json()["location"]["city"] == "Rome"


def test_unknown_job_404(env):
    client, _, _ = env
    assert client.get("/api/jobs/nope/events").status_code == 404
    assert client.post("/api/jobs/nope/cancel").status_code == 404


def test_layout_boxes(env):
    client, _, fake_cli = env
    load_paris(client, fake_cli, latitude="48.85", longitude="2.35")
    body = client.post("/api/layout", json={"display_city": "Lutetia"}).json()
    assert body["width"] == 300 and body["height"] == 400
    minx, miny, maxx, maxy = body["boxes"]["city"]
    assert minx < 150 < maxx and 300 < miny < maxy < 400
    assert set(body["boxes"]) >= {"city", "country", "coords", "divider"}


# --- Posters -----------------------------------------------------------------


def test_history_newest_first(env):
    client, posters, _ = env
    now = time.time()
    for i, name in enumerate(["a.png", "b.svg", "c.pdf"]):
        path = posters / name
        path.write_bytes(b"x" * (i + 1))
        os.utime(path, (now - 100 + i * 10, now - 100 + i * 10))
    (posters / "notes.txt").write_text("ignore")
    (posters / "old").mkdir()
    (posters / "old" / "z.png").write_bytes(b"x")
    names = [p["name"] for p in client.get("/api/posters").json()]
    assert names == ["c.pdf", "b.svg", "a.png"]


def test_poster_served_inline_and_as_download(env):
    client, posters, _ = env
    (posters / "map.svg").write_text("<svg/>")
    res = client.get("/api/posters/map.svg")
    assert res.status_code == 200
    assert res.headers["content-type"].startswith("image/svg+xml")
    assert res.headers["content-disposition"].startswith("inline")
    res = client.get("/api/posters/map.svg?download=1")
    assert res.headers["content-disposition"].startswith("attachment")


@pytest.mark.parametrize("name", ["../pyproject.toml", "..%2Fpyproject.toml", "..%5Cpyproject.toml", "notes.txt"])
def test_unsafe_poster_names_rejected(env, name):
    client, posters, _ = env
    (posters / "notes.txt").write_text("secret")
    assert client.get(f"/api/posters/{name}").status_code == 404


def test_no_preview_404(env):
    client, _, _ = env
    assert client.get("/api/preview").status_code == 404


# --- OpenStreetMap servers -----------------------------------------------------


def test_overpass_url_normalized():
    loc, errors = web.validate_location({**PARIS, "overpass_url": "https://lz4.overpass-api.de/api/interpreter"})
    assert not errors
    args = web.location_args(loc)
    assert args[args.index("--overpass-url") + 1] == "https://lz4.overpass-api.de/api"


def test_server_list_and_default(env, monkeypatch):
    client, _, _ = env
    monkeypatch.delenv("OVERPASS_URL", raising=False)
    body = client.get("/api/overpass/servers").json()
    assert body["default"] == "auto"
    assert body["servers"][0]["url"] == "https://overpass-api.de/api"
    monkeypatch.setenv("OVERPASS_URL", "https://lz4.overpass-api.de/api/interpreter")
    assert client.get("/api/overpass/servers").json()["default"] == "https://lz4.overpass-api.de/api"


def test_server_check(env, monkeypatch):
    client, _, _ = env
    seen = []

    def fake_check(urls):
        seen.extend(urls)
        return [
            {"url": u, "ok": i == 1, "ms": 100, "error": None if i == 1 else "HTTP 504"} for i, u in enumerate(urls)
        ]

    monkeypatch.setattr(web.overpass, "check_servers", fake_check)
    body = client.post("/api/overpass/check", json={"custom": "https://my.example/api/interpreter"}).json()
    assert seen[-1] == "https://my.example/api"
    assert len(body) == len(web.overpass.SERVERS) + 1
    assert body[1]["ok"] and not body[0]["ok"]
    assert client.post("/api/overpass/check", json={"custom": "nope"}).status_code == 422


def test_export_passes_only_changed_colors(env):
    client, _, fake_cli = env
    load_paris(client, fake_cli, mode="plotter")
    base = web.theme_colors("terracotta")
    colors = {"bg": base["bg"], "water": "#1F5FA8"}  # bg unchanged, water changed
    job = client.post("/api/export", json={"theme": "terracotta", "colors": colors}).json()
    run_to_end(client, job["id"])
    args = web.CURRENT_JOB.args
    assert [args[i + 1] for i, a in enumerate(args) if a == "--color"] == ["water=#1f5fa8"]
    assert "--color 'water=#1f5fa8'" in job["command"]


def test_page_credits_original_project(env):
    client, _, _ = env
    html = client.get("/").text
    assert "<title>map2plotter</title>" in html
    assert 'href="https://github.com/originalankur/maptoposter"' in html
    assert 'href="https://github.com/Dirnei/map2plotter"' in html
