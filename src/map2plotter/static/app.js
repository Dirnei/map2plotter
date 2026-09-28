// map2plotter web UI: step 1 loads a location (downloading the map data once); step 2
// customizes the plotter SVG with live previews rendered from the cached data, then exports.

import {
  appendLog, applyValues, clearErrors, formValues, loadSaved, postJson, posterCard, save, showBanner, showErrors,
} from "./form.js";
import { Editor, LAYERS } from "./editor.js";
import { Zoom } from "./zoom.js";

const $ = (id) => document.getElementById(id);

const locationForm = $("location-form");
const customizeForm = $("customize-form");
const locationBanner = $("location-banner");
const customizeBanner = $("customize-banner");
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
const previewBusy = $("preview-busy");
const previewState = $("preview-state");
const previewLog = $("preview-log");
const overpassSelect = $("overpass-select");
const overpassCustomLabel = $("overpass-custom-label");
const checkServersBtn = $("check-servers");
const checkStatusEl = $("check-status");
const serverStatusEl = $("server-status");

const PREVIEW_DEBOUNCE = 500;  // ms
const PENS_KEY = "map2plotter-pens-v1";
const PEN_ELEMENTS = [...LAYERS, ["text", "Text"]];
const themeColors = new Map();  // theme id -> {key: colour}

const state = {
  step: "location",
  loaded: null,          // location values of the loaded map, or null
  loadingLocation: null,
  mainJob: null,         // running load or export
  previewJob: null,      // running preview
  previewTimer: null,
  previewPending: false, // a preview was blocked by a load/export and should run afterwards
  mainEvents: null,
  previewEvents: null,
  pens: {},              // pen colour per element: {key: "#rrggbb"}
  previewVersion: 0,     // guards against out-of-order inline SVG loads
};

const editor = new Editor({
  overlay: $("overlay"),
  toolbar: $("editor-toolbar"),
  textToggles: $("text-toggles"),
  onChange: () => {
    renderPens();
    schedulePreview(0);
  },
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

function customizeValues() {
  return { ...formValues(customizeForm), edits: editor.edits, colors: { ...state.pens } };
}

const AREA_KEYS = ["city", "country", "latitude", "longitude", "distance", "width", "height"];

/** Same map area and page size: edits (in page mm) stay valid. */
function sameArea(a, b) {
  return AREA_KEYS.every((k) => String(a?.[k] ?? "") === String(b?.[k] ?? ""));
}

// --- Steps ------------------------------------------------------------------------

function showStep(step) {
  state.step = step;
  for (const panel of document.querySelectorAll(".step-panel")) panel.hidden = panel.dataset.panel !== step;
  for (const btn of document.querySelectorAll(".step")) {
    if (btn.dataset.step === step) btn.setAttribute("aria-current", "step");
    else btn.removeAttribute("aria-current");
  }
  document.querySelector('.step[data-step="customize"]').disabled = !state.loaded;
  toCustomizeBtn.hidden = !state.loaded || !sameArea(state.loaded, locationValues());
  if (step === "customize") requestAnimationFrame(() => zoom.apply());
}

/** Place and size of the loaded map, shown above the Customize options. */
function updateSummary() {
  const loc = state.loaded;
  $("mode-summary").textContent = loc
    ? `${loc.city}, ${loc.country} · ${loc.width} × ${loc.height} mm · ${loc.distance} m radius`
    : "";
}

function setLoaded(location) {
  state.loaded = location;
  updateSummary();
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

/** The base theme: file names and the --color overrides of exports are relative to it. */
function selectTheme(id) {
  customizeForm.elements.theme.value = id;
  save(formValues(customizeForm));
}

async function loadThemes() {
  const res = await fetch("/api/themes");
  const themes = await res.json();
  const penTheme = $("pen-theme");
  for (const theme of themes) {
    themeColors.set(theme.id, theme.colors);
    const option = new Option(theme.name, theme.id);
    option.title = theme.description;
    penTheme.append(option);
  }
}

// --- Pens -----------------------------------------------------------------------

function savePens() {
  try {
    localStorage.setItem(PENS_KEY, JSON.stringify(state.pens));
  } catch {
    // Storage unavailable: pens reset on reload
  }
}

function loadSavedPens() {
  try {
    return JSON.parse(localStorage.getItem(PENS_KEY)) || null;
  } catch {
    return null;
  }
}

/** Set every pen from a theme (and make it the base theme, so exports pass fewer --color options). */
function pensFromTheme(themeId) {
  const colors = themeColors.get(themeId) || {};
  state.pens = Object.fromEntries(PEN_ELEMENTS.map(([key]) => [key, (colors[key] || "#000000").toLowerCase()]));
  selectTheme(themeId);
  savePens();
  renderPens();
  recolor();
}

function penCount() {
  const visible = PEN_ELEMENTS.filter(([key]) => key === "text" || !editor.layerHidden(key));
  return new Set(visible.map(([key]) => state.pens[key])).size;
}

function renderPens() {
  const list = $("pens");
  if (!list.childElementCount) {
    for (const [key, label] of PEN_ELEMENTS) {
      const row = document.createElement("div");
      row.className = "pen";
      row.dataset.key = key;
      const color = document.createElement("input");
      color.type = "color";
      color.setAttribute("aria-label", `${label} pen colour`);
      color.addEventListener("input", () => {
        state.pens[key] = color.value.toLowerCase();
        savePens();
        recolor();
        renderPens();
      });
      const name = document.createElement("span");
      name.className = "pen-name";
      name.textContent = label;
      row.append(color, name);
      if (key !== "text") {
        const toggle = document.createElement("label");
        toggle.className = "inline pen-visible";
        const box = document.createElement("input");
        box.type = "checkbox";
        box.addEventListener("change", () => editor.setLayerVisible(key, box.checked));
        toggle.append(box, " Draw");
        row.append(toggle);
      }
      list.append(row);
    }
  }
  for (const row of list.children) {
    const key = row.dataset.key;
    row.querySelector('input[type="color"]').value = state.pens[key] || "#000000";
    const box = row.querySelector('input[type="checkbox"]');
    if (box) {
      box.checked = !editor.layerHidden(key);
      row.classList.toggle("off", !box.checked);
    }
  }
  const count = penCount();
  $("pen-count").textContent = `· ${count} pen${count === 1 ? "" : "s"}`;
}

/** Apply the pen colours to the inline preview SVG (no re-render needed). */
function recolor() {
  for (const g of $("preview-svg").querySelectorAll("g[data-key]")) {
    const color = state.pens[g.dataset.key];
    if (color) g.style.stroke = color;
  }
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
      pensFromTheme(customizeForm.elements.theme.value);
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
  // Inline, so pen colours can be applied without a re-render. White paper, no background.
  const inline = $("preview-svg");
  const version = ++state.previewVersion;
  fetch(preview.url).then((res) => res.text()).then((text) => {
    if (version !== state.previewVersion) return;  // a newer preview is already shown
    const svg = new DOMParser().parseFromString(text, "image/svg+xml").documentElement;
    if (svg.nodeName !== "svg") return;
    inline.replaceChildren(document.importNode(svg, true));
    inline.hidden = false;
    recolor();
  });
  stageEl.classList.remove("outdated");
  previewState.classList.remove("error");
  previewState.textContent = "The actual pen paths of the SVG, sharp at any zoom";
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
  // Pen colours are applied in the browser; pen visibility goes through the editor's edit list
  if (e?.target?.closest?.("#pens, .pen-presets")) return;
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
    const saved = loadSavedPens();
    if (saved) {
      state.pens = saved;
      renderPens();
    } else {
      pensFromTheme(customizeForm.elements.theme.value);
    }
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
$("pen-theme").addEventListener("change", (e) => {
  if (e.target.value) pensFromTheme(e.target.value);
  e.target.value = "";
});
$("single-pen").addEventListener("click", () => {
  state.pens = Object.fromEntries(PEN_ELEMENTS.map(([key]) => [key, "#000000"]));
  savePens();
  renderPens();
  recolor();
});
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
updateCustomServerVisibility();
updateSummary();
Promise.all([loadThemes(), loadServers()]).then(restore);
loadHistory();
