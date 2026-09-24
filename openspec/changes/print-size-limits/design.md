# Design

## Context

- `create_map_poster.main` clamps `width`/`height` above `MAX_SIZE_MM = 500` to 500 for every non-plotter format, with a "⚠ … enforced as 500 mm" line. Each side is clamped on its own, so the aspect ratio, the fetch radius (`compensated_dist` depends on the aspect ratio) and the crop all change.
- PNG is written by matplotlib's Agg backend at `--dpi` (default 300). Agg refuses images over 65,535 px per side. Memory grows with the pixel count: RGBA at about 4 bytes per pixel, plus PNG encoding buffers.
- `web_app.validate_location` rejects print sizes over 500 mm. `preview_size()` already scales raster previews down to 500 mm on the long side, keeping the aspect ratio. Text scales with `min(width, height)`, so a scaled preview looks the same as the full poster.
- The export has no dpi control in the web UI: the CLI's 300 dpi default is used.

## Goals / Non-Goals

**Goals:**
- Never change the requested poster size silently.
- Put the only real limit (PNG pixels) where the user can fix it: at the format and dpi choice in Customize, not at the size in Location.

**Non-Goals:**
- Tiled or streamed PNG rendering beyond the limit.
- Limits based on detected machine memory.
- A dpi option for PDF/SVG rasterised content (none is rasterised).

## Decisions

### 1. Pixel limit of 200 MP and 65,535 px per side
`png_pixels(width_mm, height_mm, dpi)` returns `(round(w/25.4·dpi), round(h/25.4·dpi))`, the same rounding matplotlib uses for the canvas.

- The limits are `MAX_PNG_PIXELS = 200_000_000` and `MAX_PNG_SIDE = 65_535`.
- 200 MP allows A0 at 300 dpi (139.5 MP), and needs about 0.8 GB for the RGBA buffer, which is acceptable for a desktop or container.
- `max_png_dpi(w, h)` finds the highest integer dpi that satisfies both limits. It starts from the closed form `floor(sqrt(limit / (w·h/25.4²)))` and adjusts for rounding.

*Alternative:* keep an mm limit but raise it. That is rejected, because the cost depends on dpi, not mm.

### 2. Validate in the CLI; the web mirrors it
The CLI check runs with the other argument validation, before geocoding, and is the authority. `web_app.validate_customize` imports nothing from the CLI (a heavy import). It duplicates the two constants and the rounding, so it can answer quickly. A test asserts that the two agree for a set of sizes.

### 3. The web UI: dpi field in Customize, limit feedback computed client-side
- The dpi field is shown for PNG in the print workflow.
- The client computes the pixel size from the loaded width and height for instant feedback: pixel size, a warning above 100 MP, and an error with "Use N dpi" over the limit.
- The server enforces the limit on export with a 422 on `dpi`.
- Previews ignore the export dpi and keep `preview_size()` and `preview_dpi()`, so a huge print poster previews as fast as a small one.

### 4. Location accepts any positive print size
The workflow card and size hint text drop the 500 mm limit. The load's raster preview is already scaled.

## Risks / Trade-offs

- [Very large vector posters (e.g. 3 × 2 m PDF) produce files that some viewers render slowly.] → The file size is dominated by the map data, not the page size, so this is acceptable. The README notes it.
- [A 200 MP PNG export can take minutes and about 1 GB of RAM inside the container.] → The warning above 100 MP, and the existing cancel button.
- [Two changes (`plotter-pen-colors` and this one) modify "Choose the workflow".] → Archive them one after the other. The second archive must merge onto the already updated requirement text.

## Migration Plan

- CLI scripts that relied on silent clamping now fail with a clear error for oversized PNGs, or get the exact requested size for SVG/PDF (the fixed behaviour).
- There is no data migration.
