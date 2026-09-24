// Shared helpers: form values, per-viewer storage, field errors, log view, poster cards.

const STORAGE_KEY = "maptoposter-form-v3";  // v3: two-step form
const NUMBER_FIELDS = [
  "distance", "width", "height", "pen_width", "hatch_spacing", "water_spacing", "parks_spacing",
];

// --- Storage (per-viewer convenience only) ---------------------------------

export function loadSaved() {
  try {
    return JSON.parse(localStorage.getItem(STORAGE_KEY)) || {};
  } catch {
    return {};
  }
}

export function save(values) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({ ...loadSaved(), ...values }));
  } catch {
    // Storage unavailable (private mode etc.): nothing to do
  }
}

// --- Values ------------------------------------------------------------------

export function formValues(form) {
  const values = {};
  for (const el of form.elements) {
    if (!el.name) continue;
    if (el.type === "checkbox") {
      values[el.name] = el.checked;
    } else if (el.type === "radio") {
      if (el.checked) values[el.name] = el.value;
    } else if (NUMBER_FIELDS.includes(el.name)) {
      values[el.name] = el.value.trim() === "" ? null : Number(el.value);
    } else {
      values[el.name] = el.value;
    }
  }
  return values;
}

export function applyValues(form, values) {
  for (const [name, value] of Object.entries(values)) {
    const el = form.elements.namedItem(name);
    if (!el || value === undefined || el.type === "hidden" && value === null) continue;
    if (el.type === "checkbox") el.checked = Boolean(value);
    else el.value = value ?? "";
  }
}

// --- Errors ------------------------------------------------------------------

export function showBanner(banner, message) {
  banner.textContent = message;
  banner.hidden = false;
}

export function clearErrors(form, banner) {
  banner.hidden = true;
  for (const el of form.querySelectorAll("[aria-invalid]")) el.removeAttribute("aria-invalid");
  for (const el of form.querySelectorAll(".error")) el.textContent = "";
}

function errorSlot(form, name) {
  let slot = form.querySelector(`[data-error-for="${name}"]`);
  if (!slot) {
    const input = form.elements.namedItem(name);
    if (!input || !input.closest || !input.closest("label")) return null;
    slot = document.createElement("p");
    slot.className = "error";
    slot.dataset.errorFor = name;
    input.closest("label").append(slot);
  }
  return slot;
}

export function showErrors(form, banner, errors) {
  for (const [name, message] of Object.entries(errors)) {
    const input = form.elements.namedItem(name);
    if (input && input.setAttribute) input.setAttribute("aria-invalid", "true");
    const slot = errorSlot(form, name);
    if (slot) slot.textContent = message;
    else showBanner(banner, `${name}: ${message}`);
  }
}

// --- Log view ------------------------------------------------------------------

// Progress bars redraw the same line with \r; replace instead of appending those updates
function progressKey(line) {
  const match = line.match(/^(.*?)(\d+%\|)/);
  return match ? match[1].replace(/:\s*$/, "") : null;
}

export function appendLog(logEl, line) {
  const atBottom = logEl.scrollTop + logEl.clientHeight >= logEl.scrollHeight - 4;
  const lines = logEl.textContent ? logEl.textContent.split("\n") : [];
  if (progressKey(line) !== null && lines.length && progressKey(lines[lines.length - 1]) !== null) {
    lines[lines.length - 1] = line;
  } else {
    lines.push(line);
  }
  logEl.textContent = lines.join("\n");
  if (atBottom) logEl.scrollTop = logEl.scrollHeight;
}

// --- Posters -----------------------------------------------------------------

function formatSize(bytes) {
  if (bytes >= 1024 * 1024) return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
  return `${Math.max(1, Math.round(bytes / 1024))} KB`;
}

export function posterCard(poster) {
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

// --- HTTP ----------------------------------------------------------------------

export async function postJson(url, body) {
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  let data = null;
  try {
    data = await res.json();
  } catch {
    // Non-JSON error body
  }
  return { res, data };
}
