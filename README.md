# City Map Poster Generator

Generate beautiful, minimalist map posters for any city in the world.

<img src="docs/images/singapore_neon_cyberpunk_20260118_153328.png" width="250">
<img src="docs/images/dubai_midnight_blue_20260118_140807.png" width="250">

## Examples


| Country      | City           | Theme           | Poster |
|:------------:|:--------------:|:---------------:|:------:|
| USA          | San Francisco  | sunset          | <img src="docs/images/san_francisco_sunset_20260118_144726.png" width="250"> |
| Spain        | Barcelona      | warm_beige      | <img src="docs/images/barcelona_warm_beige_20260118_140048.png" width="250"> |
| Italy        | Venice         | blueprint       | <img src="docs/images/venice_blueprint_20260118_140505.png" width="250"> |
| Japan        | Tokyo          | japanese_ink    | <img src="docs/images/tokyo_japanese_ink_20260118_142446.png" width="250"> |
| India        | Mumbai         | contrast_zones  | <img src="docs/images/mumbai_contrast_zones_20260118_145843.png" width="250"> |
| Morocco      | Marrakech      | terracotta      | <img src="docs/images/marrakech_terracotta_20260118_143253.png" width="250"> |
| Singapore    | Singapore      | neon_cyberpunk  | <img src="docs/images/singapore_neon_cyberpunk_20260118_153328.png" width="250"> |
| Australia    | Melbourne      | forest          | <img src="docs/images/melbourne_forest_20260118_153446.png" width="250"> |
| UAE          | Dubai          | midnight_blue   | <img src="docs/images/dubai_midnight_blue_20260118_140807.png" width="250"> |
| USA          | Seattle        | emerald         | <img src="docs/images/seattle_emerald_20260124_162244.png" width="250"> |

## Installation

### With uv (Recommended)

Make sure [uv](https://docs.astral.sh/uv/) is installed. In a clone of this repository, `uv sync` creates a virtual environment with the locked dependencies and installs the `maptoposter` package into it. `uv run` then starts its commands:

```bash
uv sync
uv run maptoposter --city "Paris" --country "France"   # poster CLI
uv run maptoposter-web                                 # web interface
```

### With pip + venv

```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
pip install -e .
maptoposter --city "Paris" --country "France"
```

`python -m maptoposter` works the same as `maptoposter`. Posters are written to `posters/` and map data is cached in `cache/`, both in the current directory (set `CACHE_DIR` to use another cache directory).

### With Docker Compose (web interface)

```bash
docker compose up -d        # builds the image and serves http://localhost:8000/
docker compose down         # stop
```

Posters are saved to `./posters` and map data is cached in `./cache`. To use another host port, run `MAPTOPOSTER_PORT=9000 docker compose up -d`. To preselect an OpenStreetMap server, run e.g. `OVERPASS_URL=https://lz4.overpass-api.de/api docker compose up -d` (see [OpenStreetMap Servers](#openstreetmap-servers)). The compose file publishes the port on `127.0.0.1` only, because the web interface has no authentication.

To use the CLI with the same image and volumes:

```bash
docker compose run --rm maptoposter --city "Paris" --country "France"
```

### With Docker

With no arguments the container starts the web interface. With `--options` it runs the CLI:

```bash
# Web interface on http://localhost:8000/
docker run --rm -p 127.0.0.1:8000:8000 -v $(pwd)/posters:/app/posters -v $(pwd)/cache:/app/cache \
  ghcr.io/originalankur/maptoposter:latest
```

Run the CLI with docker:

```bash
# Basic usage
docker run --rm -v $(pwd)/posters:/app/posters -v $(pwd)/cache:/app/cache \
  ghcr.io/originalankur/maptoposter:latest --city "Paris" --country "France"

# With custom theme and distance
docker run --rm -v $(pwd)/posters:/app/posters -v $(pwd)/cache:/app/cache \
  ghcr.io/originalankur/maptoposter:latest --city "New York" --country "USA" --theme noir --distance 12000

# With all options
docker run --rm -v $(pwd)/posters:/app/posters -v $(pwd)/cache:/app/cache \
  ghcr.io/originalankur/maptoposter:latest --city "Tokyo" --country "Japan" \
  --display-city "東京" --display-country "日本" \
  --font-family "Noto Sans JP" --theme japanese_ink --distance 15000

# List available themes
docker run --rm ghcr.io/originalankur/maptoposter:latest --list-themes

# Generate for all themes
docker run --rm -v $(pwd)/posters:/app/posters -v $(pwd)/cache:/app/cache \
  ghcr.io/originalankur/maptoposter:latest --city "Paris" --country "France" --all-themes
```

**Note**: The `-v $(pwd)/posters:/app/posters` and `-v $(pwd)/cache:/app/cache` flags mount local directories so that generated posters and cached data persist on your host machine. 

**Windows users**: 
- PowerShell: Use `$PWD` instead of `$(pwd)`
- CMD: Use `%cd%` instead of `$(pwd)`

## Usage

### Generate Poster

If you're using `uv`:
```bash
uv run maptoposter --city <city> --country <country> [options]
```

Otherwise (pip + venv, with the environment activated):
```bash
maptoposter --city <city> --country <country> [options]
```

### Web Interface

Rather than typing CLI flags, you can configure a poster in your browser:

```bash
maptoposter-web              # then open http://127.0.0.1:8000/
maptoposter-web --port 9000  # use another port
```

Prefix the commands with `uv run` if you use uv. The server uses `posters/` and `cache/` in the directory it is started from, like the CLI.

The page works in two steps:

1. **Location**: first choose what you are making: a **Print poster** (PNG, SVG or PDF) or a **Pen plotter** SVG. Any poster size works. Then enter the city, country (or exact coordinates), distance, poster size and OpenStreetMap server (automatic fallback, or a fixed server; **Check servers** shows which ones are up). **Load map** downloads the data once, streaming the generator's output, and shows a quick preview.
2. **Customize**: only the options of your workflow. For print posters that is theme, labels, font and file format. For the pen plotter it is the **Pens** list, labels, pen width, fill mode, line spacing and water outline. Every change re-renders the preview from the loaded data with `--cache-only`, so nothing is downloaded again.

   **Pens:** each element (water, parks, each road class, text) gets a colour picker. The map layers also get a *Draw* toggle. Elements with the same colour share one pen and one Inkscape layer; the list shows how many pens you need. Start from any theme's colours or use *Single pen*. Colour changes apply to the preview instantly, without re-rendering, and the export passes them as `--color` options. Plotter previews are shown on white paper. **Export poster** writes the full-resolution poster to `posters/`, optionally one per theme.

Zoom into the preview with **+ / − / Fit** (or the `+`, `-` and `0` keys) and Ctrl + mouse wheel. Move around with the **Pan** tool or the middle mouse button. Plotter previews are vector and stay sharp at any zoom.

In the Customize step, you can edit the preview directly:
- **Erase ▭ / Erase ✎**: drag a rectangle or draw a shape to remove the map there. Text is kept.
- **Select**: click an erased region, then press **Delete region** (or the Delete key).
- **Move text**: drag the city, country, coordinates or divider.
- **Show / hide**: turn single text lines or map layers (water, parks, each road class) on or off.
- **Undo / Redo** (Ctrl+Z / Ctrl+Y) and **Reset edits**.

Edits are stored in page millimetres and applied again on every re-render and export (see [Edit lists](#edit-lists)), so switching the theme, format or pen keeps them. Loading a different location or size clears them after a confirmation.

The page also shows the exact `maptoposter` command of the last load or export, and lists everything in `posters/`. Previews are kept in `cache/web/` and do not appear there. One job runs at a time; a newer preview replaces one that is still rendering.

With Docker, run `docker compose up -d` or start the container without arguments (see [With Docker Compose](#with-docker-compose-web-interface)).

> **Note:** the web interface has no authentication. By default it only listens on `127.0.0.1`. Use `--host 0.0.0.0` (or publish the container port on all interfaces) only on a trusted network, because anyone who can reach the port can start generation jobs and download posters.

### Required Options

| Option | Short | Description |
|--------|-------|-------------|
| `--city` | `-c` | City name (used for geocoding) |
| `--country` | `-C` | Country name (used for geocoding) |

### Optional Flags

| Option | Short | Description | Default |
|--------|-------|-------------|---------|
| **OPTIONAL:** `--latitude` | `-lat` | Override latitude center point (use with --longitude) | |
| **OPTIONAL:** `--longitude` | `-long` | Override longitude center point (use with --latitude) | |
| **OPTIONAL:** `--country-label` | | Override country text displayed on poster | |
| **OPTIONAL:** `--theme` | `-t` | Theme name | terracotta |
| **OPTIONAL:** `--distance` | `-d` | Map radius in meters | 18000 |
| **OPTIONAL:** `--list-themes` | | List all available themes | |
| **OPTIONAL:** `--all-themes` | | Generate posters for all available themes | |
| **OPTIONAL:** `--width` | `-W` | Poster width in mm (any size; PNG is limited by pixels, see below) | 300 |
| **OPTIONAL:** `--height` | `-H` | Poster height in mm | 400 |
| **OPTIONAL:** `--format` | `-f` | Output format: `png`, `svg`, `pdf` or `plotter` | png |
| **OPTIONAL:** `--overpass-url` | | OpenStreetMap (Overpass API) server URL, or `auto` | `$OVERPASS_URL` or `auto` |
| **OPTIONAL:** `--cache-only` | | Never download map data or geocode; fail if the area is not cached | |
| **OPTIONAL:** `--output` | `-o` | Write the poster to this file instead of `posters/<city>_<theme>_<timestamp>` (extension must match the format; not with `--all-themes`) | |
| **OPTIONAL:** `--dpi` | | Resolution of PNG output | 300 |
| **OPTIONAL:** `--edits` | | JSON edit list to apply (see [Edit lists](#edit-lists)) | |
| **OPTIONAL:** `--color` | | Override one theme colour, e.g. `--color water=#1f5fa8` (repeatable). Keys: `bg`, `text`, `gradient_color`, `water`, `parks`, `road_motorway`, `road_primary`, `road_secondary`, `road_tertiary`, `road_residential`, `road_default` | |

### OpenStreetMap Servers

Street, water and park data come from the public Overpass API, which is sometimes overloaded or down. By default (`--overpass-url auto`) the generator:
1. checks the known public servers in parallel;
2. downloads from the first one that answered;
3. falls back to the next server if a download fails. It gives up on a server that keeps answering "busy" (429/504) after 3 attempts.

To use one specific server, pass it with `--overpass-url` or set the `OVERPASS_URL` environment variable, e.g. `--overpass-url https://lz4.overpass-api.de/api`. Both the `/api` base URL and the full `/api/interpreter` URL work. Known public servers are `overpass-api.de`, `lz4.overpass-api.de`, `z.overpass-api.de`, `maps.mail.ru/osm/tools/overpass`, `overpass.private.coffee` and `overpass.kumi.systems`.

In the web interface, the **Map data** section has a dropdown for the server and a **Check servers** button that shows which servers answer right now.

### Pen Plotter Output

`--format plotter` writes an SVG that a pen plotter can draw directly. It contains only stroked paths: no fills, gradients, raster images or font text. The page is sized in millimetres (1 SVG unit = 1 mm).

| Option | Description | Default |
|--------|-------------|---------|
| `--pen-width` | Pen (stroke) width in mm. Wide roads get as many parallel strokes as they need, and hatch spacing is based on this | 0.3 |
| `--width` | Final poster width in mm (same option as for the other formats) | 300 |
| `--height` | Final poster height in mm (same option as for the other formats) | 400 |
| `--hatch-spacing` | Distance between fill lines for water and parks, in mm (must be ≥ pen width) | pen width |
| `--water-fill` / `--parks-fill` | `hatch` (parallel lines) or `concentric` (contours following the shape) | hatch |
| `--water-spacing` / `--parks-spacing` | Fill line spacing for that area type, in mm (must be ≥ pen width) | `--hatch-spacing` |
| `--water-outline` | Also stroke the shoreline of water areas (the fill then keeps one spacing away from it) | off |

How the poster is turned into pen paths:
- **Roads** keep the road hierarchy. A road wider than the pen is filled with parallel strokes. Narrower roads get a single centerline. Where roads overlap, the more important road is the only one drawn.
- **Water and parks** are hatch-filled at different angles, or filled with concentric contours. Roads are left out of the fill. Water can get an outline.
- **Text** is drawn with a single-stroke (Hershey) font, and the map is cleared behind it. Accented letters are drawn without their accents. Scripts the font cannot draw (e.g. CJK) are skipped with a warning, so use a Latin `--display-city` for those.
- **Pens:** each colour gets its own Inkscape layer, so you can swap pens between layers. Inside a layer, each element type (water, parks, each road class, text) has its own labelled group. Set single colours with `--color`, e.g. `--color water=#1f5fa8`. The background colour is not drawn; use coloured paper instead.

```bash
# A3 portrait poster for a 0.3 mm fineliner
maptoposter -c "Venice" -C "Italy" -d 3000 --format plotter --width 297 --height 420 --pen-width 0.3

# Thicker pen with sparser hatching for faster plots
maptoposter -c "Paris" -C "France" --format plotter --width 300 --height 400 --pen-width 0.5 --hatch-spacing 1.5

# Outlined water with concentric fill, sparse parks
maptoposter -c "Amsterdam" -C "Netherlands" -d 4000 -f plotter --water-outline --water-fill concentric --water-spacing 0.8 --parks-spacing 2
```

**Tip:** paths are already sorted to keep pen-up travel short. To optimise further, post-process the file with [vpype](https://github.com/abey79/vpype), which keeps the layers:

```bash
vpype read posters/venice_terracotta_*.svg linemerge linesort write --page-size 297x420mm optimized.svg
```

### Edit lists

`--edits <file>` applies manual changes to any format and theme. The web interface's editor writes this file for you. All positions are in page millimetres, measured from the top-left corner:

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

### Multilingual Support - i18n

Display city and country names in your language with custom fonts from google fonts:

| Option | Short | Description |
|--------|-------|-------------|
| `--display-city` | `-dc` | Custom display name for city (e.g., "東京") |
| `--display-country` | `-dC` | Custom display name for country (e.g., "日本") |
| `--font-family` | | Google Fonts family name (e.g., "Noto Sans JP") |

**Examples:**

```bash
# Japanese
maptoposter -c "Tokyo" -C "Japan" -dc "東京" -dC "日本" --font-family "Noto Sans JP"

# Korean
maptoposter -c "Seoul" -C "South Korea" -dc "서울" -dC "대한민국" --font-family "Noto Sans KR"

# Arabic
maptoposter -c "Dubai" -C "UAE" -dc "دبي" -dC "الإمارات" --font-family "Cairo"
```

**Note**: Fonts are automatically downloaded from Google Fonts and cached locally in `cache/fonts/`.

### Resolution Guide (300 DPI)

PNG output is rendered at 300 DPI by default (`--dpi` changes it). Use these values for `--width` and `--height` to target specific resolutions:

| Target | Resolution (px) | Size in mm (`--width` / `--height`) |
|--------|-----------------|------------------|
| **Instagram Post** | 1080 x 1080 | 91.4 x 91.4 |
| **Mobile Wallpaper** | 1080 x 1920 | 91.4 x 162.6 |
| **HD Wallpaper** | 1920 x 1080 | 162.6 x 91.4 |
| **4K Wallpaper** | 3840 x 2160 | 325.1 x 182.9 |
| **A4 Print** | 2480 x 3508 | 210 x 297 |
| **A0 Print** | 9933 x 14043 | 841 x 1189 |

**Size limits:** SVG, PDF and plotter output have no size limit. A PNG may have at most 200 megapixels and 65,535 px per side. Larger requests fail before downloading, and the error names the highest dpi that fits. For example, 1000 × 1500 mm fits at up to 293 dpi. The poster size is never changed silently.

### Examples

#### Basic Examples
```bash
# Simple usage with default theme
maptoposter -c "Paris" -C "France"

# With custom theme and distance
maptoposter -c "New York" -C "USA" -t noir -d 12000
```

#### Multilingual Examples (Non-Latin Scripts)

Display city names in their native scripts:

```bash
# Japanese
maptoposter -c "Tokyo" -C "Japan" -dc "東京" -dC "日本" --font-family "Noto Sans JP" -t japanese_ink

# Korean
maptoposter -c "Seoul" -C "South Korea" -dc "서울" -dC "대한민국" --font-family "Noto Sans KR" -t midnight_blue

# Thai
maptoposter -c "Bangkok" -C "Thailand" -dc "กรุงเทพมหานคร" -dC "ประเทศไทย" --font-family "Noto Sans Thai" -t sunset

# Arabic
maptoposter -c "Dubai" -C "UAE" -dc "دبي" -dC "الإمارات" --font-family "Cairo" -t terracotta

# Chinese (Simplified)
maptoposter -c "Beijing" -C "China" -dc "北京" -dC "中国" --font-family "Noto Sans SC"

# Khmer
maptoposter -c "Phnom Penh" -C "Cambodia" -dc "ភ្នំពេញ" -dC "កម្ពុជា" --font-family "Noto Sans Khmer"
```

#### Advanced Examples
```bash
# Iconic grid patterns
maptoposter -c "New York" -C "USA" -t noir -d 12000           # Manhattan grid
maptoposter -c "Barcelona" -C "Spain" -t warm_beige -d 8000   # Eixample district

# Waterfront & canals
maptoposter -c "Venice" -C "Italy" -t blueprint -d 4000       # Canal network
maptoposter -c "Amsterdam" -C "Netherlands" -t ocean -d 6000  # Concentric canals
maptoposter -c "Dubai" -C "UAE" -t midnight_blue -d 15000     # Palm & coastline

# Radial patterns
maptoposter -c "Paris" -C "France" -t pastel_dream -d 10000   # Haussmann boulevards
maptoposter -c "Moscow" -C "Russia" -t noir -d 12000          # Ring roads

# Organic old cities
maptoposter -c "Tokyo" -C "Japan" -t japanese_ink -d 15000    # Dense organic streets
maptoposter -c "Marrakech" -C "Morocco" -t terracotta -d 5000 # Medina maze
maptoposter -c "Rome" -C "Italy" -t warm_beige -d 8000        # Ancient layout

# Coastal cities
maptoposter -c "San Francisco" -C "USA" -t sunset -d 10000    # Peninsula grid
maptoposter -c "Sydney" -C "Australia" -t ocean -d 12000      # Harbor city
maptoposter -c "Mumbai" -C "India" -t contrast_zones -d 18000 # Coastal peninsula

# River cities
maptoposter -c "London" -C "UK" -t noir -d 15000              # Thames curves
maptoposter -c "Budapest" -C "Hungary" -t copper_patina -d 8000  # Danube split

# Override center coordinates
maptoposter --city "New York" --country "USA" -lat 40.776676 -long -73.971321 -t noir

# List available themes
maptoposter --list-themes

# Generate posters for every theme
maptoposter -c "Tokyo" -C "Japan" --all-themes
```

### Distance Guide

| Distance | Best for |
|----------|----------|
| 4000-6000m | Small/dense cities (Venice, Amsterdam center) |
| 8000-12000m | Medium cities, focused downtown (Paris, Barcelona) |
| 15000-20000m | Large metros, full city view (Tokyo, Mumbai) |

## Themes

17 themes available in `src/maptoposter/data/themes/`:

| Theme | Style |
|-------|-------|
| `gradient_roads` | Smooth gradient shading |
| `contrast_zones` | High contrast urban density |
| `noir` | Pure black background, white roads |
| `midnight_blue` | Navy background with gold roads |
| `blueprint` | Architectural blueprint aesthetic |
| `neon_cyberpunk` | Dark with electric pink/cyan |
| `warm_beige` | Vintage sepia tones |
| `pastel_dream` | Soft muted pastels |
| `japanese_ink` | Minimalist ink wash style |
| `emerald`      | Lush dark green aesthetic |
| `forest` | Deep greens and sage |
| `ocean` | Blues and teals for coastal cities |
| `terracotta` | Mediterranean warmth |
| `sunset` | Warm oranges and pinks |
| `autumn` | Seasonal burnt oranges and reds |
| `copper_patina` | Oxidized copper aesthetic |
| `monochrome_blue` | Single blue color family |

## Output

Posters are saved to `posters/` directory with format:
```
{city}_{theme}_{YYYYMMDD_HHMMSS}.png
```

## Adding Custom Themes

Create a JSON file in `src/maptoposter/data/themes/` (then run `uv sync` or `pip install -e .` again if you use a non-editable install):

```json
{
  "name": "My Theme",
  "description": "Description of the theme",
  "bg": "#FFFFFF",
  "text": "#000000",
  "gradient_color": "#FFFFFF",
  "water": "#C0C0C0",
  "parks": "#F0F0F0",
  "road_motorway": "#0A0A0A",
  "road_primary": "#1A1A1A",
  "road_secondary": "#2A2A2A",
  "road_tertiary": "#3A3A3A",
  "road_residential": "#4A4A4A",
  "road_default": "#3A3A3A"
}
```

## Project Structure

```
maptoposter/
├── src/maptoposter/
│   ├── poster.py           # Rendering and the maptoposter CLI
│   ├── web.py              # Web interface (maptoposter-web)
│   ├── fonts.py            # Font loading and Google Fonts integration
│   ├── osm_cache.py        # Map data cache
│   ├── overpass.py         # OpenStreetMap (Overpass) servers and fallback
│   ├── plotter.py          # Pen plotter SVG output
│   ├── colors.py / edits.py / size.py
│   ├── paths.py            # Package data and working-directory paths
│   ├── data/themes/        # Theme JSON files
│   ├── data/fonts/         # Default Roboto fonts
│   └── static/             # Web interface files
├── test/                   # pytest suite
├── docs/images/            # README example posters
├── posters/                # Generated posters (git-ignored)
├── cache/                  # Map data, Google Fonts, web previews (git-ignored)
└── README.md
```

## Hacker's Guide

Quick reference for contributors who want to extend or modify the script.

### Architecture Overview

```
┌─────────────────┐     ┌──────────────┐     ┌─────────────────┐
│   CLI Parser    │────▶│  Geocoding   │────▶│  Data Fetching  │
│   (argparse)    │     │  (Nominatim) │     │    (OSMnx)      │
└─────────────────┘     └──────────────┘     └─────────────────┘
                                                     │
                        ┌──────────────┐             ▼
                        │    Output    │◀────┌─────────────────┐
                        │  (matplotlib)│     │   Rendering     │
                        └──────────────┘     │  (matplotlib)   │
                                             └─────────────────┘
```

### Key Functions

| Function | Purpose | Modify when... |
|----------|---------|----------------|
| `get_coordinates()` | City → lat/lon via Nominatim | Switching geocoding provider |
| `create_poster()` | Main rendering pipeline | Adding new map layers |
| `get_edge_colors_by_type()` | Road color by OSM highway tag | Changing road styling |
| `get_edge_widths_by_type()` | Road width by importance | Adjusting line weights |
| `create_gradient_fade()` | Top/bottom fade effect | Modifying gradient overlay |
| `load_theme()` | JSON theme → dict | Adding new theme properties |
| `is_latin_script()` | Detects script for typography | Supporting new scripts |
| `load_fonts()` | Load custom/default fonts | Changing font loading logic |

### Rendering Layers (z-order)

```
z=11  Text labels (city, country, coords)
z=10  Gradient fades (top & bottom)
z=3   Roads (via ox.plot_graph)
z=2   Parks (green polygons)
z=1   Water (blue polygons)
z=0   Background color
```

### OSM Highway Types → Road Hierarchy

```python
# In get_edge_colors_by_type() and get_edge_widths_by_type()
motorway, motorway_link     → Thickest (1.2), darkest
trunk, primary              → Thick (1.0)
secondary                   → Medium (0.8)
tertiary                    → Thin (0.6)
residential, living_street  → Thinnest (0.4), lightest
```

### Typography & Script Detection

The script automatically detects text scripts to apply appropriate typography:

- **Latin scripts** (English, French, Spanish, etc.): Letter spacing applied for elegant "P  A  R  I  S" effect
- **Non-Latin scripts** (Japanese, Arabic, Thai, Korean, etc.): Natural spacing for "東京" (no gaps between characters)

Script detection uses Unicode ranges (U+0000-U+024F for Latin). If >80% of alphabetic characters are Latin, spacing is applied.

### Adding New Features

**New map layer (e.g., railways):**
```python
# In create_poster(), after parks fetch:
try:
    railways = ox.features_from_point(point, tags={'railway': 'rail'}, dist=dist)
except:
    railways = None

# Then plot before roads:
if railways is not None and not railways.empty:
    railways.plot(ax=ax, color=THEME['railway'], linewidth=0.5, zorder=2.5)
```

**New theme property:**
1. Add to theme JSON: `"railway": "#FF0000"`
2. Use in code: `THEME['railway']`
3. Add fallback in `load_theme()` default dict

### Typography Positioning

All text uses `transform=ax.transAxes` (0-1 normalized coordinates):
```
y=0.14  City name (spaced letters for Latin scripts)
y=0.125 Decorative line
y=0.10  Country name
y=0.07  Coordinates
y=0.02  Attribution (bottom-right)
```

### Useful OSMnx Patterns

```python
# Get all buildings
buildings = ox.features_from_point(point, tags={'building': True}, dist=dist)

# Get specific amenities
cafes = ox.features_from_point(point, tags={'amenity': 'cafe'}, dist=dist)

# Different network types
G = ox.graph_from_point(point, dist=dist, network_type='drive')  # roads only
G = ox.graph_from_point(point, dist=dist, network_type='bike')   # bike paths
G = ox.graph_from_point(point, dist=dist, network_type='walk')   # pedestrian
```

### Performance Tips

- Large `dist` values (>20km) = slow downloads + memory heavy
- Cache coordinates locally to avoid Nominatim rate limits
- Use `network_type='drive'` instead of `'all'` for faster renders
- Reduce `dpi` from 300 to 150 for quick previews
