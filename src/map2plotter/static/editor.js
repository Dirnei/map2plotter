// Poster editor: an SVG overlay in page millimetres on top of the preview.
// Edits (erase regions, text offsets / hidden lines, hidden layers) are plain data
// that the server passes to the CLI with --edits, so every re-render applies them.

const SVG_NS = "http://www.w3.org/2000/svg";

export const TEXT_KEYS = [
  ["city", "City"],
  ["country", "Country"],
  ["coords", "Coordinates"],
  ["divider", "Divider"],
];

export const LAYERS = [
  ["water", "Water"],
  ["parks", "Parks"],
  ["road_motorway", "Motorways"],
  ["road_primary", "Primary roads"],
  ["road_secondary", "Secondary roads"],
  ["road_tertiary", "Tertiary roads"],
  ["road_residential", "Residential roads"],
  ["road_default", "Other roads"],
];

const MIN_SIZE = 1;  // mm: smaller rectangles are treated as clicks
const FREEHAND_STEP = 0.8;  // mm between freehand points

function emptyEdits() {
  return { version: 1, erase: [], text: {}, hidden_layers: [] };
}

function el(name, attrs = {}) {
  const node = document.createElementNS(SVG_NS, name);
  for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, v);
  return node;
}

const round = (v) => Math.round(v * 100) / 100;

export class Editor {
  /**
   * @param {object} opts
   * @param {SVGSVGElement} opts.overlay
   * @param {HTMLElement} opts.toolbar
   * @param {HTMLElement} opts.textToggles
   * @param {HTMLElement} opts.layerToggles
   * @param {function} opts.onChange  called with the edit list after every committed change
   */
  constructor({ overlay, toolbar, textToggles, layerToggles, onChange }) {
    this.overlay = overlay;
    this.toolbar = toolbar;
    this.onChange = onChange;
    this.width = 300;
    this.height = 400;
    this.boxes = {};
    this.edits = emptyEdits();
    this.undoStack = [];
    this.redoStack = [];
    this.tool = "move";
    this.selected = null;
    this.drag = null;

    this.buttons = {
      delete: toolbar.querySelector("#delete-region"),
      undo: toolbar.querySelector("#undo"),
      redo: toolbar.querySelector("#redo"),
      reset: toolbar.querySelector("#reset-edits"),
    };
    for (const btn of toolbar.querySelectorAll(".tool")) {
      btn.addEventListener("click", () => this.setTool(btn.dataset.tool));
    }
    this.buttons.delete.addEventListener("click", () => this.deleteSelected());
    this.buttons.undo.addEventListener("click", () => this.undo());
    this.buttons.redo.addEventListener("click", () => this.redo());
    this.buttons.reset.addEventListener("click", () => this.commit(emptyEdits()));

    this.textInputs = this.buildToggles(textToggles, TEXT_KEYS, (key, visible) => {
      const next = this.snapshot();
      const entry = { dx: 0, dy: 0, ...next.text[key], hidden: !visible };
      next.text[key] = entry;
      this.commit(next);
    });
    this.layerInputs = this.buildToggles(layerToggles, LAYERS, (key, visible) => this.setLayerVisible(key, visible));

    overlay.addEventListener("pointerdown", (e) => this.pointerDown(e));
    overlay.addEventListener("pointermove", (e) => this.pointerMove(e));
    overlay.addEventListener("pointerup", (e) => this.pointerUp(e));
    overlay.addEventListener("pointercancel", () => this.cancelDrag());
    document.addEventListener("keydown", (e) => this.keyDown(e));
    this.render();
  }

  buildToggles(container, items, onToggle) {
    const inputs = {};
    for (const [key, label] of items) {
      const wrap = document.createElement("label");
      wrap.className = "inline";
      const input = document.createElement("input");
      input.type = "checkbox";
      input.checked = true;
      input.addEventListener("change", () => onToggle(key, input.checked));
      wrap.append(input, ` ${label}`);
      container.append(wrap);
      inputs[key] = input;
    }
    return inputs;
  }

  // --- State ------------------------------------------------------------------

  /** Page size (mm) of the loaded poster and default text boxes from /api/layout. */
  setPage(width, height, boxes) {
    this.width = width;
    this.height = height;
    this.boxes = boxes || {};
    this.overlay.setAttribute("viewBox", `0 0 ${width} ${height}`);
    this.render();
  }

  setBoxes(boxes) {
    this.boxes = boxes || {};
    this.render();
  }

  snapshot() {
    return JSON.parse(JSON.stringify(this.edits));
  }

  isEmpty() {
    const e = this.edits;
    return !e.erase.length && !e.hidden_layers.length
      && Object.values(e.text).every((t) => !t.hidden && !t.dx && !t.dy);
  }

  commit(next) {
    if (JSON.stringify(next) === JSON.stringify(this.edits)) {
      this.render();
      return;
    }
    this.undoStack.push(this.edits);
    this.redoStack = [];
    this.edits = next;
    this.changed();
  }

  /** Clear all edits and history without notifying (used when the location changes). */
  clear() {
    this.edits = emptyEdits();
    this.undoStack = [];
    this.redoStack = [];
    this.selected = null;
    this.render();
  }

  undo() {
    if (!this.undoStack.length) return;
    this.redoStack.push(this.edits);
    this.edits = this.undoStack.pop();
    this.changed();
  }

  redo() {
    if (!this.redoStack.length) return;
    this.undoStack.push(this.edits);
    this.edits = this.redoStack.pop();
    this.changed();
  }

  changed() {
    if (this.selected !== null && this.selected >= this.edits.erase.length) this.selected = null;
    this.render();
    this.onChange(this.edits);
  }

  setLayerVisible(key, visible) {
    const next = this.snapshot();
    next.hidden_layers = next.hidden_layers.filter((k) => k !== key);
    if (!visible) next.hidden_layers.push(key);
    this.commit(next);
  }

  layerHidden(key) {
    return this.edits.hidden_layers.includes(key);
  }

  setTool(tool) {
    this.tool = tool;
    for (const btn of this.toolbar.querySelectorAll(".tool")) {
      btn.setAttribute("aria-pressed", String(btn.dataset.tool === tool));
    }
    this.overlay.dataset.tool = tool;
    if (tool !== "select") this.selected = null;
    this.render();
  }

  deleteSelected() {
    if (this.selected === null) return;
    const next = this.snapshot();
    next.erase.splice(this.selected, 1);
    this.selected = null;
    this.commit(next);
  }

  // --- Pointer handling -----------------------------------------------------------

  toPage(e) {
    const pt = this.overlay.createSVGPoint();
    pt.x = e.clientX;
    pt.y = e.clientY;
    const p = pt.matrixTransform(this.overlay.getScreenCTM().inverse());
    return [round(p.x), round(p.y)];
  }

  pointerDown(e) {
    if (e.button !== 0) return;
    const p = this.toPage(e);
    const target = e.target;
    if (this.tool === "move" && target.dataset.textKey) {
      const key = target.dataset.textKey;
      const t = this.edits.text[key] || {};
      this.drag = { kind: "move", key, start: p, dx: t.dx || 0, dy: t.dy || 0 };
    } else if (this.tool === "select") {
      this.selected = target.dataset.eraseIndex !== undefined ? Number(target.dataset.eraseIndex) : null;
      this.render();
      return;
    } else if (this.tool === "rect") {
      this.drag = { kind: "rect", start: p, end: p };
    } else if (this.tool === "free") {
      this.drag = { kind: "free", points: [p] };
    } else {
      return;
    }
    this.overlay.setPointerCapture(e.pointerId);
    e.preventDefault();
  }

  pointerMove(e) {
    if (!this.drag) return;
    const p = this.toPage(e);
    const d = this.drag;
    if (d.kind === "move") {
      d.current = [round(d.dx + p[0] - d.start[0]), round(d.dy + p[1] - d.start[1])];
    } else if (d.kind === "rect") {
      d.end = p;
    } else if (d.kind === "free") {
      const last = d.points[d.points.length - 1];
      if (Math.hypot(p[0] - last[0], p[1] - last[1]) >= FREEHAND_STEP) d.points.push(p);
    }
    this.render();
  }

  pointerUp(e) {
    const d = this.drag;
    if (!d) return;
    this.drag = null;
    if (this.overlay.hasPointerCapture(e.pointerId)) this.overlay.releasePointerCapture(e.pointerId);
    const next = this.snapshot();
    if (d.kind === "move" && d.current) {
      const t = next.text[d.key] || { hidden: false };
      next.text[d.key] = { ...t, dx: d.current[0], dy: d.current[1] };
      this.commit(next);
    } else if (d.kind === "rect") {
      const [x0, y0] = d.start;
      const [x1, y1] = d.end;
      if (Math.abs(x1 - x0) >= MIN_SIZE && Math.abs(y1 - y0) >= MIN_SIZE) {
        next.erase.push([[x0, y0], [x1, y0], [x1, y1], [x0, y1]]);
        this.commit(next);
      } else {
        this.render();
      }
    } else if (d.kind === "free") {
      if (d.points.length >= 3) {
        next.erase.push(d.points);
        this.commit(next);
      } else {
        this.render();
      }
    } else {
      this.render();
    }
  }

  cancelDrag() {
    this.drag = null;
    this.render();
  }

  keyDown(e) {
    if (this.overlay.closest("[hidden]")) return;
    const typing = ["INPUT", "SELECT", "TEXTAREA"].includes(document.activeElement?.tagName);
    if (typing) return;
    const mod = e.ctrlKey || e.metaKey;
    if (mod && e.key.toLowerCase() === "z" && !e.shiftKey) {
      this.undo();
      e.preventDefault();
    } else if (mod && (e.key.toLowerCase() === "y" || (e.key.toLowerCase() === "z" && e.shiftKey))) {
      this.redo();
      e.preventDefault();
    } else if ((e.key === "Delete" || e.key === "Backspace") && this.selected !== null) {
      this.deleteSelected();
      e.preventDefault();
    }
  }

  // --- Drawing ---------------------------------------------------------------------

  render() {
    const svg = this.overlay;
    svg.replaceChildren();

    this.edits.erase.forEach((poly, i) => {
      svg.append(el("polygon", {
        class: `erase${this.selected === i ? " selected" : ""}`,
        points: poly.map((p) => p.join(",")).join(" "),
        "data-erase-index": i,
      }));
    });

    for (const [key] of TEXT_KEYS) {
      const box = this.boxes[key];
      if (!box) continue;
      const t = this.edits.text[key] || {};
      let [dx, dy] = [t.dx || 0, t.dy || 0];
      if (this.drag?.kind === "move" && this.drag.key === key && this.drag.current) [dx, dy] = this.drag.current;
      const pad = 1;
      const [x0, y0, x1, y1] = box;
      svg.append(el("rect", {
        class: `text-handle${t.hidden ? " hidden-text" : ""}`,
        x: x0 + dx - pad,
        y: y0 + dy - pad,
        width: x1 - x0 + 2 * pad,
        height: Math.max(y1 - y0, 1) + 2 * pad,
        "data-text-key": key,
      }));
    }

    const d = this.drag;
    if (d?.kind === "rect") {
      const [x0, y0] = d.start;
      const [x1, y1] = d.end;
      svg.append(el("rect", {
        class: "erase drawing",
        x: Math.min(x0, x1), y: Math.min(y0, y1), width: Math.abs(x1 - x0), height: Math.abs(y1 - y0),
      }));
    } else if (d?.kind === "free") {
      svg.append(el("polyline", { class: "erase drawing", points: d.points.map((p) => p.join(",")).join(" ") }));
    }

    for (const [key, input] of Object.entries(this.textInputs)) input.checked = !this.edits.text[key]?.hidden;
    for (const [key, input] of Object.entries(this.layerInputs)) {
      input.checked = !this.edits.hidden_layers.includes(key);
    }
    this.buttons.delete.disabled = this.selected === null;
    this.buttons.undo.disabled = !this.undoStack.length;
    this.buttons.redo.disabled = !this.redoStack.length;
    this.buttons.reset.disabled = this.isEmpty();
  }
}
