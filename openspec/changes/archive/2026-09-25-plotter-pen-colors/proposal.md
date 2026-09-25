# Proposal

## Why

In the pen plotter workflow, the colour choice is still the print theme grid. That doesn't fit a plotter:
- A theme bundles a background colour and gradient colours. A plotter has neither: the background is the paper.
- The only way to change a single pen is to switch the whole theme.
- Every colour change starts a full re-render, although the pen paths do not depend on colour at all.

Plotter users think in pens: "water in blue, roads in black, text in red".

## What Changes

- **Pens list (plotter workflow only).** It replaces the theme grid with one row per plottable element:
  - water, parks
  - motorways, primary, secondary, tertiary and residential roads, other roads
  - text

  Each row has a colour picker. The map layer rows also have the show/hide toggle, which moves here from the "Show / hide" layer list. Rows with the same colour share a pen, and the list shows the resulting number of pens.
- **Presets:** "Start from theme…" copies the colours of any theme, and "Single pen" sets every element to one colour (black).
- **No background in plotter previews:** they are shown on white paper; the theme background is no longer used.
- **Instant recolouring:** the plotter preview is embedded as inline SVG, so a colour change is applied in the browser right away, without a new render. A new render still happens when the paths change (pen width, fills, spacing, labels, edits, hidden layers).
- **Per-element groups in the plotter SVG:** inside each per-colour Inkscape layer, the paths of each element type are wrapped in their own group, labelled with the element name. This is what lets the preview recolour one element. It also makes files easier to work with in Inkscape. Layers still correspond to pens.
- **CLI `--color KEY=#RRGGBB`** (repeatable) overrides single theme colours for any format, for example `--color water=#1f5fa8 --color text=#000000`. The web page passes the chosen pen colours this way, so exports and the copyable command match the preview.
- Print posters keep the theme grid unchanged.

## Capabilities

### New Capabilities
- `poster-colors`: overriding single theme colours from the command line (`--color`), for every output format.

### Modified Capabilities
- `plotter-svg-export`: "One layer per pen colour" gains per-element sub-groups inside each layer.
- `poster-web-ui`: "Choose the workflow" no longer uses the theme grid for the plotter. A new requirement adds the pens list, presets, instant recolouring and white-paper previews.

## Impact

- `create_map_poster.py`: the `--color` option (parsed, validated and applied on top of each loaded theme, including with `--all-themes`).
- `plotter_svg.py`: `build_layers` / `write_svg` keep element identity and emit nested groups. Path ordering for short pen-up travel then happens per element group instead of per layer.
- `web_app.py`: `CustomizeConfig.colors` (validated keys and hex values), passed as `--color` for values that differ from the base theme. `get_themes()` already provides the theme colours for the presets.
- `web/static/`: a pens list component, inline SVG preview with direct recolouring, and a white stage in plotter mode.
- Tests: CLI colour parsing and override, nested SVG structure, and the web argument building. README sections for `--color` and the pens list.
- No new dependencies.
