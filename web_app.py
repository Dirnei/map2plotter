#!/usr/bin/env python3
"""
Web Interface

A local web UI to configure every poster option, run create_map_poster.py as a
subprocess, stream its progress, and preview/download the generated posters.
"""

import argparse
import asyncio
import codecs
import json
import os
import re
import shlex
import sys
import time
import uuid
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, Optional

import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from lat_lon_parser import parse
from pydantic import BaseModel, ValidationError, field_validator

import overpass_servers

ROOT = Path(__file__).resolve().parent
POSTERS_DIR = ROOT / "posters"
THEMES_DIR = ROOT / "themes"
STATIC_DIR = ROOT / "web" / "static"
CLI_SCRIPT = ROOT / "create_map_poster.py"

POSTER_TYPES = {".png": "image/png", ".svg": "image/svg+xml", ".pdf": "application/pdf"}
MAX_SIZE_MM = 500  # Same limit as the CLI for png/svg/pdf; plotter output is not limited
PING_INTERVAL = 15  # seconds between SSE keep-alive comments
KILL_TIMEOUT = 5  # seconds to wait after terminate before killing


# ---------------------------------------------------------------------------
# Configuration and validation
# ---------------------------------------------------------------------------


class PosterConfig(BaseModel):
    """All poster options, with the same defaults as the CLI."""

    city: str = ""
    country: str = ""
    latitude: Optional[str] = None
    longitude: Optional[str] = None
    distance: int = 18000
    theme: str = "terracotta"
    all_themes: bool = False
    width: float = 300  # mm
    height: float = 400  # mm
    country_label: Optional[str] = None
    display_city: Optional[str] = None
    display_country: Optional[str] = None
    font_family: Optional[str] = None
    format: Literal["png", "svg", "pdf", "plotter"] = "png"
    pen_width: float = 0.3
    hatch_spacing: Optional[float] = None
    overpass_url: str = overpass_servers.AUTO

    @field_validator(
        "latitude", "longitude", "country_label", "display_city", "display_country", "font_family",
        mode="before",
    )
    @classmethod
    def _blank_to_none(cls, value):
        if isinstance(value, str) and not value.strip():
            return None
        return value.strip() if isinstance(value, str) else value

    @field_validator("city", "country", "theme", mode="before")
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


def validate_config(data):
    """
    Validate submitted form data.

    Returns:
        (PosterConfig or None, {field: error message})
    """
    try:
        config = PosterConfig.model_validate(data)
    except ValidationError as e:
        errors = {}
        for err in e.errors():
            name = str(err["loc"][0]) if err["loc"] else "form"
            errors.setdefault(name, err["msg"])
        return None, errors

    errors = {}
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

    for name in ("distance", "width", "height", "pen_width", "hatch_spacing"):
        value = getattr(config, name)
        if value is not None and value <= 0:
            errors[name] = "Must be greater than 0"
    if config.format != "plotter":
        for name in ("width", "height"):
            if getattr(config, name) > MAX_SIZE_MM:
                errors.setdefault(name, f"Must not exceed {MAX_SIZE_MM} mm (except for plotter output)")

    if not config.all_themes and config.theme not in {t["id"] for t in get_themes()}:
        errors["theme"] = f"Theme '{config.theme}' not found"

    try:
        config.overpass_url = overpass_servers.normalize(config.overpass_url)
    except ValueError as e:
        errors["overpass_url"] = str(e)

    if config.format == "plotter" and "pen_width" not in errors:
        hatch = config.hatch_spacing if config.hatch_spacing is not None else config.pen_width
        if hatch < config.pen_width:
            errors["hatch_spacing"] = "Hatch spacing must not be less than the pen width"

    return (None if errors else config), errors


def _num(value):
    """Format a number without a trailing '.0'."""
    return f"{value:g}"


def _opt(flag, value):
    """One CLI option; values starting with '-' use the '--flag=value' form so argparse keeps them."""
    return [f"{flag}={value}"] if value.startswith("-") else [flag, value]


def build_args(config):
    """Map a validated PosterConfig onto create_map_poster.py arguments (empty options omitted)."""
    args = _opt("--city", config.city) + _opt("--country", config.country)
    if config.latitude is not None and config.longitude is not None:
        args += _opt("--latitude", config.latitude) + _opt("--longitude", config.longitude)
    args += ["--distance", str(config.distance)]
    if config.all_themes:
        args.append("--all-themes")
    else:
        args += _opt("--theme", config.theme)
    args += ["--width", _num(config.width), "--height", _num(config.height)]
    for flag, value in (
        ("--country-label", config.country_label),
        ("--display-city", config.display_city),
        ("--display-country", config.display_country),
        ("--font-family", config.font_family),
    ):
        if value:
            args += _opt(flag, value)
    args += ["--format", config.format]
    args += ["--overpass-url", config.overpass_url]
    if config.format == "plotter":
        args += ["--pen-width", _num(config.pen_width)]
        if config.hatch_spacing is not None:
            args += ["--hatch-spacing", _num(config.hatch_spacing)]
    return args


def display_command(args):
    """The equivalent shell command line, for users to copy."""
    return shlex.join(["python", "create_map_poster.py", *args])


# ---------------------------------------------------------------------------
# Jobs
# ---------------------------------------------------------------------------


@dataclass
class Job:
    """A single run of the poster CLI."""

    id: str
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
    proc: Optional[asyncio.subprocess.Process] = None
    task: Optional[asyncio.Task] = None
    changed: asyncio.Condition = field(default_factory=asyncio.Condition)

    def summary(self):
        return {
            "id": self.id,
            "status": self.status,
            "command": self.command,
            "files": self.files,
            "returncode": self.returncode,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
        }


CURRENT_JOB: Optional[Job] = None

LINE_BREAK = re.compile(r"\r\n|\r|\n")


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
    await _notify(job)


async def start_job(config):
    """Start the CLI for a validated config; raises if a job is already running."""
    global CURRENT_JOB
    if CURRENT_JOB is not None and CURRENT_JOB.status == "running":
        raise HTTPException(status_code=409, detail="A job is already running")

    args = build_args(config)
    job = Job(id=uuid.uuid4().hex, args=args, command=display_command(args), before=poster_names())
    CURRENT_JOB = job
    env = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUNBUFFERED": "1"}
    try:
        job.proc = await asyncio.create_subprocess_exec(
            sys.executable, "-u", str(CLI_SCRIPT), *args,
            cwd=str(ROOT),
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
            yield _sse({"type": "status", **job.summary()})
            return


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(_app):
    yield
    if CURRENT_JOB is not None:
        await cancel_job(CURRENT_JOB)


app = FastAPI(title="Map Poster Generator", lifespan=lifespan)


@app.get("/")
def index():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/themes")
def list_themes():
    return get_themes()


@app.post("/api/jobs")
async def create_job(request: Request):
    try:
        data = await request.json()
    except json.JSONDecodeError:
        data = None
    if not isinstance(data, dict):
        return JSONResponse({"detail": "Expected a JSON object"}, status_code=400)
    config, errors = validate_config(data)
    if errors:
        return JSONResponse({"detail": "Invalid configuration", "errors": errors}, status_code=422)
    job = await start_job(config)
    return job.summary()


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
        return overpass_servers.normalize(os.environ.get("OVERPASS_URL"))
    except ValueError:
        return overpass_servers.AUTO


@app.get("/api/overpass/servers")
def overpass_server_list():
    return {
        "default": default_overpass(),
        "servers": [{"url": url, "label": label} for url, label in overpass_servers.SERVERS],
    }


@app.post("/api/overpass/check")
async def overpass_check(request: Request):
    """Health-check the known servers (plus an optional custom URL) in parallel."""
    try:
        data = await request.json()
    except json.JSONDecodeError:
        data = {}
    urls = [url for url, _ in overpass_servers.SERVERS]
    custom = data.get("custom") if isinstance(data, dict) else None
    if custom:
        try:
            custom = overpass_servers.normalize(custom)
        except ValueError as e:
            return JSONResponse({"detail": str(e), "errors": {"overpass_url": str(e)}}, status_code=422)
        if custom != overpass_servers.AUTO and custom not in urls:
            urls.append(custom)
    return await asyncio.to_thread(overpass_servers.check_servers, urls)


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
    parser = argparse.ArgumentParser(description="Web interface for the map poster generator")
    parser.add_argument("--host", default="127.0.0.1", help="Address to bind (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8000, help="Port to listen on (default: 8000)")
    args = parser.parse_args()
    print(f"Map Poster Generator web UI: http://{args.host}:{args.port}/", flush=True)
    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
