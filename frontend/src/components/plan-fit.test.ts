import { describe, expect, it } from 'vitest'
import { fitDrawingFrame, type PlanBounds } from './plan-fit'

function edges(bounds: PlanBounds, frame: { width: number; height: number }, margin: number) {
  const fit = fitDrawingFrame(bounds, frame, margin)
  return {
    fit,
    left: fit.ox + bounds.minX * fit.S,
    right: fit.ox + bounds.maxX * fit.S,
    top: fit.oy + bounds.minY * fit.S,
    bottom: fit.oy + bounds.maxY * fit.S,
  }
}

describe('fitDrawingFrame', () => {
  const bounds: PlanBounds = { minX: 2, minY: -1, maxX: 22, maxY: 9, w: 20, h: 10 }
  const frame = { width: 500, height: 400 }
  const margin = 40

  it('preserves aspect ratio and keeps the full bounds inside the frame', () => {
    const box = edges(bounds, frame, margin)
    expect((box.right - box.left) / (box.bottom - box.top)).toBeCloseTo(bounds.w / bounds.h, 6)
    expect(box.left).toBeGreaterThanOrEqual(margin - 0.01)
    expect(box.top).toBeGreaterThanOrEqual(margin - 0.01)
    expect(box.right).toBeLessThanOrEqual(frame.width - margin + 0.01)
    expect(box.bottom).toBeLessThanOrEqual(frame.height - margin + 0.01)
  })

  it('uses one scale for a wide plan and a tall plan', () => {
    const wide = fitDrawingFrame({ minX: 0, minY: 0, maxX: 40, maxY: 10, w: 40, h: 10 }, { width: 400, height: 400 }, 0)
    const tall = fitDrawingFrame({ minX: 0, minY: 0, maxX: 10, maxY: 40, w: 10, h: 40 }, { width: 400, height: 400 }, 0)
    expect(wide.S).toBeCloseTo(400 / 40, 6)
    expect(tall.S).toBeCloseTo(400 / 40, 6)
    expect(wide.S).toBeCloseTo(tall.S, 6)
  })
})
