# map2plotter reference

Everything in detail: installation options, every CLI option, how posters become pen paths, the web interface, OpenStreetMap servers, edit lists, themes and releases. For a quick start, see the [README](../README.md).

## Installation

### With uv (recommended)

Make sure [uv](https://docs.astral.sh/uv/) is installed. In a clone of this repository, `uv sync` creates a virtual environment with the locked dependencies and installs the `map2plotter` package into it. `uv run` then starts its commands:

```bash
uv sync
uv run map2plotter --city "Paris" --country "France"   # poster CLI
uv run map2plotter-web                                 # web interface
```

### With pip + venv

```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
pip install -e .
map2plotter --city "Paris" --country "France"
```

`python -m map2plotter` works the same as `map2plotter`. Posters are written to `posters/` and map data is cached in `cache/`, both in the current directory (set `CACHE_DIR` to use another cache directory).

### With Docker Compose (web interface)

```bash
docker compose up -d        # builds the image and serves http://localhost:8001/
docker compose down         # stop
```

Posters are saved to `./posters` and map data is cached in `./cache`. To use another host port, run `MAP2PLOTTER_PORT=9000 docker compose up -d`. To preselect an OpenStreetMap server, run e.g. `OVERPASS_URL=https://lz4.overpass-api.de/api docker compose up -d` (see [OpenStreetMap servers](#openstreetmap-servers)). The compose file publishes the port on `127.0.0.1` only, because the web interface has no authentication.

To use the CLI with the same image and volumes:

```bash
docker compose run --rm map2plotter --city "Paris" --country "France"
```

### With Docker

With no arguments the container starts the web interface. With `--options` it runs the CLI:

```bash
# Web interface on http://localhost:8000/
docker run --rm -p 127.0.0.1:8000:8000 -v $(pwd)/posters:/app/posters -v $(pwd)/cache:/app/cache \
  ghcr.io/dirnei/map2plotter:latest

# CLI: an A3 poster of Paris
docker run --rm -v $(pwd)/posters:/app/posters -v $(pwd)/cache:/app/cache \
  ghcr.io/dirnei/map2plotter:latest --city "Paris" --country "France" -W 297 -H 420

# List the themes
docker run --rm ghcr.io/dirnei/map2plotter:latest --list-themes
```

`latest` is the newest release. To stay on one major version, use its tag instead, for example `ghcr.io/dirnei/map2plotter:1` (see [Releases](#releases)). The `-v` flags keep posters and cached map data on your machine. On Windows, use `$PWD` (PowerShell) or `%cd%` (CMD) instead of `$(pwd)`.

## Command line

```bash
map2plotter --city <city> --country <country> [options]
```

Every run writes one SVG to `posters/<city>_<theme>_<timestamp>.svg` (or one per theme with `--all-themes`).

| Option | Short | Description | Default |
|--------|-------|-------------|---------|
| `--city` | `-c` | City name (used for geocoding and as the title) | required |
| `--country` | `-C` | Country name | required |
| `--latitude` / `--longitude` | `-lat` / `-long` | Use this centre point instead of geocoding (set both) | |
| `--distance` | `-d` | Map radius in metres | 18000 |
| `--width` / `--height` | `-W` / `-H` | Poster size in mm, any size | 300 / 400 |
| `--theme` | `-t` | Pen colour preset (see [Themes](#themes)) | terracotta |
| `--all-themes` | | One SVG per theme | |
| `--color` | | Override one pen colour, e.g. `--color water=#1f5fa8` (repeatable) | |
| `--pen-width` | | Pen (stroke) width in mm | 0.3 |
| `--hatch-spacing` | | Distance between fill lines for water and parks, in mm (≥ pen width) | pen width |
| `--water-fill` / `--parks-fill` | | `hatch` (parallel lines) or `concentric` (contours following the shape) | hatch |
| `--water-spacing` / `--parks-spacing` | | Fill line spacing for that area type, in mm (≥ pen width) | `--hatch-spacing` |
| `--water-outline` | | Also stroke the shoreline of water areas | off |
| `--display-city` / `--display-country` | `-dc` / `-dC` | Text on the poster instead of the city/country name | |
| `--country-label` | | Override the country line | |
| `--edits` | | Apply an [edit list](#edit-lists) | |
| `--output` | `-o` | Write to this `.svg` file instead (not with `--all-themes`) | |
| `--cache-only` | | Never download map data or geocode; fail if the area is not cached | |
| `--overpass-url` | | OpenStreetMap server URL, or `auto` | `$OVERPASS_URL` or `auto` |
| `--list-themes` | | List the themes | |

`--color` keys are `text`, `water`, `parks`, `road_motorway`, `road_primary`, `road_secondary`, `road_tertiary`, `road_residential` and `road_default`.

```bash
# A3 portrait poster for a 0.3 mm fineliner
map2plotter -c "Venice" -C "Italy" -d 3000 -W 297 -H 420

# Thicker pen with sparser hatching for faster plots
map2plotter -c "Paris" -C "France" -d 10000 --pen-width 0.5 --hatch-spacing 1.5

# Outlined water with concentric fill, sparse parks
map2plotter -c "Amsterdam" -C "Netherlands" -d 4000 --water-outline --water-fill concentric --water-spacing 0.8 --parks-spacing 2

# Black-ink theme with blue water (two pens)
map2plotter -c "Rome" -C "Italy" -d 8000 -t japanese_ink --color water=#1f5fa8

# Re-render from cached data only (no downloads)
map2plotter -c "Venice" -C "Italy" -d 3000 --cache-only -o venice.svg
```

Distance guide: 4000–6000 m for small or dense cities (Venice, Amsterdam's old centre), 8000–12000 m for a focused downtown (Paris, Barcelona), 15000–20000 m for a large metro (Tokyo, Mumbai).

## How the poster becomes pen paths

- **Roads** keep the road hierarchy. A road wider than the pen is filled with parallel strokes; narrower roads get a single centerline. Where roads overlap, only the more important road is drawn.
- **Water and parks** are hatch-filled at different angles, or filled with concentric contours. Roads are left out of the fill. Water can get an outline; the fill then keeps one spacing away from it.
- **Text** (city, country, coordinates, divider and the OpenStreetMap attribution) is drawn with a single-stroke (Hershey) font, and the map is cleared behind it. The font covers Latin script: accented letters are drawn without their accents, and other scripts (e.g. CJK, Arabic) are skipped with a warning. Use a Latin `--display-city` for those cities.
- **Pens:** every distinct colour becomes its own Inkscape layer, so you can plot one pen after another. Inside a layer, each element type (water, parks, each road class, text) has its own labelled group. There is no background: use coloured paper instead.
- **Size:** the SVG page is in millimetres (1 SVG unit = 1 mm), with every path inside the page.

Paths are already sorted to keep pen-up travel short. To optimise further, post-process the file with [vpype](https://github.com/abey79/vpype), which keeps the layers:

```bash
vpype read posters/venice_terracotta_*.svg linemerge linesort write --page-size 297x420mm optimized.svg
```

In Inkscape, *Layers and Objects* shows one layer per pen; hide all but one to plot (or export) a single pen.

## Web interface

Rather than typing options, you can design a poster in your browser:

```bash
map2plotter-web              # then open http://127.0.0.1:8000/
map2plotter-web --port 9000  # use another port
```

Prefix the commands with `uv run` if you use uv. The server uses `posters/` and `cache/` in the directory it is started from, like the CLI.

The page works in two steps:

1. **Location**: city, country (or exact coordinates), distance, poster size and OpenStreetMap server (automatic fallback, or a fixed server; **Check servers** shows which ones are up). **Load map** downloads the data once, streaming the generator's output, and shows the plotter SVG as the preview.
2. **Customize**: pens, labels, pen width, fill modes, line spacing and water outline. Every change re-renders the preview from the loaded data with `--cache-only`, so nothing is downloaded again.

**Pens:** each element (water, parks, each road class, text) gets a colour picker and, for map layers, a *Draw* toggle. Elements with the same colour share one pen and one Inkscape layer, and the list shows how many pens you need. Start from any theme's colours or use *Single pen*. Colour changes apply to the preview at once, without re-rendering, and the export passes them as `--color` options. **Export poster** writes the SVG to `posters/`, optionally one per theme.

Zoom into the preview with **+ / − / Fit** (or the `+`, `-` and `0` keys) and Ctrl + mouse wheel; the preview is vector and stays sharp. Move around with the **Pan** tool or the middle mouse button.

You can edit the preview directly:
- **Erase ▭ / Erase ✎**: drag a rectangle or draw a shape to remove the map there. Text is kept.
- **Select**: click an erased region, then press **Delete region** (or the Delete key).
- **Move text**: drag the city, country, coordinates or divider.
- **Show / hide**: turn single text lines on or off (map layers are switched in the pens list).
- **Undo / Redo** (Ctrl+Z / Ctrl+Y) and **Reset edits**.

Edits are stored in page millimetres and applied again on every re-render and export (see [Edit lists](#edit-lists)), so changing the pens or fill options keeps them. Loading a different location or size clears them after a confirmation.

The page also shows the exact `map2plotter` command of the last load or export, and lists the SVGs in `posters/`. Previews are kept in `cache/web/` and do not appear there. One job runs at a time; a newer preview replaces one that is still rendering.

> **Note:** the web interface has no authentication. By default it only listens on `127.0.0.1`. Use `--host 0.0.0.0` (or publish the container port on all interfaces) only on a trusted network, because anyone who can reach the port can start generation jobs and download posters.

## OpenStreetMap servers

Street, water and park data come from the public Overpass API, which is sometimes overloaded or down. By default (`--overpass-url auto`) map2plotter:
1. checks the known public servers in parallel;
2. downloads from the first one that answered;
3. falls back to the next server if a download fails. It gives up on a server that keeps answering "busy" (429/504) after 3 attempts.

To use one specific server, pass it with `--overpass-url` or set the `OVERPASS_URL` environment variable, e.g. `--overpass-url https://lz4.overpass-api.de/api`. Both the `/api` base URL and the full `/api/interpreter` URL work. Known public servers are `overpass-api.de`, `lz4.overpass-api.de`, `z.overpass-api.de`, `maps.mail.ru/osm/tools/overpass`, `overpass.private.coffee` and `overpass.kumi.systems`.

Downloaded areas are cached in `cache/`. A later poster of the same place at the same or a smaller distance reuses them, and `--cache-only` guarantees that no request is made at all.

## Edit lists

`--edits <file>` applies manual changes for any theme. The web interface's editor writes this file for you. All positions are in page millimetres, measured from the top-left corner:

```json
{
  "version": 1,
  "erase": [[[20, 20], [80, 20], [80, 60], [20, 60]]],
  "text": {"city": {"dy": -10}, "coords": {"hidden": true}},
  "hidden_layers": ["parks"]
}
```

- `erase`: polygons (at least 3 points) in which roads, water and parks are removed. Text is kept.
- `text`: `city`, `country`, `coords` or `divider`, each with an optional `dx`/`dy` offset in mm and `hidden`.
- `hidden_layers`: any of `water`, `parks`, `road_motorway`, `road_primary`, `road_secondary`, `road_tertiary`, `road_residential`, `road_default`.

The OpenStreetMap attribution is always drawn.

## Themes

A theme is a set of pen colours. The 17 built-in themes live in `src/map2plotter/data/themes/`; `map2plotter --list-themes` lists them with their descriptions.

| Theme | Pens |
|-------|------|
| `terracotta` (default), `autumn`, `sunset` | Warm oranges, reds and browns |
| `japanese_ink`, `contrast_zones`, `gradient_roads` | Black and greys |
| `forest`, `copper_patina` | Greens and teals |
| `ocean`, `monochrome_blue` | Blues |
| `warm_beige`, `pastel_dream` | Soft sepia and pastel tones (light; best with fine, dark-ish pens) |
| `noir`, `blueprint`, `emerald`, `neon_cyberpunk`, `midnight_blue` | Light or metallic pens, made for **dark paper** (white text is invisible on white paper) |

To add a theme, create a JSON file in `src/map2plotter/data/themes/` (then run `uv sync` or `pip install -e .` again if you use a non-editable install):

```json
{
  "name": "My Theme",
  "description": "Description of the theme",
  "text": "#000000",
  "water": "#1F5FA8",
  "parks": "#2E7D32",
  "road_motorway": "#0A0A0A",
  "road_primary": "#1A1A1A",
  "road_secondary": "#2A2A2A",
  "road_tertiary": "#3A3A3A",
  "road_residential": "#4A4A4A",
  "road_default": "#3A3A3A"
}
```

Keys that share a colour share a pen. Other keys (such as `bg` in themes from maptoposter) are ignored.

## Project structure

```
map2plotter/
├── src/map2plotter/
│   ├── poster.py           # Data fetching and the map2plotter CLI
│   ├── plotter.py          # Pen paths, text layout and the SVG writer
│   ├── web.py              # Web interface (map2plotter-web)
│   ├── osm_cache.py        # Map data cache
│   ├── overpass.py         # OpenStreetMap (Overpass) servers and fallback
│   ├── colors.py / edits.py
│   ├── paths.py            # Package data and working-directory paths
│   ├── data/themes/        # Theme JSON files (pen colours)
│   └── static/             # Web interface files
├── test/                   # pytest suite
├── docs/images/            # README examples
├── posters/                # Generated posters (git-ignored)
├── cache/                  # Map data and web previews (git-ignored)
└── README.md
```

Run the tests with `uv run pytest` and the linter with `uv run flake8 src test`.

## Releases

Releases are automated with [release-please](https://github.com/googleapis/release-please). Commit messages follow [Conventional Commits](https://www.conventionalcommits.org/), and their type decides the next version:

| Commit | Example | Next version |
|--------|---------|--------------|
| `fix:` | `fix: keep water outline inside the page` | patch (1.0.0 → 1.0.1) |
| `feat:` | `feat: add a dotted fill mode` | minor (1.0.0 → 1.1.0) |
| `feat!:` / `fix!:` / `refactor!:` | `feat!: rename --hatch-spacing` | major (1.0.0 → 2.0.0) |
| `docs:`, `refactor:`, `test:`, `ci:`, `chore:` | `docs: explain pen widths` | no release on their own |

On every push to `main`, release-please updates an open release pull request that bumps the version in `pyproject.toml` and adds the new entry to [CHANGELOG.md](../CHANGELOG.md). Merging that pull request creates the tag `vX.Y.Z` and the GitHub release. It also publishes the Docker image `ghcr.io/dirnei/map2plotter` with the tags `X.Y.Z`, `X.Y`, `X` and `latest`. Pushes that do not merge the release pull request publish nothing.
