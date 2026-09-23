# Proposal

## Why

The existing `--format svg` output is a matplotlib export. It has filled polygons, gradient raster images, stroke widths in points and TTF text. A pen plotter cannot draw any of that directly. Users want to draw posters with a pen plotter, and every mark has to be a pen path in real paper units. That output can only be computed once the pen width and the final paper size in millimetres are known.

## What Changes

- Add a new output format, `--format plotter`, that writes a plotter-ready `.svg`: stroked paths only, with no fills, gradients or raster images.
- Add `--pen-width <mm>` to configure the pen (stroke) width. The pen width sets how many parallel strokes a wide road needs and how far apart the hatch lines are.
- Add `--width-mm <mm>` and `--height-mm <mm>` to set the final physical size. The SVG uses millimetre units (`width="…mm"`, with a `viewBox` in mm). All geometry is converted from projected metres to mm on the page. If these flags are not given, the existing `--width`/`--height` in inches are converted.
- Add `--hatch-spacing <mm>` (defaults to the pen width) to control hatch density.
- Roads: each road-hierarchy class gets a target width in mm. That width is filled with as many parallel pen strokes as it needs, as concentric offsets of the merged road outline. Roads narrower than or equal to the pen width become a single centerline stroke. Road classes that sit higher in the hierarchy knock out the classes below them, so the pen does not draw twice over the same ink.
- Water and parks: polygons are hatch-filled with parallel lines. Roads are knocked out of the hatching.
- Text: the city, country, coordinates, divider and attribution are drawn with a single-stroke (Hershey) font. The map is knocked out behind the text block so the pen does not cross the letters.
- Pens: paths are grouped into Inkscape/vpype-compatible layers, one layer per distinct theme colour. The user can swap pens between layers. The background colour and the gradient fades are not drawn.
- Existing `png`/`svg`/`pdf` output is unchanged.

## Capabilities

### New Capabilities
- `plotter-svg-export`: generates a plotter-ready, millimetre-scaled SVG made only of stroked paths. It covers the pen width, the physical size, multi-stroke road widths, hatch fills, single-stroke text and one layer per colour.

### Modified Capabilities
<!-- None: no existing specs in openspec/specs/ -->

## Impact

- `create_map_poster.py`: CLI arguments, format dispatch in `create_poster` (the data fetching and the crop logic are reused), and output filename extension handling.
- New module `plotter_svg.py`: geometry-to-paths conversion, hatching, text and the SVG writer. It is listed in `pyproject.toml` `py-modules` and copied in the `Dockerfile`.
- New dependency: `Hershey-Fonts`, a pure-Python single-stroke font package. It goes in `pyproject.toml` and `requirements.txt`. `pytest` is added as a dev requirement for new unit tests.
- Docs: README options table and examples. `test/all_variations.sh` gets a plotter example.
