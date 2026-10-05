export interface PlanBounds {
  minX: number
  minY: number
  maxX: number
  maxY: number
  w: number
  h: number
}

/** Room left inside a document frame for dimension chains, text, and the north mark. */
export const DOCUMENT_MARGIN = 96

/**
 * Uniform scale that fits `bounds` inside `frame` with a margin on every side.
 * The drawing stays centred and keeps its aspect ratio.
 */
export function fitDrawingFrame(
  bounds: PlanBounds,
  frame: { width: number; height: number },
  margin = DOCUMENT_MARGIN,
): { S: number; ox: number; oy: number } {
  const innerW = Math.max(frame.width - margin * 2, 1)
  const innerH = Math.max(frame.height - margin * 2, 1)
  const S = Math.min(innerW / Math.max(bounds.w, 1e-6), innerH / Math.max(bounds.h, 1e-6))
  const drawnW = bounds.w * S
  const drawnH = bounds.h * S
  const ox = margin + (innerW - drawnW) / 2 - bounds.minX * S
  const oy = margin + (innerH - drawnH) / 2 - bounds.minY * S
  return { S, ox, oy }
}
