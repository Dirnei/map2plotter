"""Tests for the web UI backend (fake CLI scripts, no network access)."""

import json
import os
import textwrap
import time

import pytest
from fastapi.testclient import TestClient

import web_app

THEME = {"name": "Noir", "description": "Dark", "bg": "#000000", "text": "#FFFFFF"}


@pytest.fixture
def env(tmp_path, monkeypatch):
    """Point the app at temporary posters/themes directories and a fake CLI."""
    posters = tmp_path / "posters"
    themes = tmp_path / "themes"
    posters.mkdir()
    themes.mkdir()
    (themes / "noir.json").write_text(json.dumps(THEME), encoding="utf-8")
    (themes / "terracotta.json").write_text(
        json.dumps({"name": "Terracotta", "description": "Warm", "bg": "#F5EDE4", "water": "#A8C4C4"}),
        encoding="utf-8",
    )
    monkeypatch.setattr(web_app, "POSTERS_DIR", posters)
    monkeypatch.setattr(web_app, "THEMES_DIR", themes)
    monkeypatch.setattr(web_app, "CURRENT_JOB", None)

    def fake_cli(body):
        script = tmp_path / "fake_cli.py"
        script.write_text(
            f"import sys, time, pathlib\nPOSTERS = pathlib.Path({str(posters)!r})\n" + textwrap.dedent(body),
            encoding="utf-8",
        )
        monkeypatch.setattr(web_app, "CLI_SCRIPT", script)

    with TestClient(web_app.app) as client:
        yield client, posters, fake_cli


SUCCESS = """
print("args:", " ".join(sys.argv[1:]))
print("Downloading street network")
sys.stdout.write("Fetching 50%|#####\\rFetching 100%|##########\\n")
print("✓ Done")
(POSTERS / "paris_noir_1.png").write_bytes(b"\\x89PNG fake")
"""

FAILURE = """
print("✗ Error: something broke")
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


def wait_for_output(client, job_id, timeout=10):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if web_app.CURRENT_JOB and web_app.CURRENT_JOB.lines:
            return
        time.sleep(0.05)
    raise AssertionError("no output from job")


# --- Themes and validation --------------------------------------------------


def test_themes_listed(env):
    client, _, _ = env
    themes = client.get("/api/themes").json()
    assert [t["id"] for t in themes] == ["noir", "terracotta"]
    assert themes[0]["name"] == "Noir"
    assert themes[0]["colors"] == {"bg": "#000000", "text": "#FFFFFF"}


def test_missing_city_rejected(env):
    client, _, _ = env
    res = client.post("/api/jobs", json={"country": "France"})
    assert res.status_code == 422
    assert "city" in res.json()["errors"]
    assert web_app.CURRENT_JOB is None


def test_plotter_hatch_below_pen_rejected(env):
    client, _, _ = env
    res = client.post("/api/jobs", json={
        "city": "Paris", "country": "France", "format": "plotter", "pen_width": 0.5, "hatch_spacing": 0.2,
    })
    assert res.status_code == 422
    assert "hatch_spacing" in res.json()["errors"]


@pytest.mark.parametrize("data, field", [
    ({"latitude": "48.8"}, "longitude"),
    ({"latitude": "abc", "longitude": "2.3"}, "latitude"),
    ({"distance": 0}, "distance"),
    ({"width": 0}, "width"),
    ({"height": 600}, "height"),
    ({"theme": "missing"}, "theme"),
    ({"format": "gif"}, "format"),
])
def test_field_validation(env, data, field):
    client, _, _ = env
    res = client.post("/api/jobs", json={"city": "Paris", "country": "France", **data})
    assert res.status_code == 422
    assert field in res.json()["errors"]


def test_unknown_theme_allowed_with_all_themes(env, monkeypatch):
    config, errors = web_app.validate_config({"city": "A", "country": "B", "theme": "x", "all_themes": True})
    assert not errors


# --- Command building --------------------------------------------------------


def _config(**kwargs):
    return web_app.PosterConfig(city="Paris", country="France", **kwargs)


def test_build_args_basic():
    args = web_app.build_args(_config(theme="noir", distance=10000, format="svg"))
    assert args == [
        "--city", "Paris", "--country", "France", "--distance", "10000", "--theme", "noir",
        "--width", "300", "--height", "400", "--format", "svg", "--overpass-url", "auto",
    ]
    assert web_app.display_command(args).startswith("python create_map_poster.py --city Paris")


def test_build_args_plotter_and_optional_fields():
    args = web_app.build_args(_config(
        format="plotter", pen_width=0.5, hatch_spacing=1, width=841, height=1189, display_city="東京",
        latitude="40.7", longitude="-73.9", all_themes=True,
    ))
    assert "--all-themes" in args and "--theme" not in args
    assert "--longitude=-73.9" in args
    assert args[args.index("--display-city") + 1] == "東京"
    assert args[args.index("--width") + 1] == "841" and args[args.index("--height") + 1] == "1189"
    assert args[-8:] == [
        "--format", "plotter", "--overpass-url", "auto", "--pen-width", "0.5", "--hatch-spacing", "1",
    ]


def test_plotter_options_omitted_for_other_formats():
    args = web_app.build_args(_config(format="png", hatch_spacing=1))
    assert "--hatch-spacing" not in args and "--pen-width" not in args


def test_no_shell_interpretation():
    args = web_app.build_args(_config().model_copy(update={"city": "Paris; rm -rf /"}))
    assert args[:2] == ["--city", "Paris; rm -rf /"]


# --- Jobs --------------------------------------------------------------------


def test_successful_job_streams_and_reports_files(env):
    client, posters, fake_cli = env
    fake_cli(SUCCESS)
    res = client.post("/api/jobs", json={"city": "Paris", "country": "France", "theme": "noir"})
    assert res.status_code == 200
    job = res.json()
    assert job["command"].startswith("python create_map_poster.py --city Paris --country France")

    lines, status = run_to_end(client, job["id"])
    assert any("--city Paris" in line for line in lines)
    assert "Downloading street network" in lines
    assert "Fetching 100%|##########" in lines  # \r-separated progress updates become lines
    assert "✓ Done" in lines
    assert status["status"] == "succeeded"
    assert status["files"] == ["paris_noir_1.png"]

    # Reconnecting replays the full output
    replay, _ = run_to_end(client, job["id"])
    assert replay == lines
    assert client.get("/api/jobs/current").json()["status"] == "succeeded"


def test_failed_job_keeps_output(env):
    client, _, fake_cli = env
    fake_cli(FAILURE)
    job = client.post("/api/jobs", json={"city": "Paris", "country": "France"}).json()
    lines, status = run_to_end(client, job["id"])
    assert status["status"] == "failed"
    assert status["returncode"] == 1
    assert "✗ Error: something broke" in lines


def test_second_job_rejected_while_running_then_cancel(env):
    client, _, fake_cli = env
    fake_cli(SLOW)
    first = client.post("/api/jobs", json={"city": "Paris", "country": "France"}).json()
    wait_for_output(client, first["id"])

    second = client.post("/api/jobs", json={"city": "Rome", "country": "Italy"})
    assert second.status_code == 409
    assert web_app.CURRENT_JOB.id == first["id"]

    cancelled = client.post(f"/api/jobs/{first['id']}/cancel").json()
    assert cancelled["status"] == "cancelled"

    fake_cli(FAILURE)
    third = client.post("/api/jobs", json={"city": "Rome", "country": "Italy"})
    assert third.status_code == 200
    run_to_end(client, third.json()["id"])


def test_unknown_job_404(env):
    client, _, _ = env
    assert client.get("/api/jobs/nope/events").status_code == 404
    assert client.post("/api/jobs/nope/cancel").status_code == 404


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


@pytest.mark.parametrize("name", ["../create_map_poster.py", "..%2Fweb_app.py", "..%5Cweb_app.py", "notes.txt"])
def test_unsafe_poster_names_rejected(env, name):
    client, posters, _ = env
    (posters / "notes.txt").write_text("secret")
    assert client.get(f"/api/posters/{name}").status_code == 404


def test_plotter_size_not_limited(env):
    config, errors = web_app.validate_config(
        {"city": "A", "country": "B", "format": "plotter", "width": 841, "height": 1189}
    )
    assert not errors


# --- OpenStreetMap servers -----------------------------------------------------


def test_overpass_url_passed_to_cli():
    args = web_app.build_args(_config())
    assert args[args.index("--overpass-url") + 1] == "auto"
    config, errors = web_app.validate_config(
        {"city": "A", "country": "B", "overpass_url": "https://lz4.overpass-api.de/api/interpreter"}
    )
    assert not errors
    args = web_app.build_args(config)
    assert args[args.index("--overpass-url") + 1] == "https://lz4.overpass-api.de/api"


def test_invalid_overpass_url_rejected(env):
    client, _, _ = env
    res = client.post("/api/jobs", json={"city": "Paris", "country": "France", "overpass_url": "not a url"})
    assert res.status_code == 422
    assert "overpass_url" in res.json()["errors"]


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

    monkeypatch.setattr(web_app.overpass_servers, "check_servers", fake_check)
    body = client.post("/api/overpass/check", json={"custom": "https://my.example/api/interpreter"}).json()
    assert seen[-1] == "https://my.example/api"
    assert len(body) == len(web_app.overpass_servers.SERVERS) + 1
    assert body[1]["ok"] and not body[0]["ok"]
    assert client.post("/api/overpass/check", json={"custom": "nope"}).status_code == 422
