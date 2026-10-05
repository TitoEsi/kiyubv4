import { describe, expect, it } from 'vitest'
import { buildSiteContext, lotRect, SITE_SETBACK_M } from './site-context'
import { loadLiveScene } from '../edit/load-scene'
import { FIDELITY_PLAN } from '../adapters/fidelity.fixture'
import type { SceneDocument } from '../types'
import { wallPointAtT } from '../edit/geometry'
import { openingT } from '../edit/opening-ops'

const scene = loadLiveScene(FIDELITY_PLAN, { lotWidth: 20, lotDepth: 30 })

function bounds(s: SceneDocument) {
  const xs: number[] = [], ys: number[] = []
  for (const w of s.walls) xs.push(w.start.x, w.end.x), ys.push(w.start.y, w.end.y)
  for (const r of s.rooms) {
    xs.push(r.position.x, r.position.x + r.dimensions.width)
    ys.push(r.position.y, r.position.y + r.dimensions.height)
  }
  return { minX: Math.min(...xs), maxX: Math.max(...xs), minY: Math.min(...ys), maxY: Math.max(...ys) }
}

function insideAnyRoom(s: SceneDocument, x: number, y: number) {
  return s.rooms.some(r => {
    const pts = r.polygon?.length ? r.polygon : [
      { x: r.position.x, y: r.position.y },
      { x: r.position.x + r.dimensions.width, y: r.position.y },
      { x: r.position.x + r.dimensions.width, y: r.position.y + r.dimensions.height },
      { x: r.position.x, y: r.position.y + r.dimensions.height },
    ]
    let inside = false
    for (let i = 0, j = pts.length - 1; i < pts.length; j = i++) {
      const xi = pts[i].x, yi = pts[i].y, xj = pts[j].x, yj = pts[j].y
      if ((yi > y) !== (yj > y) && x < ((xj - xi) * (y - yi)) / (yj - yi + 1e-12) + xi) inside = !inside
    }
    return inside
  })
}

describe('site context', () => {
  it('places the lot one setback before the envelope origin when the house fits', () => {
    const { lot, inferred } = lotRect(scene, { width: 20, depth: 30 })
    expect(inferred).toBe(false)
    expect(lot).toEqual({ x: -SITE_SETBACK_M, y: -SITE_SETBACK_M, width: 20, height: 30 })
  })

  it('centres the lot on an axis where the house does not fit within the setbacks', () => {
    const b = bounds(scene)
    const { lot } = lotRect(scene, { width: 13, depth: 30 })
    expect(lot!.x).toBeCloseTo((b.minX + b.maxX) / 2 - 6.5, 9)
    expect(lot!.y).toBe(-SITE_SETBACK_M)
  })

  it('uses the shorter side for square lots', () => {
    const { lot } = lotRect(scene, { width: 20, depth: 30, shape: 'square' })
    expect(lot!.width).toBe(20)
    expect(lot!.height).toBe(20)
  })

  it('infers a margin around the footprint when no lot is known', () => {
    const b = bounds(scene)
    const ctx = buildSiteContext(scene, null)
    expect(ctx.inferred).toBe(true)
    expect(ctx.lot!.x).toBeCloseTo(b.minX - SITE_SETBACK_M, 9)
    expect(ctx.lot!.width).toBeCloseTo(b.maxX - b.minX + 2 * SITE_SETBACK_M, 9)
  })

  it('is deterministic', () => {
    expect(buildSiteContext(scene, { width: 20, depth: 30 })).toEqual(buildSiteContext(scene, { width: 20, depth: 30 }))
  })

  it('keeps vegetation inside the lot, off the building and clear of doors', () => {
    const ctx = buildSiteContext(scene, { width: 20, depth: 30 })
    const lot = ctx.lot!
    const kinds = new Set(ctx.vegetation.map(v => v.kind))
    expect(kinds.has('tree-lg')).toBe(true)
    expect(kinds.size).toBeGreaterThan(2)
    const doors = scene.openings.filter(o => o.type !== 'window').map(o => {
      const host = scene.walls.find(w => w.id === o.wallId)!
      return wallPointAtT(host, openingT(o, host))
    })
    for (const v of ctx.vegetation) {
      expect(v.x).toBeGreaterThan(lot.x)
      expect(v.x).toBeLessThan(lot.x + lot.width)
      expect(v.y).toBeGreaterThan(lot.y)
      expect(v.y).toBeLessThan(lot.y + lot.height)
      expect(insideAnyRoom(scene, v.x, v.y)).toBe(false)
      for (const d of doors) expect(Math.hypot(v.x - d.x, v.y - d.y)).toBeGreaterThan(1.1)
    }
  })

  it('shows the lot without vegetation when the lot leaves no open ground', () => {
    const ctx = buildSiteContext(scene, { width: 4, depth: 4 })
    expect(ctx.lot).not.toBeNull()
    expect(ctx.vegetation).toEqual([])
  })

  it('handles an empty scene', () => {
    const empty = { ...scene, rooms: [], walls: [], openings: [] }
    expect(buildSiteContext(empty, null)).toEqual({ lot: null, inferred: true, vegetation: [] })
    expect(buildSiteContext(empty, { width: 10, depth: 10 }).vegetation).toEqual([])
  })
})
