// Zoom and pan for the preview: the stage is resized inside a scrollable viewport.
// The editor overlay maps pointers through getScreenCTM(), so it works at any zoom.

const MIN_ZOOM = 1;
const MAX_ZOOM = 8;
const STEP = 1.25;

export class Zoom {
  /**
   * @param {object} opts
   * @param {HTMLElement} opts.viewport  scroll container
   * @param {HTMLElement} opts.stage     element to scale (keeps its aspect ratio)
   * @param {HTMLElement} opts.label     shows the zoom percentage
   * @param {function} opts.panning      returns true when a primary-button drag should pan
   */
  constructor({ viewport, stage, label, panning }) {
    this.viewport = viewport;
    this.stage = stage;
    this.label = label;
    this.panning = panning;
    this.zoom = 1;
    this.aspect = 0.75;
    this.pan = null;

    viewport.addEventListener("wheel", (e) => this.wheel(e), { passive: false });
    viewport.addEventListener("pointerdown", (e) => this.panStart(e));
    viewport.addEventListener("pointermove", (e) => this.panMove(e));
    viewport.addEventListener("pointerup", (e) => this.panEnd(e));
    viewport.addEventListener("pointercancel", (e) => this.panEnd(e));
    viewport.addEventListener("auxclick", (e) => e.button === 1 && e.preventDefault());
    new ResizeObserver(() => this.apply()).observe(viewport);
    this.apply();
  }

  setAspect(aspect) {
    this.aspect = aspect;
    this.apply();
  }

  /** Stage width at 100 % (fits the viewport). */
  fitWidth() {
    const style = getComputedStyle(this.viewport);
    const w = this.viewport.clientWidth - parseFloat(style.paddingLeft) - parseFloat(style.paddingRight);
    const h = this.viewport.clientHeight - parseFloat(style.paddingTop) - parseFloat(style.paddingBottom);
    return Math.max(50, Math.min(w, h * this.aspect));
  }

  apply() {
    const width = this.fitWidth() * this.zoom;
    this.stage.style.width = `${width}px`;
    this.stage.style.height = `${width / this.aspect}px`;
    this.label.textContent = `${Math.round(this.zoom * 100)}%`;
    this.viewport.classList.toggle("zoomed", this.zoom > 1);
  }

  /** Zoom to z, keeping the page point under (clientX, clientY) in place (default: viewport centre). */
  set(z, clientX, clientY) {
    z = Math.min(MAX_ZOOM, Math.max(MIN_ZOOM, z));
    const vp = this.viewport.getBoundingClientRect();
    const cx = clientX ?? vp.left + vp.width / 2;
    const cy = clientY ?? vp.top + vp.height / 2;
    const before = this.stage.getBoundingClientRect();
    const fx = (cx - before.left) / before.width;
    const fy = (cy - before.top) / before.height;
    this.zoom = z;
    this.apply();
    const after = this.stage.getBoundingClientRect();
    this.viewport.scrollLeft += after.left + fx * after.width - cx;
    this.viewport.scrollTop += after.top + fy * after.height - cy;
  }

  in() { this.set(this.zoom * STEP); }
  out() { this.set(this.zoom / STEP); }
  fit() { this.set(1); }

  wheel(e) {
    if (!e.ctrlKey && !e.metaKey) return;  // plain wheel scrolls
    e.preventDefault();
    this.set(this.zoom * Math.exp(-e.deltaY * 0.0015), e.clientX, e.clientY);
  }

  panStart(e) {
    if (!(e.button === 1 || (e.button === 0 && this.panning()))) return;
    e.preventDefault();
    this.pan = { x: e.clientX, y: e.clientY, left: this.viewport.scrollLeft, top: this.viewport.scrollTop };
    this.viewport.setPointerCapture(e.pointerId);
    this.viewport.classList.add("panning");
  }

  panMove(e) {
    if (!this.pan) return;
    this.viewport.scrollLeft = this.pan.left - (e.clientX - this.pan.x);
    this.viewport.scrollTop = this.pan.top - (e.clientY - this.pan.y);
  }

  panEnd(e) {
    if (!this.pan) return;
    this.pan = null;
    if (this.viewport.hasPointerCapture(e.pointerId)) this.viewport.releasePointerCapture(e.pointerId);
    this.viewport.classList.remove("panning");
  }
}
