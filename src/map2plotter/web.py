#!/usr/bin/env python3
"""
Web Interface

A local web UI in two steps: load a location (downloading the map data once and
rendering a quick preview), then customize the poster with live previews that are
rendered from the cached data only, and export the final poster. Every render runs
`python -m map2plotter` as a subprocess; its output is streamed to the page.
"""

import argparse
import asyncio
import codecs
import json
import os
import re
import shlex
import shutil
import sys
import time
import uuid
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Literal, Optional

import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from lat_lon_parser import parse
from pydantic import BaseModel, ValidationError, field_validator

from . import colors as poster_colors
from . import edits as poster_edits
from . import overpass, paths
from . import size as poster_size

POSTERS_DIR = paths.POSTERS_DIR
THEMES_DIR = paths.THEMES_DIR
STATIC_DIR = paths.STATIC_DIR
CLI_COMMAND = [sys.executable, "-u", "-m", "map2plotter"]
WORK_DIR = paths.CACHE_DIR / "web"

POSTER_TYPES = {".png": "image/png", ".svg": "image/svg+xml", ".pdf": "application/pdf"}
PREVIEW_MAX_MM = 500  # Raster previews of larger posters are rendered scaled down (same look)
PREVIEW_PIXELS = 2000  # Long side of PNG previews (sharp enough to zoom in a little)
PING_INTERVAL = 15  # seconds between SSE keep-alive comments
KILL_TIMEOUT = 5  # seconds to wait after terminate before killing
FILL_MODES = ("hatch", "concentric")


# ---------------------------------------------------------------------------
# Configuration and validation
# ---------------------------------------------------------------------------


def _blank_to_none(value):
    if isinstance(value, str) and not value.strip():
        return None
    return value.strip() if isinstance(value, str) else value


class LocationConfig(BaseModel):
    """Step 1: the workflow and what map data to load. Same defaults as the CLI."""

    mode: Literal["print", "plotter"] = "print"  # print poster (png/svg/pdf) or pen plotter
    city: str = ""
    country: str = ""
    latitude: Optional[str] = None
    longitude: Optional[str] = None
    distance: int = 18000
    width: float = 300  # mm
    height: float = 400  # mm
    overpass_url: str = overpass.AUTO

    @field_validator("latitude", "longitude", mode="before")
    @classmethod
    def _blank(cls, value):
        return _blank_to_none(value)

    @field_validator("city", "country", mode="before")
    @classmethod
    def _strip(cls, value):
        return value.strip() if isinstance(value, str) else value


class CustomizeConfig(BaseModel):
    """Step 2: how to render the loaded map. Same defaults as the CLI."""

    theme: str = "terracotta"
    all_themes: bool = False
    country_label: Optional[str] = None
    display_city: Optional[str] = None
    display_country: Optional[str] = None
    font_family: Optional[str] = None
    format: Literal["png", "svg", "pdf", "plotter"] = "png"
    dpi: int = 300  # PNG export resolution
    pen_width: float = 0.3
    hatch_spacing: Optional[float] = None
    water_fill: Literal["hatch", "concentric"] = "hatch"
    parks_fill: Literal["hatch", "concentric"] = "hatch"
    water_spacing: Optional[float] = None
    parks_spacing: Optional[float] = None
    water_outline: bool = False
    colors: Optional[dict] = None  # {theme key: '#rrggbb'} overrides (pen colours)
    edits: Optional[dict] = None

    @field_validator("country_label", "display_city", "display_country", "font_family", mode="before")
    @classmethod
    def _blank(cls, value):
        return _blank_to_none(value)

    @field_validator("hatch_spacing", "water_spacing", "parks_spacing", mode="before")
    @classmethod
    def _blank_number(cls, value):
        return None if value == "" else value

    @field_validator("theme", mode="before")
    @classmethod
    def _strip(cls, value):
        return value.strip() if isinstance(value, str) else value


def get_themes():
    """Read all theme files into [{id, name, description, colors}]."""
    themes = []
    if not THEMES_DIR.is_dir():
        return themes
    for path in sorted(THEMES_DIR.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        colors = {
            key: value for key, value in data.items()
            if isinstance(value, str) and value.startswith("#")
        }
        themes.append({
            "id": path.stem,
            "name": data.get("name", path.stem),
            "description": data.get("description", ""),
            "colors": colors,
        })
    return themes


def _model_errors(model, data):
    """Parse data into model; return (instance or None, {field: message})."""
    try:
        return model.model_validate(data), {}
    except ValidationError as e:
        errors = {}
        for err in e.errors():
            name = str(err["loc"][0]) if err["loc"] else "form"
            errors.setdefault(name, err["msg"])
        return None, errors


def validate_location(data):
    """
    Validate the Location step.

    Returns:
        (LocationConfig or None, {field: error message})
    """
    config, errors = _model_errors(LocationConfig, data)
    if config is None:
        return None, errors

    if not config.city:
        errors["city"] = "City is required"
    if not config.country:
        errors["country"] = "Country is required"

    if (config.latitude is None) != (config.longitude is None):
        missing = "longitude" if config.longitude is None else "latitude"
        errors[missing] = "Latitude and longitude must be set together"
    for name in ("latitude", "longitude"):
        value = getattr(config, name)
        if value is not None:
            try:
                parse(value)
            except Exception:
                errors[name] = f"Cannot parse {name} '{value}'"

    for name in ("distance", "width", "height"):
        if getattr(config, name) <= 0:
            errors[name] = "Must be greater than 0"

    try:
        config.overpass_url = overpass.normalize(config.overpass_url)
    except ValueError as e:
        errors["overpass_url"] = str(e)

    return (None if errors else config), errors


def validate_customize(data, location=None, export=False):
    """
    Validate the Customize step for the loaded location's workflow, if given.
    The PNG pixel limit only applies to exports (previews are rendered scaled down).

    Returns:
        (CustomizeConfig or None, {field: error message})
    """
    config, errors = _model_errors(CustomizeConfig, data)
    if config is None:
        return None, errors

    if location is not None:
        if location.mode == "plotter":
            config.format = "plotter"
        elif config.format == "plotter":
            errors["format"] = "Pen plotter output needs the pen plotter workflow (choose it in the Location step)"

    for name in ("pen_width", "hatch_spacing", "water_spacing", "parks_spacing", "dpi"):
        value = getattr(config, name)
        if value is not None and value <= 0:
            errors[name] = "Must be greater than 0"

    if not config.all_themes and config.theme not in {t["id"] for t in get_themes()}:
        errors["theme"] = f"Theme '{config.theme}' not found"

    if config.format == "plotter" and "pen_width" not in errors:
        for name, label in (
            ("hatch_spacing", "Hatch spacing"), ("water_spacing", "Water spacing"), ("parks_spacing", "Parks spacing"),
        ):
            value = getattr(config, name)
            if name == "hatch_spacing" and value is None:
                value = config.pen_width
            if value is not None and value < config.pen_width and name not in errors:
                errors[name] = f"{label} must not be less than the pen width"

    if export and location is not None and config.format == "png" and "dpi" not in errors:
        error = poster_size.png_limit_error(location.width, location.height, config.dpi)
        if error:
            errors["dpi"] = error[0].upper() + error[1:]

    if config.colors:
        try:
            config.colors = {key: poster_colors.check_color(key, value) for key, value in config.colors.items()}
        except ValueError as e:
            errors["colors"] = str(e)

    if config.edits is not None:
        try:
            poster_edits.parse_edits(config.edits)
        except poster_edits.EditsError as e:
            errors["edits"] = str(e)

    return (None if errors else config), errors


def _num(value):
    """Format a number without a trailing '.0'."""
    return f"{value:g}"


def _opt(flag, value):
    """One CLI option; values starting with '-' use the '--flag=value' form so argparse keeps them."""
    return [f"{flag}={value}"] if value.startswith("-") else [flag, value]


def location_args(loc, width=None, height=None):
    """CLI arguments selecting the map area (size may be overridden, e.g. for a scaled preview)."""
    args = _opt("--city", loc.city) + _opt("--country", loc.country)
    if loc.latitude is not None and loc.longitude is not None:
        args += _opt("--latitude", loc.latitude) + _opt("--longitude", loc.longitude)
    args += ["--distance", str(loc.distance)]
    args += ["--width", _num(width or loc.width), "--height", _num(height or loc.height)]
    args += ["--overpass-url", loc.overpass_url]
    return args


def theme_colors(theme_id):
    """Colour values of a theme file ({} if it cannot be read)."""
    try:
        data = json.loads((THEMES_DIR / f"{theme_id}.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return {k: v.lower() for k, v in data.items() if isinstance(v, str) and v.startswith("#")}


def color_args(c, all_themes=False):
    """--color options for the colours that differ from the base theme (all of them with all themes)."""
    if not c.colors:
        return []
    base = {} if all_themes else theme_colors(c.theme)
    return [
        arg for key, value in c.colors.items() if base.get(key) != value
        for arg in ("--color", f"{key}={value}")
    ]


def customize_args(c, fmt=None, all_themes=None, export=False):
    """CLI arguments for the look of the poster (empty options omitted; --dpi only for PNG exports)."""
    fmt = fmt or c.format
    all_themes = c.all_themes if all_themes is None else all_themes
    args = ["--all-themes"] if all_themes else _opt("--theme", c.theme)
    args += color_args(c, all_themes)
    for flag, value in (
        ("--country-label", c.country_label),
        ("--display-city", c.display_city),
        ("--display-country", c.display_country),
        ("--font-family", c.font_family),
    ):
        if value:
            args += _opt(flag, value)
    args += ["--format", fmt]
    if export and fmt == "png" and c.dpi != 300:
        args += ["--dpi", str(c.dpi)]
    if fmt == "plotter":
        args += ["--pen-width", _num(c.pen_width)]
        for flag, value in (
            ("--hatch-spacing", c.hatch_spacing),
            ("--water-spacing", c.water_spacing),
            ("--parks-spacing", c.parks_spacing),
        ):
            if value is not None:
                args += [flag, _num(value)]
        if c.water_fill != "hatch":
            args += ["--water-fill", c.water_fill]
        if c.parks_fill != "hatch":
            args += ["--parks-fill", c.parks_fill]
        if c.water_outline:
            args.append("--water-outline")
    return args


def preview_dpi(width, height):
    """DPI that gives PNG previews about PREVIEW_PIXELS on the long side."""
    return max(30, min(150, round(PREVIEW_PIXELS / (max(width, height) / 25.4))))


def preview_size(loc):
    """Preview page size: the poster size, scaled down (same aspect) to the raster limit if needed."""
    scale = min(1.0, PREVIEW_MAX_MM / max(loc.width, loc.height))
    return loc.width * scale, loc.height * scale


def display_command(args):
    """The equivalent shell command line, for users to copy."""
    return shlex.join(["map2plotter", *args])


# ---------------------------------------------------------------------------
# Session and jobs
# ---------------------------------------------------------------------------


@dataclass
class Session:
    """The loaded location and its preview files (one per server)."""

    dir: Path
    location: Optional[LocationConfig] = None
    loaded: bool = False
    preview: Optional[Path] = None
    version: int = 0

    def preview_info(self):
        if self.preview is None or not self.preview.is_file():
            return None
        return {"url": f"/api/preview?v={self.version}", "type": self.preview.suffix[1:]}

    def set_preview(self, rendered):
        """Make a freshly rendered file the current preview, replacing the previous one."""
        target = self.dir / f"preview{rendered.suffix}"
        for old in self.dir.glob("preview.*"):
            old.unlink(missing_ok=True)
        rendered.replace(target)
        self.preview = target
        self.version += 1


def new_session():
    """Start a fresh session with an empty working directory (old ones are removed)."""
    shutil.rmtree(WORK_DIR, ignore_errors=True)
    path = WORK_DIR / uuid.uuid4().hex
    path.mkdir(parents=True, exist_ok=True)
    return Session(dir=path)


@dataclass
class Job:
    """A single run of the poster CLI."""

    id: str
    kind: str  # 'load', 'preview' or 'export'
    args: list
    command: str
    before: set
    status: str = "running"
    lines: list = field(default_factory=list)
    files: list = field(default_factory=list)
    returncode: Optional[int] = None
    started_at: float = field(default_factory=time.time)
    finished_at: Optional[float] = None
    cancel_requested: bool = False
    on_finish: Optional[Callable] = None
    proc: Optional[asyncio.subprocess.Process] = None
    task: Optional[asyncio.Task] = None
    changed: asyncio.Condition = field(default_factory=asyncio.Condition)

    def summary(self):
        return {
            "id": self.id,
            "kind": self.kind,
            "status": self.status,
            "command": self.command,
            "files": self.files,
            "returncode": self.returncode,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "preview": SESSION.preview_info() if SESSION is not None else None,
        }


SESSION: Optional[Session] = None
CURRENT_JOB: Optional[Job] = None
_START_LOCK: Optional[asyncio.Lock] = None

LINE_BREAK = re.compile(r"\r\n|\r|\n")
NOT_CACHED = "not cached"


def poster_names():
    """Names of poster files currently in the posters directory."""
    if not POSTERS_DIR.is_dir():
        return set()
    return {p.name for p in POSTERS_DIR.iterdir() if p.is_file() and p.suffix.lower() in POSTER_TYPES}


async def _notify(job):
    async with job.changed:
        job.changed.notify_all()


async def _run_job(job):
    """Read the process output into the job, then record the outcome."""
    decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")
    buffer = ""
    while True:
        chunk = await job.proc.stdout.read(4096)
        if not chunk:
            break
        buffer += decoder.decode(chunk)
        parts = LINE_BREAK.split(buffer)
        buffer = parts.pop()
        job.lines.extend(p for p in parts if p.strip())
        await _notify(job)
    buffer += decoder.decode(b"", final=True)
    if buffer.strip():
        job.lines.append(buffer)

    job.returncode = await job.proc.wait()
    new_files = poster_names() - job.before
    job.files = sorted(new_files, key=lambda n: (POSTERS_DIR / n).stat().st_mtime)
    job.finished_at = time.time()
    if job.cancel_requested:
        job.status = "cancelled"
    else:
        job.status = "succeeded" if job.returncode == 0 else "failed"
    if job.on_finish is not None:
        try:
            job.on_finish(job)
        except Exception as e:  # never leave a job running because of a bookkeeping error
            job.lines.append(f"Failed to finish job: {e}")
    await _notify(job)


async def start_job(kind, args, on_finish=None):
    """
    Start the CLI. A running preview is replaced; a running load or export blocks
    every new job (HTTP 409).
    """
    global CURRENT_JOB, _START_LOCK
    if _START_LOCK is None:
        _START_LOCK = asyncio.Lock()
    async with _START_LOCK:
        current = CURRENT_JOB
        if current is not None and current.status == "running":
            if current.kind != "preview":
                raise HTTPException(status_code=409, detail="A job is already running")
            await cancel_job(current)

        job = Job(
            id=uuid.uuid4().hex, kind=kind, args=args, command=display_command(args),
            before=poster_names(), on_finish=on_finish,
        )
        CURRENT_JOB = job
        env = {
            **os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUNBUFFERED": "1", "MPLBACKEND": "Agg",
            "CACHE_DIR": str(paths.CACHE_DIR.resolve()),  # Same cache as the server, whatever the CLI's cwd
        }
        try:
            job.proc = await asyncio.create_subprocess_exec(
                *CLI_COMMAND, *args,
                env=env,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )
        except Exception as e:
            job.status = "failed"
            job.lines.append(f"Failed to start generator: {e}")
            job.finished_at = time.time()
            return job
        job.task = asyncio.create_task(_run_job(job))
        return job


async def cancel_job(job):
    """Terminate a running job (killing it if it does not exit) and wait for it to finish."""
    if job.status != "running" or job.proc is None:
        return
    job.cancel_requested = True
    job.proc.terminate()
    try:
        await asyncio.wait_for(job.proc.wait(), KILL_TIMEOUT)
    except asyncio.TimeoutError:
        job.proc.kill()
    if job.task is not None:
        await job.task


def get_job(job_id):
    if CURRENT_JOB is None or CURRENT_JOB.id != job_id:
        raise HTTPException(status_code=404, detail="Job not found")
    return CURRENT_JOB


def _sse(payload):
    return f"data: {json.dumps(payload)}\n\n"


async def job_events(job):
    """Server-sent events: replay output, stream new lines, end with the final status."""
    sent = 0
    while True:
        ping = False
        async with job.changed:
            if sent >= len(job.lines) and job.status == "running":
                try:
                    await asyncio.wait_for(job.changed.wait(), PING_INTERVAL)
                except asyncio.TimeoutError:
                    ping = True
        if ping:
            yield ": ping\n\n"
            continue
        while sent < len(job.lines):
            yield _sse({"type": "line", "text": job.lines[sent]})
            sent += 1
        if job.status != "running":
            summary = job.summary()
            summary["not_cached"] = job.status == "failed" and any(NOT_CACHED in line for line in job.lines)
            yield _sse({"type": "status", **summary})
            return


def _write_edits(custom, name):
    """Write a non-empty edit list into the session directory; return CLI args for it."""
    if custom.edits is None:
        return []
    edits = poster_edits.parse_edits(custom.edits)
    if edits.is_empty():
        return []
    path = SESSION.dir / name
    path.write_text(json.dumps(edits.to_dict()), encoding="utf-8")
    return ["--edits", str(path)]


def _preview_finisher(rendered, on_success=None):
    """Job callback: promote the rendered preview on success, discard it otherwise."""
    def finish(job):
        if job.status == "succeeded" and rendered.is_file():
            SESSION.set_preview(rendered)
            if on_success is not None:
                on_success()
        else:
            rendered.unlink(missing_ok=True)
    return finish


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(_app):
    global SESSION
    SESSION = new_session()
    yield
    if CURRENT_JOB is not None:
        await cancel_job(CURRENT_JOB)


app = FastAPI(title="map2plotter", lifespan=lifespan)


async def _json_body(request):
    try:
        data = await request.json()
    except json.JSONDecodeError:
        data = None
    if not isinstance(data, dict):
        raise HTTPException(status_code=400, detail="Expected a JSON object")
    return data


def _invalid(errors):
    return JSONResponse({"detail": "Invalid configuration", "errors": errors}, status_code=422)


def _require_loaded():
    if SESSION is None or not SESSION.loaded or SESSION.location is None:
        raise HTTPException(status_code=409, detail="Load the map in the Location step first")
    return SESSION.location


@app.get("/")
def index():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/themes")
def list_themes():
    return get_themes()


@app.get("/api/session")
def session_state():
    return {
        "loaded": SESSION.loaded,
        "location": SESSION.location.model_dump() if SESSION.location else None,
        "preview": SESSION.preview_info(),
    }


@app.post("/api/load")
async def load(request: Request):
    """Download (or read from the cache) the map data for a location and render a quick preview."""
    data = await _json_body(request)
    loc, errors = validate_location(data)
    theme = data.get("theme") or "terracotta"
    if theme not in {t["id"] for t in get_themes()}:
        errors["theme"] = f"Theme '{theme}' not found"
    if errors:
        return _invalid(errors)

    if loc.mode == "plotter":
        rendered = SESSION.dir / "rendering.svg"
        args = location_args(loc) + _opt("--theme", theme) + ["--format", "plotter", "--output", str(rendered)]
    else:
        width, height = preview_size(loc)
        rendered = SESSION.dir / "rendering.png"
        args = location_args(loc, width, height) + _opt("--theme", theme) + [
            "--format", "png", "--output", str(rendered), "--dpi", str(preview_dpi(width, height)),
        ]

    def loaded():
        SESSION.location, SESSION.loaded = loc, True

    job = await start_job("load", args, _preview_finisher(rendered, loaded))
    SESSION.loaded = False  # Customize stays locked until this location has loaded
    return job.summary()


@app.post("/api/preview")
async def preview(request: Request):
    """Re-render the preview from the cached map data (never downloads)."""
    data = await _json_body(request)
    loc = _require_loaded()
    custom, errors = validate_customize(data, loc)
    if errors:
        return _invalid(errors)

    if custom.format == "plotter":
        rendered = SESSION.dir / "rendering.svg"
        args = location_args(loc) + customize_args(custom, all_themes=False)
    else:
        width, height = preview_size(loc)
        rendered = SESSION.dir / "rendering.png"
        args = location_args(loc, width, height) + customize_args(custom, fmt="png", all_themes=False)
        args += ["--dpi", str(preview_dpi(width, height))]
    args += ["--cache-only", "--output", str(rendered)] + _write_edits(custom, "edits.json")
    job = await start_job("preview", args, _preview_finisher(rendered))
    return job.summary()


@app.post("/api/export")
async def export(request: Request):
    """Render the final poster(s) into posters/ from the cached map data."""
    data = await _json_body(request)
    loc = _require_loaded()
    custom, errors = validate_customize(data, loc, export=True)
    if errors:
        return _invalid(errors)
    args = location_args(loc) + customize_args(custom, export=True) + ["--cache-only"]
    args += _write_edits(custom, "edits-export.json")
    job = await start_job("export", args)
    return job.summary()


@app.get("/api/preview")
def get_preview():
    info = SESSION.preview_info() if SESSION is not None else None
    if info is None:
        raise HTTPException(status_code=404, detail="No preview yet")
    return FileResponse(
        SESSION.preview, media_type=POSTER_TYPES[SESSION.preview.suffix], headers={"Cache-Control": "no-store"},
    )


@app.post("/api/layout")
async def layout(request: Request):
    """Default positions (page mm) of the poster's text lines, for the editor's drag handles."""
    data = await _json_body(request)
    loc = _require_loaded()
    from . import plotter
    from . import poster as cmp  # heavy import (osmnx, matplotlib): only when needed

    city = _blank_to_none(data.get("display_city")) or loc.city
    country = _blank_to_none(data.get("display_country")) or _blank_to_none(data.get("country_label")) or loc.country
    if loc.latitude is not None and loc.longitude is not None:
        coords = cmp.format_coordinates(parse(loc.latitude), parse(loc.longitude))
    else:
        coords = cmp.format_coordinates(0.0, 0.0)  # Same width as real coordinates
    scale = min(loc.width, loc.height) / plotter.REFERENCE_SIZE_MM
    spaced_city, city_size = cmp.format_city_title(city, scale)
    texts = {
        "city": (spaced_city, city_size),
        "country": (country.upper(), cmp.BASE_SUB * scale),
        "coords": (coords, cmp.BASE_COORDS * scale),
        "attribution": ("© OpenStreetMap contributors", cmp.BASE_ATTR),
    }
    boxes = plotter.text_boxes(texts, loc.width, loc.height)
    return {"width": loc.width, "height": loc.height, "boxes": boxes}


@app.get("/api/jobs/current")
def current_job():
    return CURRENT_JOB.summary() if CURRENT_JOB else None


@app.get("/api/jobs/{job_id}/events")
def stream_job(job_id: str):
    job = get_job(job_id)
    return StreamingResponse(
        job_events(job),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post("/api/jobs/{job_id}/cancel")
async def cancel(job_id: str):
    job = get_job(job_id)
    await cancel_job(job)
    return job.summary()


def default_overpass():
    """The server preselected in the UI: $OVERPASS_URL if valid, else automatic."""
    try:
        return overpass.normalize(os.environ.get("OVERPASS_URL"))
    except ValueError:
        return overpass.AUTO


@app.get("/api/overpass/servers")
def overpass_server_list():
    return {
        "default": default_overpass(),
        "servers": [{"url": url, "label": label} for url, label in overpass.SERVERS],
    }


@app.post("/api/overpass/check")
async def overpass_check(request: Request):
    """Health-check the known servers (plus an optional custom URL) in parallel."""
    try:
        data = await request.json()
    except json.JSONDecodeError:
        data = {}
    urls = [url for url, _ in overpass.SERVERS]
    custom = data.get("custom") if isinstance(data, dict) else None
    if custom:
        try:
            custom = overpass.normalize(custom)
        except ValueError as e:
            return JSONResponse({"detail": str(e), "errors": {"overpass_url": str(e)}}, status_code=422)
        if custom != overpass.AUTO and custom not in urls:
            urls.append(custom)
    return await asyncio.to_thread(overpass.check_servers, urls)


@app.get("/api/posters")
def list_posters():
    if not POSTERS_DIR.is_dir():
        return []
    files = [p for p in POSTERS_DIR.iterdir() if p.is_file() and p.suffix.lower() in POSTER_TYPES]
    files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return [{"name": p.name, "size": p.stat().st_size, "mtime": p.stat().st_mtime} for p in files]


@app.get("/api/posters/{name}")
def get_poster(name: str, download: bool = False):
    suffix = Path(name).suffix.lower()
    if name != Path(name).name or suffix not in POSTER_TYPES:
        raise HTTPException(status_code=404, detail="Poster not found")
    posters = POSTERS_DIR.resolve()
    path = (posters / name).resolve()
    if path.parent != posters or not path.is_file():
        raise HTTPException(status_code=404, detail="Poster not found")
    return FileResponse(
        path,
        media_type=POSTER_TYPES[suffix],
        filename=name,
        content_disposition_type="attachment" if download else "inline",
    )


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


def main():
    parser = argparse.ArgumentParser(prog="map2plotter-web", description="Web interface for map2plotter")
    parser.add_argument("--host", default="127.0.0.1", help="Address to bind (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8000, help="Port to listen on (default: 8000)")
    args = parser.parse_args()
    print(f"map2plotter web UI: http://{args.host}:{args.port}/", flush=True)
    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
