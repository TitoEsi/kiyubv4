export type Pan = { x: number; y: number }
export type Insets = { top: number; right: number; bottom: number; left: number }
export type ContentBounds = { w: number; h: number }

/** Range of one pan axis: content of `size` px starts at `base + pan` inside a view [lo, hi]. */
function axisRange(size: number, base: number, lo: number, hi: number, margin: number): [number, number] {
  if (size > hi - lo - 2 * margin) {
    return [hi - margin - size - base, lo + margin - base]
  }
  const min = lo - base
  const max = hi - size - base
  return min <= max ? [min, max] : [max, min]
}

/**
 * Keeps the drawn content reachable: larger-than-view content can slide until its far edge meets the
 * view edge (plus margin); content that fits stays fully inside the view.
 */
export function clampPan({
  pan, S, bounds, cw, ch, inset, margin,
}: {
  pan: Pan
  S: number
  bounds: ContentBounds
  cw: number
  ch: number
  inset: Insets
  margin: number
}): Pan {
  const [x0, x1] = axisRange(bounds.w * S, margin + inset.left, inset.left, cw - inset.right, margin)
  const [y0, y1] = axisRange(bounds.h * S, margin + inset.top, inset.top, ch - inset.bottom, margin)
  return {
    x: Math.min(x1, Math.max(x0, pan.x)),
    y: Math.min(y1, Math.max(y0, pan.y)),
  }
}

export const FOCUS_MIN_ZOOM = 1
export const FOCUS_MAX_ZOOM = 4
const FOCUS_FILL = 0.6

/**
 * Zoom/pan that centres `rect` (plan meters) in the usable viewport, sized so it fills roughly
 * `FOCUS_FILL` of the available space. `baseS` is the px-per-meter scale at zoom 1.
 */
export function fitRoomView({
  rect, bounds, baseS, cw, ch, inset, margin,
}: {
  rect: { minX: number; minY: number; maxX: number; maxY: number }
  bounds: ContentBounds & { minX: number; minY: number }
  baseS: number
  cw: number
  ch: number
  inset: Insets
  margin: number
}): { zoom: number; pan: Pan } {
  const availW = Math.max(1, cw - inset.left - inset.right)
  const availH = Math.max(1, ch - inset.top - inset.bottom)
  const rw = Math.max(rect.maxX - rect.minX, 0.01)
  const rh = Math.max(rect.maxY - rect.minY, 0.01)
  const fit = Math.min((availW * FOCUS_FILL) / (rw * baseS), (availH * FOCUS_FILL) / (rh * baseS))
  const zoom = Math.min(FOCUS_MAX_ZOOM, Math.max(FOCUS_MIN_ZOOM, fit))
  const S = baseS * zoom
  const cx = inset.left + availW / 2
  const cy = inset.top + availH / 2
  const pan = {
    x: cx - margin - inset.left - ((rect.minX + rect.maxX) / 2 - bounds.minX) * S,
    y: cy - margin - inset.top - ((rect.minY + rect.maxY) / 2 - bounds.minY) * S,
  }
  return { zoom, pan: clampPan({ pan, S, bounds, cw, ch, inset, margin }) }
}

/** SVG user-space point to plan meters, for a plan drawn with origin (`ox`, `oy`) at `S` px per meter. */
export function screenToPlan(loc: { x: number; y: number }, ox: number, oy: number, S: number): { x: number; y: number } {
  return { x: (loc.x - ox) / S, y: (loc.y - oy) / S }
}

/** Plan meters to SVG user space; the inverse of `screenToPlan`. */
export function planToScreen(p: { x: number; y: number }, ox: number, oy: number, S: number): { x: number; y: number } {
  return { x: ox + p.x * S, y: oy + p.y * S }
}

/** Left-drag on empty canvas pans only when zoomed in with the Select tool. */
export function canStartEmptyPan({
  zoom, tool, annotationMode, button,
}: {
  zoom: number
  tool: string
  annotationMode: boolean
  button: number
}): boolean {
  return zoom > 1 + 1e-6 && tool === 'select' && !annotationMode && button === 0
}
