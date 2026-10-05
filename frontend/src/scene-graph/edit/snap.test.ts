import { describe, expect, it } from 'vitest'
import type { Wall } from '../types'
import { NODE_EPS, nearestOnWall, dist } from './geometry'
import { SNAP_PICK_PX, snapPoint, snapToleranceFor } from './snap'

function wall(id: string, x1: number, y1: number, x2: number, y2: number, thickness = 0.15): Wall {
  return {
    id, floorId: 'f', type: 'interior', start: { x: x1, y: y1 }, end: { x: x2, y: y2 },
    thickness, height: 2.7, roomIds: [], openingIds: [], metadata: {},
  }
}

// Corner at (1.07, 1.13) is deliberately off the 0.3 m grid.
const WALLS = [
  wall('top', 1.07, 1.13, 5.07, 1.13),
  wall('left', 1.07, 1.13, 1.07, 4.13),
  wall('cross-a', 6, 0, 8, 2),
  wall('cross-b', 6, 2, 8, 0),
]
const S = 40
const opts = { grid: 0.3, enabled: true, walls: WALLS, tolerance: snapToleranceFor(S) }

describe('snapPoint', () => {
  it('lands exactly on a nearby wall endpoint', () => {
    const r = snapPoint({ x: 5.07 + 0.12, y: 1.13 - 0.1 }, opts)
    expect(r.kind).toBe('vertex')
    expect(r.point).toEqual({ x: 5.07, y: 1.13 })
  })

  it('prefers an off-grid corner over the grid and over the walls meeting there', () => {
    const r = snapPoint({ x: 1.07 + 0.15, y: 1.13 + 0.05 }, opts)
    expect(r.kind).toBe('vertex')
    expect(r.point).toEqual({ x: 1.07, y: 1.13 })
  })

  it('snaps to the crossing point of two walls', () => {
    const r = snapPoint({ x: 7.1, y: 1.08 }, opts)
    expect(r.kind).toBe('intersection')
    expect(r.point.x).toBeCloseTo(7, 9)
    expect(r.point.y).toBeCloseTo(1, 9)
  })

  it('projects onto the wall segment itself, with no axis drift afterwards', () => {
    const raw = { x: 3.01, y: 1.13 + 0.2 }
    const r = snapPoint(raw, opts)
    expect(r.kind).toBe('segment')
    expect(r.point).toEqual(nearestOnWall(WALLS[0], raw))
    expect(r.point.y).toBe(1.13)
    expect(r.point.x).toBeCloseTo(3.01, 9)
  })

  it('projects onto a diagonal wall exactly', () => {
    const r = snapPoint({ x: 6.5, y: 0.6 }, { ...opts, walls: [WALLS[2]] })
    expect(r.kind).toBe('segment')
    expect(r.point.x).toBeCloseTo(r.point.y + 6, 9)
  })

  it('does not force a snap outside the tolerance', () => {
    const tol = snapToleranceFor(S)
    const r = snapPoint({ x: 3.01, y: 1.13 + tol + 0.05 }, opts)
    expect(['grid', 'align']).toContain(r.kind)
    expect(r.point.y).not.toBe(1.13)
  })

  it('scales the tolerance with zoom so the screen reach stays constant', () => {
    for (const zoom of [0.5, 1, 1.5, 2, 4]) {
      const s = S * zoom
      const tol = snapToleranceFor(s)
      expect(tol).toBeCloseTo(Math.max(NODE_EPS * 1.5, SNAP_PICK_PX / s), 12)
      const near = snapPoint({ x: 3, y: 1.13 + tol * 0.9 }, { ...opts, tolerance: tol })
      const far = snapPoint({ x: 3, y: 1.13 + tol * 1.1 }, { ...opts, tolerance: tol })
      expect(near.kind).toBe('segment')
      expect(far.kind).not.toBe('segment')
    }
  })

  it('aligns to a vertex coordinate before falling back to the grid', () => {
    const r = snapPoint({ x: 1.07 + 0.1, y: 4.83 }, opts)
    expect(r.kind).toBe('align')
    expect(r.point.x).toBe(1.07)
    expect(r.point.y).toBeCloseTo(4.8, 9)
  })

  it('ignores excluded walls', () => {
    const r = snapPoint({ x: 5.1, y: 1.15 }, { ...opts, excludeWallIds: ['top'] })
    expect(r.kind).not.toBe('vertex')
    expect(dist(r.point, { x: 5.07, y: 1.13 })).toBeGreaterThan(0)
  })

  it('returns the raw point when disabled', () => {
    const r = snapPoint({ x: 5.1, y: 1.15 }, { ...opts, enabled: false })
    expect(r).toEqual({ point: { x: 5.1, y: 1.15 }, kind: 'none', guides: [] })
  })
})
