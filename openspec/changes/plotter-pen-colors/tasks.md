# Tasks

## 1. Plotter SVG structure

- [ ] 1.1 Change `build_layers` to keep `(key, polylines)` per colour, and `write_svg` to emit one `<g inkscape:label=key data-key=key>` per element inside each colour layer, with ordering per element group. Verify in `test_plotter_svg.py`: layer count per colour is unchanged, tertiary and default in a shared layer get two groups with only their own paths, element groups set no stroke, and every path is inside exactly one element group.

## 2. CLI colour overrides

- [ ] 2.1 Add `parse_color_overrides` and the repeatable `--color KEY=#RRGGBB` option, validated before any download, and applied on top of each loaded theme (including `--all-themes`). Verify in `test_cli.py`: an unknown key and an invalid hex both exit non-zero without a download, the last duplicate wins, a plotter render with `--color water=#1F5FA8` has a `#1f5fa8` water layer, and a PNG with `--color text=#000000` draws the text in black.
- [ ] 2.2 Document `--color` in `--help`, `print_examples` and the README options table, and check it shows in `--help`.

## 3. Web server

- [ ] 3.1 Add `CustomizeConfig.colors`, validated with the CLI parser (error key `colors`). `customize_args` emits `--color` only for colours that differ from the base theme's JSON. Verify with web tests: an invalid key or hex returns 422, and an export with water changed has exactly `--color water=#1f5fa8` in its command.

## 4. Web frontend

- [ ] 4.1 Build the pens list for plotter mode: rows with colour pickers for the nine elements, visibility toggles for the eight map layers (writing `edits.hidden_layers`), the pen count, and the "Start from theme…" and "Single pen" presets, initialised from the load theme and kept in localStorage. Hide the theme grid and the layer toggles of the Show / hide panel in plotter mode. Verify in the browser that a plotter session shows the pens list and a print session the theme grid.
- [ ] 4.2 Switch the plotter preview to inline SVG (fetch, parse, replace the `<img>`, overlay kept on top), recolour via `style.stroke` on `g[data-key]`, re-apply after each new preview, and keep the stage on white paper. Colour changes must not schedule a preview. Verify in the browser that picking a water colour recolours at once with no new job (`/api/jobs/current` unchanged), and that zoom and the editor tools still work on the inline SVG.
- [ ] 4.3 Send `colors` with preview and export requests. Verify in the browser that after changing water to blue and exporting, the command contains `--color water=…` and the exported file's water layer has that stroke.

## 5. Integration

- [ ] 5.1 Run the full test suite and flake8, and check both are clean.
- [ ] 5.2 Update the README web interface section (the pens list), rebuild and restart the Docker Compose container, and verify the new UI on port 8001.
