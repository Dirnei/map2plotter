# Design

## Context

- `plotter_svg.build_layers(entries)` merges `(key, colour, polylines)` entries into one polyline list per colour. After that, the element identity is lost. `write_svg` then orders each layer's polylines (`order_polylines`) and sets `stroke` on the layer `<g>`.
- The CLI loads a theme into the global `THEME` dict (`load_theme`, once per theme with `--all-themes`). Both renderers read colours only from `THEME`, so an override applied right after loading covers every format.
- The web preview is shown as `<img src="/api/preview?v=N">`. CSS cannot style inside an `<img>`, so any colour change needs a new render (a subprocess that takes seconds).
- The plotter workflow (from the previous change) shows the theme grid labelled "Pen colours", and a separate "Show / hide" panel with text and layer toggles.

## Goals / Non-Goals

**Goals:**
- Colour is presentation only: changing a pen colour never starts a render in the browser.
- The web preview, the exported file and the copyable command always agree on colours.
- One CLI mechanism (`--color`) for all formats, so print and plotter share it.

**Non-Goals:**
- Per-element colour pickers for print posters. They keep themes; `--color` still works there from the CLI.
- A paper colour or a background in plotter output.
- Saving custom pen sets as new theme files.
- Stroke width per pen. There is still one `--pen-width`.

## Decisions

### 1. Element groups inside colour layers
`build_layers` keeps a list of `(key, polylines)` per colour, instead of one flat list. `write_svg` writes, for each colour layer, one child `<g inkscape:label="<key>" data-key="<key>">` per element, and orders polylines within that group.

- The layer structure, which is the pen assignment that Inkscape, AxiDraw and vpype use, stays exactly as today. Nested groups are flattened into their layer by these tools.
- The trade-off is slightly more pen-up travel: ordering can no longer interleave, for example, tertiary and default roads of the same pen. This is small, since each group is already ordered, and the vpype `linesort` tip in the README still applies.

*Alternative:* a `class` or `data-key` on every path. That makes files larger and gives Inkscape users no per-element structure.

### 2. `--color` applied after `load_theme`
`parse_color_overrides(values)` validates `KEY=#RRGGBB` against the theme colour keys (the same set the themes define) and returns a dict. In the theme loop, `THEME = {**load_theme(name), **overrides}`. Validation happens with the other argument checks, before geocoding or download.

### 3. Inline SVG preview with direct recolouring
In plotter mode, the client fetches the preview SVG as text, parses it with `DOMParser`, and places the `<svg>` element in the stage in place of the `<img>`. The editor overlay stays on top.

- Recolouring sets `style.stroke` on every `g[data-key]`. The inline style overrides the stroke inherited from the layer, so an element can take a new colour even when it currently shares a layer with another one.
- The mapping is re-applied after every new preview, so a render that was started before a colour change still shows the current colours.
- Print previews stay `<img>` PNGs.
- The SVG comes from our own server (the CLI output). Only the parsed `<svg>` element is inserted, never HTML.

*Alternative:* CSS variables written into the SVG by the CLI. That would put web-only concerns into the plotter output.

### 4. Pens state lives in the client, the base theme on the server
- The pens list holds `{key: "#rrggbb"}` for the nine plottable keys. It is initialised from the theme used for the load, and kept in `localStorage` as a per-viewer convenience.
- `CustomizeConfig` gains `colors: dict[str, str]`, validated with the same parser as the CLI.
- `customize_args` compares each colour with the base theme's JSON (`theme` stays the base) and emits `--color` only for differences. That keeps the command short and identical to what a CLI user would type.
- Colour changes do not schedule a preview. Previews still send `colors`, so a failed preview's output reflects the real state.

### 5. Show/hide moves into the pens list (plotter)
In plotter mode, the layer toggles live in the pens rows. The "Show / hide" panel keeps only the text line toggles. Toggling a layer still edits `edits.hidden_layers` and re-renders, because hiding roads changes the knockouts for the water and park fills. So hiding is geometry, not presentation.

## Risks / Trade-offs

- [Large plotter SVGs (many MB, e.g. 600 × 900 mm with fine hatching) inserted into the DOM can make zoom and pan sluggish.] → The preview already had to decode this SVG as an image. If profiling shows a problem, a later change can simplify the preview. This is noted, not solved here.
- [The theme's `text` colour for dark themes (e.g. noir: white) is invisible on white paper.] → That is the expected result for a white pen on white paper. The preset picker names the theme, and the single-pen preset gives a quick visible default.
- [Recolouring by inline style shows a colour split that the preview SVG's layers do not reflect (two elements in one layer, shown in different colours).] → Only the export's layering matters, and it is rebuilt by the CLI from the chosen colours.

## Migration Plan

Additive. Existing plotter SVGs gain an extra group level; tools that read layers are unaffected. The CLI without `--color` is unchanged. There is no data migration.
