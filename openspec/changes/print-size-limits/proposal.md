# Proposal

## Why

Print posters (PNG, SVG, PDF) are capped at 500 mm per side. The cap comes from the original project's "20 inches, supports 4K" limit, not from a technical constraint:
- SVG and PDF are vector, so their size costs nothing.
- Only PNG has a real cost: pixel count and memory at 300 dpi.

The cap is also dangerous in the CLI. It silently clamps each side to 500 mm, so a 600 × 900 mm request comes out as 500 × 500 mm: a different aspect ratio, a different map crop, and only a warning line in the output. The web interface blocks larger print sizes, which pushes users into the plotter workflow just to get a large SVG or PDF.

## What Changes

- **No size limit for SVG and PDF** output, in the CLI and in the web interface.
- **PNG limited by pixels instead of millimetres:**
  - at most 200 megapixels, and at most 65,535 pixels per side (the renderer's limit)
  - computed from width, height and `--dpi`
  - for scale: A0 at 300 dpi is about 140 MP and allowed; 1 × 1.5 m at 300 dpi is about 209 MP and rejected, but fits at 293 dpi
- **BREAKING (CLI):** width and height are no longer clamped. A PNG over the limit is rejected before any download, with an error that states the pixel count and the highest dpi that would fit. SVG, PDF and plotter output accept any size.
- **Web interface:**
  - Location accepts any size in the print workflow. The workflow cards no longer mention a 500 mm limit.
  - Customize gets a **PNG resolution (dpi)** field (default 300) in the print workflow, shown for PNG.
  - When the PNG would exceed the limit, the field shows the error and the highest possible dpi, with a one-click "Use N dpi". Export is blocked until it fits. Choosing SVG or PDF removes the problem.
  - A soft warning appears above 100 MP ("large file, slow export").
  - Previews stay scaled down, so they are unaffected by the poster size.

## Capabilities

### New Capabilities
<!-- none -->

### Modified Capabilities
- `poster-output`: "Raster resolution" gains the PNG pixel limit and a no-clamping guarantee. A new requirement states that SVG, PDF and plotter output have no size limit.
- `poster-web-ui`: "Choose the workflow" drops the 500 mm print limit and its scenario. "Server-side validation" replaces the mm rule with the PNG pixel rule. A new requirement adds the PNG dpi field with its limit feedback.

## Impact

- `create_map_poster.py`: remove `MAX_SIZE_MM` clamping, add `png_pixels()` and the pixel-limit validation with the suggested-dpi error, update the help texts.
- `web_app.py`: remove the print mm check from `validate_location`. Add `CustomizeConfig.dpi` (PNG only) and pixel-limit validation in `validate_customize` against the loaded size. Export passes `--dpi`. Previews keep the scaled size and their own dpi.
- `web/static/`: the workflow card text, the dpi field with its limit and warning feedback, and the "Use N dpi" action.
- Tests: CLI (no clamp, the PNG limit error with suggested dpi, large SVG/PDF accepted) and web (a large print load is accepted, PNG export over the limit gets 422 on `dpi`, SVG export at the same size is accepted). README tables and the resolution guide.
- **Overlaps with the `plotter-pen-colors` change:** both modify the "Choose the workflow" requirement. Whichever is archived second must merge its delta onto the already updated text.
