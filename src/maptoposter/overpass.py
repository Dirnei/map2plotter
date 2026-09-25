"""
OpenStreetMap (Overpass API) Servers

Known public Overpass servers, a quick health check, and automatic fallback so
poster generation keeps working when the main server is overloaded or down.
"""

import time
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlparse

import requests

AUTO = "auto"

# Public servers in fallback order: (base URL, label)
SERVERS = [
    ("https://overpass-api.de/api", "overpass-api.de (main)"),
    ("https://lz4.overpass-api.de/api", "lz4.overpass-api.de"),
    ("https://z.overpass-api.de/api", "z.overpass-api.de"),
    ("https://maps.mail.ru/osm/tools/overpass/api", "maps.mail.ru"),
    ("https://overpass.private.coffee/api", "overpass.private.coffee"),
    ("https://overpass.kumi.systems/api", "overpass.kumi.systems"),
]

CHECK_TIMEOUT = 15  # seconds per server for the health check
MAX_ATTEMPTS = 3  # attempts per request when a server answers 429/504 (OSMnx would retry forever)

# Tiny query (a node count in a ~100 m box) to test whether a server answers
CHECK_QUERY = "[out:json][timeout:10];node(47.735,12.459,47.736,12.460);out count;"
USER_AGENT = "maptoposter (https://github.com/originalankur/maptoposter)"


class OverpassError(RuntimeError):
    """Raised when no OpenStreetMap server could answer a request."""


class OverpassBusyError(RuntimeError):
    """Raised when a server keeps answering 429/504 after MAX_ATTEMPTS."""


def normalize(url):
    """
    Turn a user-supplied server into an OSMnx base URL (without '/interpreter').

    Returns 'auto' unchanged; raises ValueError for anything that is not an http(s) URL.
    """
    value = (url or AUTO).strip()
    if value.lower() == AUTO:
        return AUTO
    parsed = urlparse(value)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise ValueError(f"Not an http(s) URL: {value!r}")
    value = value.rstrip("/")
    for suffix in ("/interpreter", "/status"):
        if value.endswith(suffix):
            value = value[: -len(suffix)]
    return value


def hostname(url):
    return urlparse(url).netloc or url


def uses_slot_status(url):
    """
    Whether OSMnx should wait for a free slot via the server's /status page.

    Only the overpass-api.de servers hand out per-client slots. Servers without a
    rate limit (e.g. maps.mail.ru) have no slot line on /status, and OSMnx then
    re-checks the status every 5 s forever, so their check is switched off.
    """
    host = hostname(url)
    return host == "overpass-api.de" or host.endswith(".overpass-api.de")


def check_server(url, timeout=CHECK_TIMEOUT):
    """Send the test query to one server; returns {url, ok, ms, error}."""
    start = time.monotonic()
    try:
        response = requests.post(
            url.rstrip("/") + "/interpreter",
            data={"data": CHECK_QUERY},
            timeout=timeout,
            headers={"User-Agent": USER_AGENT},
        )
        ms = round((time.monotonic() - start) * 1000)
        if response.status_code != 200:
            return {"url": url, "ok": False, "ms": ms, "error": f"HTTP {response.status_code} {response.reason}"}
        elements = response.json().get("elements", [])
        if not any(e.get("type") == "count" for e in elements):
            return {"url": url, "ok": False, "ms": ms, "error": "Unexpected response"}
        return {"url": url, "ok": True, "ms": ms, "error": None}
    except requests.exceptions.Timeout:
        error = f"No answer within {timeout} s"
    except requests.exceptions.SSLError:
        error = "TLS/SSL error"
    except requests.exceptions.ConnectionError:
        error = "Connection failed"
    except (requests.exceptions.RequestException, ValueError) as e:
        error = type(e).__name__
    return {"url": url, "ok": False, "ms": round((time.monotonic() - start) * 1000), "error": error}


def check_servers(urls=None, timeout=CHECK_TIMEOUT):
    """Check several servers in parallel; results keep the input order."""
    urls = urls or [url for url, _ in SERVERS]
    with ThreadPoolExecutor(max_workers=len(urls)) as pool:
        return list(pool.map(lambda u: check_server(u, timeout), urls))


def candidates(choice, log=print, check=check_servers):
    """
    Servers to try, in order.

    A specific server is used on its own. 'auto' checks all known servers and
    returns the healthy ones first (in fallback order), then the others.
    """
    if choice != AUTO:
        return [choice]
    log("Checking OpenStreetMap servers...")
    results = check(None)
    healthy = [r["url"] for r in results if r["ok"]]
    unhealthy = [r["url"] for r in results if not r["ok"]]
    if healthy:
        log(f"✓ Available: {', '.join(hostname(u) for u in healthy)}")
    else:
        log("⚠ No OpenStreetMap server passed the check; trying all of them")
    return healthy + unhealthy


def _server_errors():
    from osmnx._errors import ResponseStatusCodeError

    return (requests.exceptions.RequestException, ResponseStatusCodeError, OverpassBusyError)


def _short(error):
    text = str(error).strip().splitlines()[0] if str(error).strip() else type(error).__name__
    return text if len(text) <= 160 else text[:157] + "..."


def run(call, servers, log=print):
    """
    Run an OSMnx download, falling back to the next server on server errors.

    Args:
        call: Function doing the download (reads osmnx.settings.overpass_url)
        servers: Ordered list of base URLs (see candidates)
        log: Function for progress/warning messages

    Returns:
        (result of call, URL of the server that answered)

    Raises:
        OverpassError: If every server failed. Other errors (e.g. no data in the
        area) are raised unchanged.
    """
    import osmnx as ox

    errors = []
    for i, url in enumerate(servers):
        ox.settings.overpass_url = url
        ox.settings.overpass_rate_limit = uses_slot_status(url)
        try:
            return call(), url
        except _server_errors() as e:
            errors.append(f"{hostname(url)}: {_short(e)}")
            if i + 1 < len(servers):
                log(f"⚠ {hostname(url)} failed ({_short(e)}); trying {hostname(servers[i + 1])}")
    raise OverpassError("; ".join(errors) if errors else "no server to try")


def limit_retries(max_attempts=MAX_ATTEMPTS, log=print):
    """
    Cap OSMnx's retries on 429/504 answers.

    OSMnx pauses and retries such requests recursively without limit, so an
    overloaded server would block forever and the fallback would never happen.
    The recursive call goes through the module attribute, so wrapping it counts
    the attempts of one request.
    """
    from osmnx import _overpass, settings

    original = _overpass._overpass_request
    if getattr(original, "_attempt_limited", False):
        return
    depth = [0]

    def limited(data):
        depth[0] += 1
        try:
            if depth[0] > max_attempts:
                raise OverpassBusyError(
                    f"{hostname(settings.overpass_url)} still busy (429/504) after {max_attempts} attempts"
                )
            if depth[0] > 1:
                log(f"  {hostname(settings.overpass_url)} is busy, retry {depth[0] - 1}/{max_attempts - 1}...")
            return original(data)
        finally:
            depth[0] -= 1

    limited._attempt_limited = True
    _overpass._overpass_request = limited
