# Design

## Context

- The web UI (`web_app.py` + `web/static/`) runs `create_map_poster.py` as a subprocess for every request. It keeps one `CURRENT_JOB`, streams its output over SSE, and finds results by diffing `posters/` before and after the run.
- Map data already goes through `osm_cache.load_area`. It reuses any cached area that covers the requested radius and crops it. Coordinates are cached by `get_coordinates`. So a re-render with a different theme *usually* does not download. Nothing enforces that, though: a crop miss or a different aspect ratio silently downloads again.
- The fetch radius depends on the poster's aspect ratio (`compensated_dist = dist * max(w,h)/min(w,h) / 4`). For that reason size belongs to the Location step, not to Customize.
- `plotter_svg.render` builds, in order: the text layout (with the knockout polygon), roads per class (knocked out by higher classes and the text), then hatch fills (excluding roads and the text). It ends with `build_layers` / `write_svg`. `fill_area` already implements concentric insets for roads, at a spacing of one pen width.
- The matplotlib path in `create_poster` draws water, parks, roads (`ox.plot_graph`), gradients and text with hard-coded axis fractions.

## Goals / Non-Goals

**Goals:**
- Keep "the CLI is the single rendering engine": the web UI adds no rendering code in Python or JS. It only builds arguments and edit lists.
- Make "no redownload in Customize" a hard guarantee (`--cache-only`), not a cache side effect.
- Edits are data (an edit list in page mm) that every render applies, so they survive theme, format and pen changes.

**Non-Goals:**
- Freehand drawing or adding new strokes or shapes. The editor only removes, moves or hides.
- Editing individual plotter paths by ID. Path identity is not stable across re-renders.
- Keeping sessions across server restarts, or several sessions at once. There is one active session per server, as today.
- Making previews fast by keeping data in a long-lived render worker (see Risks).
- Concentric fill or outlines for png/svg/pdf. Raster output keeps solid fills.

## Decisions

### 1. Two steps on top of the existing subprocess model
The server keeps a single `Session` in memory:
- the validated Location config
- the resolved lat/lon
- the working directory `cache/web/<session-id>/`
- the last preview file
- the current job

Loads, previews and exports are all `Job`s with a `kind` (`load`, `preview` or `export`). The existing SSE and cancel machinery is reused unchanged.

- `POST /api/load` takes the Location config and runs the CLI with `--output <dir>/preview.png --dpi <preview dpi>` and the current theme. On success, the session is marked loaded.
- `POST /api/preview` takes the Customize config plus the edit list and runs with `--cache-only --output <dir>/preview.<png|svg>`. The Location fields come from the session, never from the request, so a preview can't point at a different area.
- `POST /api/export` does the same with `--cache-only` and no `--output`. Results are found by the existing `posters/` diff.
- `GET /api/preview` serves the latest preview file (with a cache-busting query param on the client).

*Alternative:* render in-process (import `create_map_poster`) and keep the graph in memory. That is much faster, but it means refactoring the CLI's module-level globals (`THEME`, `OVERPASS_CHOICE`, `FONTS`) and running matplotlib, which is not thread-safe, off the event loop. It also breaks the "Invoke the existing CLI" contract. It is deferred.

**Coordinates.** Previews and exports pass the same city, country and optional lat/lon as the load. Without lat/lon they rely on the geocode the load cached, and cache-only mode makes a missing geocode a clear error instead of a network call.

### 2. `--cache-only` implemented in `osm_cache.load_area`
`load_area` stays as it is. In cache-only mode, `create_map_poster` passes a `download` that raises a new `NotCachedError` instead of calling Overpass. `fetch_graph` turns that into a fatal "map data is not cached" error. `fetch_features` turns it into the existing warning path. `get_coordinates` raises when there is no cache entry. The server health check is never reached, because it is initialised lazily inside `overpass_download`.

*Alternative:* block the network with an env var or a monkeypatched `requests`. That is fragile and gives an unclear error.

### 3. Preview resolution
PNG previews use `dpi = clamp(round(1200 / (max(w,h) / 25.4)), 30, 150)`, which is about 1200 px on the long side. Plotter previews are the real plotter SVG, because pen spacing is exactly what the user is tuning. For format `svg`/`pdf`, the preview is a PNG, since the look is identical and the browser can't show PDFs inline reliably.

### 4. Edit list: page mm, top-left origin
Both renderers already work in page space. Plotter works in mm with y down. matplotlib works in axes fractions with y up, so it converts with `x/W`, `1 - y/H`. Parsing and validation go in a new small module `poster_edits.py` (dataclasses, no dependencies), shared by the CLI and `web_app.validate_config`, so both reject the same inputs.

How each renderer applies the edits:

**Plotter** (`plotter_svg.render`):
- The union of the erase polygons is added to the existing `knockout` for roads and to `exclude` for area fills and the water outline. Text is not clipped by it, because text is laid out separately.
- `layout_text` gets per-line `dx`/`dy`/`hidden`. The knockout boxes are built from the moved positions, so the knockout follows the text.
- Hidden layers are skipped before their geometry is computed.

**matplotlib** (`create_poster`):
- Hidden layers are not plotted (road classes are filtered from the edges).
- Erase polygons are drawn as `Polygon` patches in `THEME["bg"]` at zorder 9: above the map, below the gradients (10) and text (11). The gradient fades stay continuous and text is unaffected, as the spec requires.
- Text offsets shift the `ax.text` anchor fractions by `dx/W`, `-dy/H`.

The attribution line is not addressable in the schema, so it can't be edited.

### 5. Plotter fills
- `PlotterSettings` gains `water_fill`, `parks_fill`, `water_spacing`, `parks_spacing` and `water_outline`. `render_areas(polygons, mode, spacing, angle, exclude, page)` dispatches to the existing `hatch()` or to a new `concentric(area, spacing, pen)`.
- `concentric` starts at an inset of `pen/2`, steps by `spacing` and drops rings shorter than `2*pen`. It generalises `fill_area`'s loop with a spacing parameter; `fill_area` then calls it with `spacing=pen`.
- For the water outline, the stroke is the boundary of `water ∩ page`, clipped by `difference(exclude)` so it is not drawn through bridges or text. The fill is then computed on `water.buffer(-spacing)`, so the first line keeps a gap from the outline.
- The outline and fill both go into the `water` entry, which is the same layer.

### 6. Frontend structure
The page is plain JS modules without a build step, consistent with today:
- `app.js` holds the step state machine and the API calls
- `editor.js` is the SVG overlay: a `<svg viewBox="0 0 W H">` absolutely positioned over the preview image, so pointer coordinates map to mm through `getScreenCTM().inverse()`
- `form.js` holds the shared field helpers split out of `app.js`

Other client-side details:
- Customize changes are debounced by 500 ms and then `POST /api/preview`.
- The edit list lives on the client, with undo and redo stacks as plain arrays of snapshots. It is sent with every preview and export, and the server writes it to `<dir>/edits.json`.
- Text handle positions for dragging come from a new `GET /api/layout?width=&height=` that returns the default anchor boxes (in mm) for city, country, coords and divider, computed by the same functions the plotter layout uses. That way the drag handles match the rendered text without the client re-implementing the layout.
- `localStorage` keeps form values as today. Edits are not persisted.

### 7. Job arbitration
The rules are given by "Single job and cancellation" in the spec. The implementation checks the current job's `kind` in `start_job`: a running preview is cancelled with the existing `cancel_job` (terminate, then kill after 5 s) before a new job starts. A running load or export makes the request fail with 409. Clients keep the last good preview when a preview is cancelled or fails.

### 8. Workflow chosen in Location (review feedback)
Print posters and pen plotter output have different size limits, options and previews. The size lives in Location, so the workflow (`mode`) is chosen there too and stored with the loaded location. The server then derives the format in plotter mode and rejects plotter output in print mode. This makes the "large poster with SVG format" combination impossible, where every preview used to be rejected silently. Customize shows only the options of that workflow.

*Alternative:* keep the format dropdown in Customize and show size errors more loudly. That was rejected, because the user could still land in a state where nothing renders.

### 9. Zoom
The preview sits in a scrollable viewport. Zooming changes the stage's pixel width (height follows the aspect ratio), and a scroll adjustment keeps the point under the pointer fixed. The editor overlay maps pointers through `getScreenCTM()`, so it needs no change. Plotter previews are SVG and stay sharp at any zoom. PNG previews are 2000 px, which looks fine up to about 2–3×.

## Risks / Trade-offs

- [Each preview is a fresh Python process that reloads the pickled graph and reprojects it. That can take several seconds for large areas, and much longer for plotter renders.] → A busy indicator on the preview, debouncing, and a newer preview cancelling the older one. An in-process render worker is the known follow-up if this is too slow.
- [The edit list uses page mm, so changing the poster size in Location invalidates edits.] → Edits are cleared (with confirmation) when location or size changes, as the spec requires.
- [Erase in matplotlib is a background-coloured patch, not real removal. A theme whose `bg` differs from `gradient_color` could show a visible patch edge under the fades.] → The patch sits below the gradients. This is accepted for raster, and plotter output does real geometric removal.
- [Concentric fill of large, complex water bodies can produce many rings and slow buffering.] → Simplify the area to `pen/4` first (as roads do), and stop when an inset is empty.
- [The Location/Customize split breaks the old `POST /api/jobs` payload.] → The web UI and its API ship together, and nothing else calls the API. `test_web_app.py` is updated.
- [If `cache/` is wiped between load and preview, cache-only fails.] → A specific error message, and the UI offers to reload (see spec).

## Migration Plan

- The CLI is purely additive: every new option defaults to the current behaviour.
- The web UI is replaced as a whole. There is no data migration, and `cache/web/` is created on demand and can be deleted at any time.
- Rollback means reverting the commit. Posters and the OSM cache are unaffected.

## Open Questions

- The exact hatch angle and inset start for parks in concentric mode may need visual tuning after the first renders. This does not affect the specs.
- Whether to keep old session directories in `cache/web/` or remove them at startup. The default is to remove them at startup.
