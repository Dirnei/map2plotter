// Map Poster Generator web UI: step 1 picks the workflow (print poster or pen plotter) and
// loads a location (downloading the map data once); step 2 customizes it with live previews
// rendered from the cached data, then exports.

import {
  appendLog, applyValues, clearErrors, formValues, loadSaved, postJson, posterCard, save, showBanner, showErrors,
} from "./form.js";
import { Editor } from "./editor.js";
import { Zoom } from "./zoom.js";

const $ = (id) => document.getElementById(id);

const locationForm = $("location-form");
const customizeForm = $("customize-form");
const locationBanner = $("location-banner");
const customizeBanner = $("customize-banner");
const themesEl = $("themes");
const loadBtn = $("load");
const toCustomizeBtn = $("to-customize");
const loadStatusEl = $("load-status");
const exportBtn = $("export");
const exportStatusEl = $("export-status");
const cancelBtn = $("cancel");
const jobEl = $("job");
const jobTitleEl = $("job-title");
const commandEl = $("command");
const logEl = $("log");
const resultsEl = $("results");
const historyEl = $("history");
const historyEmptyEl = $("history-empty");
const stageEl = $("stage");
const previewImg = $("preview-img");
const previewBusy = $("preview-busy");
const previewState = $("preview-state");
const previewLog = $("preview-log");
const overpassSelect = $("overpass-select");
const overpassCustomLabel = $("overpass-custom-label");
const checkServersBtn = $("check-servers");
const checkStatusEl = $("check-status");
const serverStatusEl = $("server-status");

const PREVIEW_DEBOUNCE = 500;  // ms
const MAX_PRINT_MM = 500;
const MODE_NAMES = { print: "Print poster", plotter: "Pen plotter" };
const themeBackgrounds = new Map();

const state = {
  step: "location",
  loaded: null,          // location values of the loaded map (incl. mode), or null
  loadingLocation: null,
  mainJob: null,         // running load or export
  previewJob: null,      // running preview
  previewTimer: null,
  previewPending: false, // a preview was blocked by a load/export and should run afterwards
  mainEvents: null,
  previewEvents: null,
};

const editor = new Editor({
  overlay: $("overlay"),
  toolbar: $("editor-toolbar"),
  textToggles: $("text-toggles"),
  layerToggles: $("layer-toggles"),
  onChange: () => schedulePreview(0),
});

const zoom = new Zoom({
  viewport: $("viewport"),
  stage: stageEl,
  label: $("zoom-level"),
  panning: () => editor.tool === "pan",
});

// --- Values ------------------------------------------------------------------

function locationValues() {
  const values = formValues(locationForm);
  if (values.overpass_url === "custom") values.overpass_url = values.overpass_custom.trim();
  delete values.overpass_custom;
  return values;
}

function currentMode() {
  return state.loaded?.mode || "print";
}

function customizeValues() {
  const values = { ...formValues(customizeForm), edits: editor.edits };
  if (currentMode() === "plotter") values.format = "plotter";
  return values;
}

const AREA_KEYS = ["city", "country", "latitude", "longitude", "distance", "width", "height"];

/** Same map area and page size: edits (in page mm) stay valid. */
function sameArea(a, b) {
  return AREA_KEYS.every((k) => String(a?.[k] ?? "") === String(b?.[k] ?? ""));
}

/** The loaded map matches the form, workflow included: no need to load again. */
function sameLoad(a, b) {
  return sameArea(a, b) && (a?.mode || "print") === (b?.mode || "print");
}

// --- Steps and workflow -----------------------------------------------------------

function showStep(step) {
  state.step = step;
  for (const panel of document.querySelectorAll(".step-panel")) panel.hidden = panel.dataset.panel !== step;
  for (const btn of document.querySelectorAll(".step")) {
    if (btn.dataset.step === step) btn.setAttribute("aria-current", "step");
    else btn.removeAttribute("aria-current");
  }
  document.querySelector('.step[data-step="customize"]').disabled = !state.loaded;
  toCustomizeBtn.hidden = !state.loaded || !sameLoad(state.loaded, locationValues());
  if (step === "customize") requestAnimationFrame(() => zoom.apply());
}

function updateSizeHint() {
  const plotter = locationForm.elements.mode.value === "plotter";
  $("size-hint").textContent = plotter
    ? "Any size. The size sets the map area and the physical size of the SVG in mm."
    : `Up to ${MAX_PRINT_MM} mm per side. The size sets the map area; for larger posters use the pen plotter.`;
}

/** Show only the Customize options of the loaded workflow. */
function applyMode() {
  const mode = currentMode();
  for (const el of customizeForm.querySelectorAll("[data-mode]")) el.hidden = el.dataset.mode !== mode;
  const plotter = mode === "plotter";
  $("theme-legend").textContent = plotter ? "Pen colours" : "Theme";
  $("theme-hint").hidden = !plotter;
  $("all-themes-label").textContent = plotter ? "Export one SVG per colour set" : "Export one poster per theme";
  const loc = state.loaded;
  $("mode-badge").textContent = MODE_NAMES[mode];
  $("mode-badge").dataset.mode = mode;
  $("mode-summary").textContent = loc
    ? `${loc.city}, ${loc.country} · ${loc.width} × ${loc.height} mm · ${loc.distance} m radius`
    : "";
}

function setLoaded(location) {
  state.loaded = location;
  applyMode();
  showStep(state.step);
}

// --- OpenStreetMap servers ---------------------------------------------------

const serverLabels = new Map([["auto", "Automatic"]]);

function hostnameOf(url) {
  try {
    return new URL(url).host;
  } catch {
    return url;
  }
}

function updateCustomServerVisibility() {
  overpassCustomLabel.hidden = overpassSelect.value !== "custom";
}

function selectServer(url) {
  if ([...overpassSelect.options].some((o) => o.value === url)) {
    overpassSelect.value = url;
  } else if (url) {
    overpassSelect.value = "custom";
    locationForm.elements.overpass_custom.value = url;
  }
  updateCustomServerVisibility();
}

async function loadServers() {
  const res = await fetch("/api/overpass/servers");
  const { default: fallback, servers } = await res.json();
  for (const server of servers) {
    serverLabels.set(server.url, server.label);
    overpassSelect.append(new Option(server.label, server.url));
  }
  overpassSelect.append(new Option("Custom…", "custom"));
  selectServer(loadSaved().overpass_url || fallback);
}

async function checkServers() {
  checkServersBtn.disabled = true;
  checkStatusEl.textContent = "Checking… (up to 15 s)";
  const custom = overpassSelect.value === "custom" ? locationForm.elements.overpass_custom.value.trim() : null;
  try {
    const { res, data } = await postJson("/api/overpass/check", { custom });
    if (!res.ok) {
      checkStatusEl.textContent = data?.detail || `Check failed (${res.status})`;
      return;
    }
    const items = data.map((r) => {
      const li = document.createElement("li");
      const name = document.createElement("span");
      name.textContent = serverLabels.get(r.url) || hostnameOf(r.url);
      const result = document.createElement("span");
      result.className = r.ok ? "ok" : "bad";
      result.textContent = r.ok ? `✓ ${r.ms} ms` : `✗ ${r.error}`;
      li.append(name, result);
      const option = [...overpassSelect.options].find((o) => o.value === r.url);
      if (option) option.textContent = `${serverLabels.get(r.url)} — ${r.ok ? `✓ ${r.ms} ms` : `✗ ${r.error}`}`;
      return li;
    });
    serverStatusEl.replaceChildren(...items);
    serverStatusEl.hidden = false;
    const okCount = data.filter((r) => r.ok).length;
    checkStatusEl.textContent = `${okCount} of ${data.length} servers answered · checked ${new Date().toLocaleTimeString()}`;
  } catch {
    checkStatusEl.textContent = "Check failed";
  } finally {
    checkServersBtn.disabled = false;
  }
}

// --- Themes ------------------------------------------------------------------

function selectTheme(id) {
  customizeForm.elements.theme.value = id;
  for (const btn of themesEl.querySelectorAll(".theme")) {
    btn.setAttribute("aria-checked", String(btn.dataset.id === id));
  }
}

async function loadThemes() {
  const res = await fetch("/api/themes");
  const themes = await res.json();
  themesEl.replaceChildren();
  for (const theme of themes) {
    themeBackgrounds.set(theme.id, theme.colors.bg);
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "theme";
    btn.dataset.id = theme.id;
    btn.setAttribute("role", "radio");
    btn.title = theme.description;
    const name = document.createElement("div");
    name.className = "name";
    name.textContent = theme.name;
    const swatches = document.createElement("div");
    swatches.className = "swatches";
    const colors = [theme.colors.bg, theme.colors.water, theme.colors.parks, theme.colors.road_motorway,
      theme.colors.road_primary, theme.colors.road_residential, theme.colors.text].filter(Boolean);
    for (const color of colors) {
      const s = document.createElement("span");
      s.style.background = color;
      swatches.append(s);
    }
    btn.append(name, swatches);
    btn.addEventListener("click", () => {
      selectTheme(theme.id);
      customizeChanged();
    });
    themesEl.append(btn);
  }
  selectTheme(customizeForm.elements.theme.value);
}

// --- Job streaming -------------------------------------------------------------

function follow(job, onLine, onStatus) {
  const events = new EventSource(`/api/jobs/${job.id}/events`);
  events.onmessage = (e) => {
    const msg = JSON.parse(e.data);
    if (msg.type === "line") {
      onLine(msg.text);
    } else if (msg.type === "status") {
      events.close();
      onStatus(msg);
    }
  };
  return events;
}

function setStatusText(el, status, running) {
  el.className = `status ${status}`;
  el.textContent = { running, succeeded: "Done", failed: "Failed", cancelled: "Cancelled" }[status] ?? "";
}

function showMainJob(job, title) {
  state.mainJob = job;
  jobEl.hidden = false;
  jobTitleEl.textContent = title;
  commandEl.textContent = job.command;
  logEl.textContent = "";
  resultsEl.replaceChildren();
  cancelBtn.hidden = job.status !== "running";
  loadBtn.disabled = exportBtn.disabled = job.status === "running";
  if (state.mainEvents) state.mainEvents.close();
  state.mainEvents = follow(job, (line) => appendLog(logEl, line), (summary) => finishMainJob(summary));
}

function finishMainJob(job) {
  state.mainJob = null;
  state.mainEvents = null;
  cancelBtn.hidden = true;
  loadBtn.disabled = exportBtn.disabled = false;
  if (job.kind === "load") {
    setStatusText(loadStatusEl, job.status, "Loading…");
    if (job.status === "succeeded") {
      setLoaded(state.loadingLocation);
      showPreview(job.preview);
      zoom.fit();
      refreshLayout().then(() => showStep("customize"));
    }
  } else {
    setStatusText(exportStatusEl, job.status, "Exporting…");
    resultsEl.replaceChildren(...job.files.map((name) => posterCard({ name })));
    loadHistory();
  }
  if (state.previewPending && state.loaded) schedulePreview(0);
}

// --- Step 1: load --------------------------------------------------------------

async function loadMap(e) {
  e?.preventDefault();
  clearErrors(locationForm, locationBanner);
  const values = locationValues();
  if (state.loaded && !sameArea(state.loaded, values) && !editor.isEmpty()) {
    if (!confirm("Loading a different location or size clears your edits. Continue?")) return;
  }
  save(values);
  const { res, data } = await postJson("/api/load", { ...values, theme: customizeForm.elements.theme.value });
  if (res.status === 422) {
    showErrors(locationForm, locationBanner, data?.errors || {});
    return;
  }
  if (!res.ok) {
    showBanner(locationBanner, data?.detail || `Request failed (${res.status})`);
    return;
  }
  if (!state.loaded || !sameArea(state.loaded, values)) editor.clear();
  state.loadingLocation = values;
  state.loaded = null;
  showStep("location");
  setStatusText(loadStatusEl, "running", "Loading…");
  showMainJob(data, "Loading map data");
}

// --- Step 2: previews ----------------------------------------------------------

function showPreview(preview) {
  if (!preview) return;
  previewImg.src = preview.url;
  // Plotter SVGs leave out the background (it is the paper): show them on the theme's colour
  stageEl.style.background = preview.type === "svg"
    ? themeBackgrounds.get(customizeForm.elements.theme.value) || "#fff" : "#fff";
  stageEl.classList.remove("outdated");
  previewState.classList.remove("error");
  const format = customizeForm.elements.format.value;
  previewState.textContent = preview.type === "svg"
    ? "Plotter preview: the actual pen paths, sharp at any zoom"
    : format === "png"
      ? "Preview at reduced resolution; the PNG export is 300 dpi"
      : `Raster preview of the same poster; the ${format.toUpperCase()} export is vector`;
}

function previewError(message) {
  stageEl.classList.add("outdated");
  previewState.classList.add("error");
  previewState.textContent = `Preview not updated: ${message}`;
}

function setPreviewBusy(busy) {
  previewBusy.hidden = !busy;
}

function schedulePreview(delay = PREVIEW_DEBOUNCE) {
  if (!state.loaded) return;
  clearTimeout(state.previewTimer);
  state.previewTimer = setTimeout(requestPreview, delay);
  setPreviewBusy(true);
}

async function requestPreview() {
  clearErrors(customizeForm, customizeBanner);
  const { res, data } = await postJson("/api/preview", customizeValues());
  if (res.status === 422) {
    setPreviewBusy(false);
    const errors = data?.errors || {};
    showErrors(customizeForm, customizeBanner, errors);
    previewError(Object.values(errors).join(" · ") || "invalid settings");
    return;
  }
  if (res.status === 409 && state.mainJob) {
    state.previewPending = true;  // runs again after the load/export
    return;
  }
  if (!res.ok) {
    setPreviewBusy(false);
    previewError(data?.detail || `request failed (${res.status})`);
    return;
  }
  state.previewPending = false;
  const job = data;
  state.previewJob = job;
  const lines = [];
  if (state.previewEvents) state.previewEvents.close();
  state.previewEvents = follow(job, (line) => lines.push(line), (summary) => finishPreview(summary, lines));
}

function finishPreview(job, lines) {
  if (state.previewJob?.id !== job.id) return;  // superseded by a newer preview
  state.previewJob = null;
  state.previewEvents = null;
  setPreviewBusy(false);
  if (job.status === "succeeded") {
    previewLog.hidden = true;
    showPreview(job.preview);
  } else if (job.status === "failed") {
    previewError("the render failed, see the output below. Showing the last good preview.");
    previewLog.textContent = lines.join("\n");
    previewLog.hidden = false;
    if (job.not_cached) offerReload();
  }
}

function offerReload() {
  customizeBanner.replaceChildren("The map data for this location is no longer cached. ");
  const btn = document.createElement("button");
  btn.type = "button";
  btn.className = "secondary small";
  btn.textContent = "Reload location";
  btn.addEventListener("click", () => {
    showStep("location");
    loadMap();
  });
  customizeBanner.append(btn);
  customizeBanner.hidden = false;
}

let layoutTimer = null;

async function refreshLayout() {
  if (!state.loaded) return;
  const values = formValues(customizeForm);
  const { res, data } = await postJson("/api/layout", {
    display_city: values.display_city,
    display_country: values.display_country,
    country_label: values.country_label,
  });
  if (res.ok) {
    zoom.setAspect(data.width / data.height);
    editor.setPage(data.width, data.height, data.boxes);
  }
}

function customizeChanged(e) {
  save(formValues(customizeForm));
  if (e?.target?.name === "all_themes") return;  // export-only option
  if (["display_city", "display_country", "country_label"].includes(e?.target?.name)) {
    clearTimeout(layoutTimer);
    layoutTimer = setTimeout(refreshLayout, PREVIEW_DEBOUNCE);
  }
  schedulePreview();
}

// --- Export ----------------------------------------------------------------------

async function exportPoster() {
  clearErrors(customizeForm, customizeBanner);
  setStatusText(exportStatusEl, "", "");
  const { res, data } = await postJson("/api/export", customizeValues());
  if (res.status === 422) {
    showErrors(customizeForm, customizeBanner, data?.errors || {});
    return;
  }
  if (!res.ok) {
    showBanner(customizeBanner, data?.detail || `Request failed (${res.status})`);
    return;
  }
  clearTimeout(state.previewTimer);
  setPreviewBusy(false);
  setStatusText(exportStatusEl, "running", "Exporting…");
  showMainJob(data, "Export");
}

async function cancelJob() {
  if (!state.mainJob) return;
  cancelBtn.disabled = true;
  try {
    await fetch(`/api/jobs/${state.mainJob.id}/cancel`, { method: "POST" });
  } finally {
    cancelBtn.disabled = false;
  }
}

// --- History -----------------------------------------------------------------------

async function loadHistory() {
  const res = await fetch("/api/posters");
  const posters = await res.json();
  historyEl.replaceChildren(...posters.map(posterCard));
  historyEmptyEl.hidden = posters.length > 0;
}

// --- Start-up ------------------------------------------------------------------------

async function restore() {
  const session = await (await fetch("/api/session")).json();
  if (session.loaded) {
    setLoaded(session.location);
    showPreview(session.preview);
    await refreshLayout();
    showStep("customize");
  } else {
    showStep("location");
  }
  const job = await (await fetch("/api/jobs/current")).json();
  if (job && job.status === "running" && job.kind !== "preview") {
    if (job.kind === "load") state.loadingLocation = locationValues();
    showMainJob(job, job.kind === "load" ? "Loading map data" : "Export");
  }
}

function keyDown(e) {
  if (state.step !== "customize") return;
  if (["INPUT", "SELECT", "TEXTAREA"].includes(document.activeElement?.tagName)) return;
  if (e.ctrlKey || e.metaKey || e.altKey) return;
  if (e.key === "+" || e.key === "=") zoom.in();
  else if (e.key === "-") zoom.out();
  else if (e.key === "0") zoom.fit();
}

locationForm.addEventListener("submit", loadMap);
locationForm.addEventListener("change", () => {
  updateCustomServerVisibility();
  updateSizeHint();
  save(locationValues());
  showStep(state.step);
});
customizeForm.addEventListener("change", customizeChanged);
customizeForm.addEventListener("submit", (e) => e.preventDefault());
toCustomizeBtn.addEventListener("click", () => showStep("customize"));
$("back").addEventListener("click", () => showStep("location"));
$("change-location").addEventListener("click", () => showStep("location"));
for (const btn of document.querySelectorAll(".step")) {
  btn.addEventListener("click", () => showStep(btn.dataset.step));
}
$("zoom-in").addEventListener("click", () => zoom.in());
$("zoom-out").addEventListener("click", () => zoom.out());
$("zoom-fit").addEventListener("click", () => zoom.fit());
document.addEventListener("keydown", keyDown);
exportBtn.addEventListener("click", exportPoster);
cancelBtn.addEventListener("click", cancelJob);
checkServersBtn.addEventListener("click", checkServers);
$("copy").addEventListener("click", async () => {
  try {
    await navigator.clipboard.writeText(commandEl.textContent);
  } catch {
    // Clipboard unavailable: the command stays selectable
  }
});

const saved = loadSaved();
applyValues(locationForm, saved);
applyValues(customizeForm, saved);
if (saved.format === "plotter") customizeForm.elements.format.value = "png";  // plotter is a workflow now
updateCustomServerVisibility();
updateSizeHint();
applyMode();
Promise.all([loadThemes(), loadServers()]).then(restore);
loadHistory();
