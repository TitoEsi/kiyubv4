import { describe, expect, it } from 'vitest'
import { canStartEmptyPan, clampPan, fitRoomView, FOCUS_MAX_ZOOM, FOCUS_MIN_ZOOM, planToScreen, screenToPlan } from './plan-viewport'

describe('screenToPlan', () => {
  it('round-trips plan points exactly at every zoom and pan', () => {
    const baseS = 37.3
    const pts = [{ x: 0, y: 0 }, { x: 1.07, y: 1.13 }, { x: 12.34, y: 7.65 }]
    for (const zoom of [0.5, 1, 1.5, 2, 4]) {
      for (const pan of [{ x: 0, y: 0 }, { x: -183.5, y: 92.25 }]) {
        const S = baseS * zoom
        const ox = 48 + pan.x - 0.5 * S, oy = 48 + pan.y - 0.75 * S
        for (const p of pts) {
          const back = screenToPlan(planToScreen(p, ox, oy, S), ox, oy, S)
          expect(back.x).toBeCloseTo(p.x, 10)
          expect(back.y).toBeCloseTo(p.y, 10)
        }
      }
    }
  })
})

const inset = { top: 0, right: 0, bottom: 0, left: 0 }
const M = 48

describe('clampPan', () => {
  // 800x600 view, 1000x1000 px content (bounds 10x10 m at 100 px/m).
  const big = { S: 100, bounds: { w: 10, h: 10 }, cw: 800, ch: 600, inset, margin: M }

  it('leaves an in-range pan alone', () => {
    expect(clampPan({ ...big, pan: { x: -100, y: -200 } })).toEqual({ x: -100, y: -200 })
  })

  it('stops the near edge at one margin from the view edge', () => {
    expect(clampPan({ ...big, pan: { x: 5000, y: 5000 } })).toEqual({ x: 0, y: 0 })
  })

  it('stops the far edge at one margin from the opposite view edge', () => {
    const p = clampPan({ ...big, pan: { x: -5000, y: -5000 } })
    expect(M + p.x + 1000).toBeCloseTo(800 - M)
    expect(M + p.y + 1000).toBeCloseTo(600 - M)
  })

  it('makes every corner reachable', () => {
    const lo = clampPan({ ...big, pan: { x: -1e6, y: -1e6 } })
    const hi = clampPan({ ...big, pan: { x: 1e6, y: 1e6 } })
    expect(hi.x - lo.x).toBeCloseTo(1000 - (800 - 2 * M))
    expect(hi.y - lo.y).toBeCloseTo(1000 - (600 - 2 * M))
  })

  it('keeps content that fits fully inside the view', () => {
    const small = { S: 30, bounds: { w: 10, h: 10 }, cw: 800, ch: 600, inset, margin: M }
    const right = clampPan({ ...small, pan: { x: 5000, y: 5000 } })
    expect(M + right.x + 300).toBeCloseTo(800)
    expect(M + right.y + 300).toBeCloseTo(600)
    const left = clampPan({ ...small, pan: { x: -5000, y: -5000 } })
    expect(M + left.x).toBeCloseTo(0)
    expect(M + left.y).toBeCloseTo(0)
    expect(clampPan({ ...small, pan: { x: 0, y: 0 } })).toEqual({ x: 0, y: 0 })
  })

  it('respects insets', () => {
    const p = clampPan({ ...big, inset: { top: 56, right: 0, bottom: 0, left: 0 }, pan: { x: 0, y: 5000 } })
    expect(p.y).toBe(0)
    const q = clampPan({ ...big, inset: { top: 56, right: 0, bottom: 0, left: 0 }, pan: { x: 0, y: -5000 } })
    expect(M + 56 + q.y + 1000).toBeCloseTo(600 - M)
  })

  it('is a no-op at fit zoom', () => {
    const S = Math.min((800 - 2 * M) / 20, (600 - 2 * M) / 30)
    expect(clampPan({ S, bounds: { w: 20, h: 30 }, cw: 800, ch: 600, inset, margin: M, pan: { x: 0, y: 0 } }))
      .toEqual({ x: 0, y: 0 })
  })
})

describe('fitRoomView', () => {
  // 20x30 m plan in an 800x600 view at fit scale.
  const bounds = { minX: 0, minY: 0, w: 20, h: 30 }
  const baseS = Math.min((800 - 2 * M) / 20, (600 - 2 * M) / 30)
  const view = { bounds, baseS, cw: 800, ch: 600, inset, margin: M }
  const screen = (x: number, y: number, r: { zoom: number; pan: { x: number; y: number } }) => ({
    x: M + r.pan.x + (x - bounds.minX) * baseS * r.zoom,
    y: M + r.pan.y + (y - bounds.minY) * baseS * r.zoom,
  })

  it('centres a room in the view', () => {
    const r = fitRoomView({ ...view, rect: { minX: 8, minY: 12, maxX: 12, maxY: 16 } })
    const c = screen(10, 14, r)
    expect(c.x).toBeCloseTo(400)
    expect(c.y).toBeCloseTo(300)
    expect(r.zoom).toBeGreaterThan(1)
  })

  it('never zooms out below 1 or past the maximum', () => {
    expect(fitRoomView({ ...view, rect: { minX: 0, minY: 0, maxX: 20, maxY: 30 } }).zoom).toBe(FOCUS_MIN_ZOOM)
    expect(fitRoomView({ ...view, rect: { minX: 10, minY: 10, maxX: 10.1, maxY: 10.1 } }).zoom).toBe(FOCUS_MAX_ZOOM)
  })

  it('clamps the pan for rooms at the plan edge', () => {
    const r = fitRoomView({ ...view, rect: { minX: 0, minY: 0, maxX: 2, maxY: 2 } })
    const S = baseS * r.zoom
    expect(r.pan).toEqual(clampPan({ pan: r.pan, S, bounds, cw: 800, ch: 600, inset, margin: M }))
    expect(r.pan.x).toBeLessThanOrEqual(0)
    expect(r.pan.y).toBeLessThanOrEqual(0)
  })

  it('centres within the inset viewport', () => {
    const withInset = { ...view, inset: { top: 0, right: 200, bottom: 0, left: 0 } }
    const r = fitRoomView({ ...withInset, rect: { minX: 9, minY: 14, maxX: 11, maxY: 16 } })
    expect(screen(10, 15, r).x).toBeCloseTo(300)
  })
})

describe('canStartEmptyPan', () => {
  const base = { zoom: 1.5, tool: 'select', annotationMode: false, button: 0 }

  it('allows left-drag with Select when zoomed in', () => {
    expect(canStartEmptyPan(base)).toBe(true)
  })

  it.each([
    ['at 100%', { zoom: 1 }],
    ['zoomed out', { zoom: 0.6 }],
    ['wall tool', { tool: 'wall' }],
    ['door tool', { tool: 'door' }],
    ['measure tool', { tool: 'measure' }],
    ['annotation mode', { annotationMode: true }],
    ['right button', { button: 2 }],
  ])('refuses %s', (_, patch) => {
    expect(canStartEmptyPan({ ...base, ...patch })).toBe(false)
  })
})
