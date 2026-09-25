"""Tests for OpenStreetMap server selection and fallback (no network access)."""

import osmnx as ox
import pytest
import requests
from osmnx import _overpass
from osmnx._errors import InsufficientResponseError, ResponseStatusCodeError

import map2plotter
import map2plotter.overpass as osrv

A, B, C = "https://a.example/api", "https://b.example/api", "https://c.example/api"


@pytest.mark.parametrize("value, expected", [
    (None, "auto"),
    ("", "auto"),
    (" AUTO ", "auto"),
    ("https://lz4.overpass-api.de/api", "https://lz4.overpass-api.de/api"),
    ("https://lz4.overpass-api.de/api/", "https://lz4.overpass-api.de/api"),
    ("https://lz4.overpass-api.de/api/interpreter", "https://lz4.overpass-api.de/api"),
    ("https://lz4.overpass-api.de/api/status", "https://lz4.overpass-api.de/api"),
])
def test_normalize(value, expected):
    assert osrv.normalize(value) == expected


@pytest.mark.parametrize("value", ["ftp://x.example/api", "overpass-api.de", "https://"])
def test_normalize_rejects_non_urls(value):
    with pytest.raises(ValueError):
        osrv.normalize(value)


def test_specific_server_used_alone():
    assert osrv.candidates(B, log=lambda _: None, check=lambda _: pytest.fail("no check")) == [B]


def test_auto_puts_healthy_servers_first():
    results = [
        {"url": A, "ok": False, "ms": 30000, "error": "HTTP 504"},
        {"url": B, "ok": True, "ms": 800, "error": None},
        {"url": C, "ok": True, "ms": 200, "error": None},
    ]
    logs = []
    assert osrv.candidates("auto", log=logs.append, check=lambda _: results) == [B, C, A]
    assert any("b.example" in line for line in logs)


def test_run_falls_back_on_server_errors(monkeypatch):
    used = []

    def call():
        used.append(ox.settings.overpass_url)
        if ox.settings.overpass_url == A:
            raise requests.exceptions.ConnectionError("Connection refused")
        if ox.settings.overpass_url == B:
            raise ResponseStatusCodeError("'b.example' responded: 403 Forbidden")
        return "graph"

    monkeypatch.setattr(ox.settings, "overpass_url", "https://original.example/api")
    logs = []
    assert osrv.run(call, [A, B, C], log=logs.append) == ("graph", C)
    assert used == [A, B, C]
    assert len(logs) == 2 and "trying b.example" in logs[0]


def test_run_reports_every_failure(monkeypatch):
    def call():
        raise requests.exceptions.ReadTimeout("timed out")

    monkeypatch.setattr(ox.settings, "overpass_url", "https://original.example/api")
    with pytest.raises(osrv.OverpassError) as e:
        osrv.run(call, [A, B], log=lambda _: None)
    assert "a.example: timed out" in str(e.value) and "b.example: timed out" in str(e.value)


def test_run_does_not_fall_back_when_area_has_no_data(monkeypatch):
    def call():
        raise InsufficientResponseError("No data elements in server response")

    monkeypatch.setattr(ox.settings, "overpass_url", "https://original.example/api")
    with pytest.raises(InsufficientResponseError):
        osrv.run(call, [A, B], log=lambda _: None)


def _install_fake_request(monkeypatch, busy_answers):
    """Fake OSMnx request that 'retries' recursively like OSMnx does on 429/504."""
    calls = []

    def fake(data):
        calls.append(data)
        if len(calls) <= busy_answers:
            return _overpass._overpass_request(data)  # OSMnx's recursive retry
        return {"elements": []}

    monkeypatch.setattr(_overpass, "_overpass_request", fake)
    return calls


def test_retries_are_capped(monkeypatch):
    calls = _install_fake_request(monkeypatch, busy_answers=100)
    osrv.limit_retries(max_attempts=3, log=lambda _: None)
    with pytest.raises(osrv.OverpassBusyError):
        _overpass._overpass_request({"data": "q"})
    assert len(calls) == 3


def test_retries_within_limit_succeed(monkeypatch):
    calls = _install_fake_request(monkeypatch, busy_answers=1)
    logs = []
    osrv.limit_retries(max_attempts=3, log=logs.append)
    assert _overpass._overpass_request({"data": "q"}) == {"elements": []}
    assert len(calls) == 2 and len(logs) == 1
    # A second request starts counting from zero again
    calls.clear()
    assert _overpass._overpass_request({"data": "q"}) == {"elements": []}


class _Response:
    def __init__(self, status, body=None, reason="OK"):
        self.status_code, self._body, self.reason = status, body, reason

    def json(self):
        return self._body


@pytest.mark.parametrize("response, ok, error", [
    (_Response(200, {"elements": [{"type": "count", "tags": {"total": "3"}}]}), True, None),
    (_Response(504, reason="Gateway Timeout"), False, "HTTP 504 Gateway Timeout"),
    (_Response(200, {"elements": []}), False, "Unexpected response"),
    (requests.exceptions.ReadTimeout(), False, "No answer within 15 s"),
    (requests.exceptions.ConnectionError(), False, "Connection failed"),
])
def test_check_server(monkeypatch, response, ok, error):
    def fake_post(url, **kwargs):
        assert url == "https://a.example/api/interpreter"
        if isinstance(response, Exception):
            raise response
        return response

    monkeypatch.setattr(osrv.requests, "post", fake_post)
    result = osrv.check_server(A)
    assert result["ok"] is ok and result["error"] == error and result["url"] == A


def test_slot_status_only_for_overpass_api_de(monkeypatch):
    seen = {}

    def call():
        seen[ox.settings.overpass_url] = ox.settings.overpass_rate_limit
        raise requests.exceptions.ConnectionError("down")

    monkeypatch.setattr(ox.settings, "overpass_url", "https://original.example/api")
    monkeypatch.setattr(ox.settings, "overpass_rate_limit", True)
    servers = [
        "https://overpass-api.de/api",
        "https://lz4.overpass-api.de/api",
        "https://maps.mail.ru/osm/tools/overpass/api",
    ]
    with pytest.raises(osrv.OverpassError):
        osrv.run(call, servers, log=lambda _: None)
    assert seen == {servers[0]: True, servers[1]: True, servers[2]: False}


def test_user_agent_identifies_map2plotter():
    assert map2plotter.USER_AGENT == f"map2plotter/{map2plotter.__version__} (+https://github.com/Dirnei/map2plotter)"


def test_check_server_sends_user_agent(monkeypatch):
    seen = {}

    def fake_post(url, **kwargs):
        seen.update(kwargs["headers"])
        return _Response(200, {"elements": [{"type": "count"}]})

    monkeypatch.setattr(osrv.requests, "post", fake_post)
    osrv.check_server(A)
    assert seen["User-Agent"] == map2plotter.USER_AGENT
