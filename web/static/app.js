// Map Poster Generator web UI: form handling, job streaming, results and history.

const form = document.getElementById("poster-form");
const themesEl = document.getElementById("themes");
const plotterEl = document.getElementById("plotter-options");
const generateBtn = document.getElementById("generate");
const cancelBtn = document.getElementById("cancel");
const statusEl = document.getElementById("status");
const bannerEl = document.getElementById("banner");
const jobEl = document.getElementById("job");
const commandEl = document.getElementById("command");
const logEl = document.getElementById("log");
const resultsEl = document.getElementById("results");
const historyEl = document.getElementById("history");
const historyEmptyEl = document.getElementById("history-empty");
const overpassSelect = document.getElementById("overpass-select");
const overpassCustomLabel = document.getElementById("overpass-custom-label");
const checkServersBtn = document.getElementById("check-servers");
const checkStatusEl = document.getElementById("check-status");
const serverStatusEl = document.getElementById("server-status");

const STORAGE_KEY = "maptoposter-form-v2";  // v2: sizes in mm
const NUMBER_FIELDS = ["distance", "width", "height", "pen_width", "hatch_spacing"];

let currentJob = null;
let events = null;

// --- Storage (per-viewer convenience only) ---------------------------------

function loadSaved() {
  try {
    return JSON.parse(localStorage.getItem(STORAGE_KEY)) || {};
  } catch {
    return {};
  }
}

function save(values) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(values));
  } catch {
    // Storage unavailable (private mode etc.): nothing to do
  }
}

// --- Form ------------------------------------------------------------------

function formValues() {
  const values = {};
  for (const el of form.elements) {
    if (!el.name) continue;
    if (el.type === "checkbox") {
      values[el.name] = el.checked;
    } else if (NUMBER_FIELDS.includes(el.name)) {
      values[el.name] = el.value.trim() === "" ? null : Number(el.value);
    } else {
      values[el.name] = el.value;
    }
  }
  if (values.overpass_url === "custom") values.overpass_url = values.overpass_custom.trim();
  delete values.overpass_custom;
  return values;
}

function applyValues(values) {
  for (const [name, value] of Object.entries(values)) {
    const el = form.elements.namedItem(name);
    if (!el || value === undefined) continue;
    if (el.type === "checkbox") el.checked = Boolean(value);
    else el.value = value ?? "";
  }
}

function updatePlotterVisibility() {
  plotterEl.hidden = form.elements.format.value !== "plotter";
}

function updateCustomServerVisibility() {
  overpassCustomLabel.hidden = overpassSelect.value !== "custom";
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

function selectServer(url) {
  if ([...overpassSelect.options].some((o) => o.value === url)) {
    overpassSelect.value = url;
  } else if (url) {
    overpassSelect.value = "custom";
    form.elements.overpass_custom.value = url;
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
  const saved = loadSaved().overpass_url;
  selectServer(saved || fallback);
}

async function checkServers() {
  checkServersBtn.disabled = true;
  checkStatusEl.textContent = "Checking… (up to 15 s)";
  const custom = overpassSelect.value === "custom" ? form.elements.overpass_custom.value.trim() : null;
  try {
    const res = await fetch("/api/overpass/check", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ custom }),
    });
    const body = await res.json();
    if (!res.ok) {
      checkStatusEl.textContent = body.detail || `Check failed (${res.status})`;
      return;
    }
    const items = body.map((r) => {
      const li = document.createElement("li");
      const name = document.createElement("span");
      name.textContent = serverLabels.get(r.url) || hostnameOf(r.url);
      const state = document.createElement("span");
      state.className = r.ok ? "ok" : "bad";
      state.textContent = r.ok ? `✓ ${r.ms} ms` : `✗ ${r.error}`;
      li.append(name, state);
      const option = [...overpassSelect.options].find((o) => o.value === r.url);
      if (option) option.textContent = `${serverLabels.get(r.url)} — ${r.ok ? `✓ ${r.ms} ms` : `✗ ${r.error}`}`;
      return li;
    });
    serverStatusEl.replaceChildren(...items);
    serverStatusEl.hidden = false;
    const okCount = body.filter((r) => r.ok).length;
    checkStatusEl.textContent = `${okCount} of ${body.length} servers answered · checked ${new Date().toLocaleTimeString()}`;
  } catch {
    checkStatusEl.textContent = "Check failed";
  } finally {
    checkServersBtn.disabled = false;
  }
}

function updateThemeState() {
  themesEl.classList.toggle("disabled", form.elements.all_themes.checked);
}

function selectTheme(id) {
  form.elements.theme.value = id;
  for (const btn of themesEl.querySelectorAll(".theme")) {
    btn.setAttribute("aria-checked", String(btn.dataset.id === id));
  }
}

async function loadThemes() {
  const res = await fetch("/api/themes");
  const themes = await res.json();
  themesEl.replaceChildren();
  for (const theme of themes) {
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
      save(formValues());
    });
    themesEl.append(btn);
  }
  selectTheme(form.elements.theme.value);
}

function clearErrors() {
  bannerEl.hidden = true;
  for (const el of form.querySelectorAll("[aria-invalid]")) el.removeAttribute("aria-invalid");
  for (const el of form.querySelectorAll(".error")) el.textContent = "";
}

function errorSlot(name) {
  let slot = form.querySelector(`[data-error-for="${name}"]`);
  if (!slot) {
    const input = form.elements.namedItem(name);
    if (!input || !input.closest("label")) return null;
    slot = document.createElement("p");
    slot.className = "error";
    slot.dataset.errorFor = name;
    input.closest("label").append(slot);
  }
  return slot;
}

function showErrors(errors) {
  for (const [name, message] of Object.entries(errors)) {
    const input = form.elements.namedItem(name);
    if (input && input.setAttribute) input.setAttribute("aria-invalid", "true");
    const slot = errorSlot(name);
    if (slot) slot.textContent = message;
    else showBanner(`${name}: ${message}`);
  }
  if (errors.pen_width || errors.hatch_spacing) plotterEl.hidden = false;
}

function showBanner(message) {
  bannerEl.textContent = message;
  bannerEl.hidden = false;
}

// --- Jobs ------------------------------------------------------------------

function setRunning(running) {
  generateBtn.disabled = running;
  cancelBtn.hidden = !running;
}

function setStatus(status) {
  statusEl.className = `status ${status}`;
  statusEl.textContent = {
    running: "Generating…",
    succeeded: "Done",
    failed: "Failed",
    cancelled: "Cancelled",
  }[status] ?? "";
}

// Progress bars redraw the same line with \r; replace instead of appending those updates
function progressKey(line) {
  const match = line.match(/^(.*?)(\d+%\|)/);
  return match ? match[1].replace(/:\s*$/, "") : null;
}

function appendLog(line) {
  const atBottom = logEl.scrollTop + logEl.clientHeight >= logEl.scrollHeight - 4;
  const lines = logEl.textContent ? logEl.textContent.split("\n") : [];
  const key = progressKey(line);
  if (key !== null && lines.length && progressKey(lines[lines.length - 1]) !== null) {
    lines[lines.length - 1] = line;
  } else {
    lines.push(line);
  }
  logEl.textContent = lines.join("\n");
  if (atBottom) logEl.scrollTop = logEl.scrollHeight;
}

function showJob(job) {
  currentJob = job;
  jobEl.hidden = false;
  commandEl.textContent = job.command;
  logEl.textContent = "";
  resultsEl.replaceChildren();
  setStatus(job.status);
  setRunning(job.status === "running");
  follow(job.id);
}

function follow(jobId) {
  if (events) events.close();
  events = new EventSource(`/api/jobs/${jobId}/events`);
  events.onmessage = (e) => {
    const msg = JSON.parse(e.data);
    if (msg.type === "line") {
      appendLog(msg.text);
    } else if (msg.type === "status") {
      events.close();
      events = null;
      finish(msg);
    }
  };
}

function finish(job) {
  currentJob = job;
  setStatus(job.status);
  setRunning(false);
  resultsEl.replaceChildren(...job.files.map((name) => posterCard({ name })));
  loadHistory();
}

async function submit(e) {
  e.preventDefault();
  clearErrors();
  const values = formValues();
  save(values);
  const res = await fetch("/api/jobs", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(values),
  });
  const body = await res.json();
  if (res.status === 422) {
    showErrors(body.errors || {});
    return;
  }
  if (!res.ok) {
    showBanner(body.detail || `Request failed (${res.status})`);
    return;
  }
  showJob(body);
}

async function cancelJob() {
  if (!currentJob) return;
  cancelBtn.disabled = true;
  try {
    await fetch(`/api/jobs/${currentJob.id}/cancel`, { method: "POST" });
  } finally {
    cancelBtn.disabled = false;
  }
}

async function reattach() {
  const res = await fetch("/api/jobs/current");
  const job = await res.json();
  if (job) showJob(job);
}

// --- Posters ---------------------------------------------------------------

function formatSize(bytes) {
  if (bytes >= 1024 * 1024) return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
  return `${Math.max(1, Math.round(bytes / 1024))} KB`;
}

function posterCard(poster) {
  const url = `/api/posters/${encodeURIComponent(poster.name)}`;
  const card = document.createElement("div");
  card.className = "card";

  const preview = document.createElement("a");
  preview.className = "preview";
  preview.href = url;
  preview.target = "_blank";
  preview.rel = "noopener";
  if (/\.(png|svg)$/i.test(poster.name)) {
    const img = document.createElement("img");
    img.src = url;
    img.alt = poster.name;
    img.loading = "lazy";
    preview.append(img);
  } else {
    preview.classList.add("doc");
    preview.textContent = "Open PDF";
  }

  const name = document.createElement("div");
  name.className = "name";
  name.textContent = poster.name;
  card.append(preview, name);

  if (poster.mtime) {
    const meta = document.createElement("div");
    meta.className = "meta";
    meta.textContent = `${new Date(poster.mtime * 1000).toLocaleString()} · ${formatSize(poster.size)}`;
    card.append(meta);
  }

  const links = document.createElement("div");
  links.className = "links";
  const download = document.createElement("a");
  download.href = `${url}?download=1`;
  download.textContent = "Download";
  links.append(download);
  card.append(links);
  return card;
}

async function loadHistory() {
  const res = await fetch("/api/posters");
  const posters = await res.json();
  historyEl.replaceChildren(...posters.map(posterCard));
  historyEmptyEl.hidden = posters.length > 0;
}

// --- Wiring ----------------------------------------------------------------

form.addEventListener("submit", submit);
form.addEventListener("change", () => {
  updatePlotterVisibility();
  updateCustomServerVisibility();
  updateThemeState();
  save(formValues());
});
cancelBtn.addEventListener("click", cancelJob);
checkServersBtn.addEventListener("click", checkServers);
document.getElementById("copy").addEventListener("click", async () => {
  try {
    await navigator.clipboard.writeText(commandEl.textContent);
  } catch {
    // Clipboard unavailable: the command stays selectable
  }
});

applyValues(loadSaved());
updatePlotterVisibility();
updateThemeState();
loadThemes();
loadServers();
loadHistory();
reattach();
