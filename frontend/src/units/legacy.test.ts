import { describe, expect, it } from 'vitest'
import type { FloorPlan } from '../types/floorplan'
import { normalizeCommentCoords, normalizeFloorPlan, normalizeQuestionnaire } from './legacy'
import { UNIT_ORDER, formatMeasurement, fromMeters, parseMeasurement, toMeters } from './measurement'
import { floorPlanToSceneDocument } from '../scene-graph/adapters/floorplan-to-scene-document'
import { sceneDocumentToFloorPlan } from '../scene-graph/adapters/scene-document-to-floorplan'

/** Pre-meters factor the app used to convert feet plans for display. */
const OLD_FT_TO_M = 1 / 3.28084

const LEGACY: FloorPlan = {
  id: 'legacy',
  name: 'Legacy',
  totalWidth: 40,
  totalHeight: 30,
  ceilingHeight: 9,
  rooms: [{ id: 'living', name: 'Living', type: 'living_room', x: 2, y: 3, width: 20, height: 15, color: '#ccc' }],
  doors: [{ x: 12, y: 3, isVertical: false, roomA: 'living', roomB: 'living' }],
  walls: [{ id: 'w', x1: 2, y1: 3, x2: 22, y2: 3, kind: 'exterior', roomIds: ['living'] }],
  openings: [{ id: 'o', wallId: 'w', kind: 'window', x: 8, y: 3, width: 4, height: 4, isVertical: false, sillHeight: 3 }],
  furniture: [{ id: 'f', roomId: 'living', kind: 'sofa', x: 4, y: 5, width: 7, depth: 3, rotation: 0 }],
}

describe('normalizeFloorPlan', () => {
  it('converts a legacy feet plan to meters and tags it', () => {
    const m = normalizeFloorPlan(LEGACY)
    expect(m.units).toBe('metric')
    expect(m.rooms[0].width).toBeCloseTo(6.096, 9)
    expect(m.walls![0].x2).toBeCloseTo(22 * 0.3048, 9)
    expect(m.openings![0].sillHeight).toBeCloseTo(0.9144, 9)
    expect(m.furniture![0].depth).toBeCloseTo(0.9144, 9)
    expect(m.ceilingHeight).toBeCloseTo(2.7432, 9)
  })

  it('is idempotent', () => {
    const m = normalizeFloorPlan(LEGACY)
    expect(normalizeFloorPlan(m)).toBe(m)
  })

  it('opens legacy projects at the same physical size and position as before', () => {
    const scene = floorPlanToSceneDocument(LEGACY, { lotWidth: 20, lotDepth: 15 })
    const room = scene.rooms[0]
    expect(Math.abs(room.position.x - 2 * OLD_FT_TO_M)).toBeLessThan(1e-5)
    expect(Math.abs(room.dimensions.width - 20 * OLD_FT_TO_M)).toBeLessThan(1e-5)
    expect(Math.abs(scene.walls[0].end.x - 22 * OLD_FT_TO_M)).toBeLessThan(1e-5)
  })

  it('round-trips a normalized plan through SceneDocument without drift', () => {
    const m = normalizeFloorPlan(LEGACY)
    const back = sceneDocumentToFloorPlan(floorPlanToSceneDocument(m, { lotWidth: 20, lotDepth: 15 }))
    expect(back.units).toBe('metric')
    expect(back.rooms[0].x).toBeCloseTo(m.rooms[0].x, 9)
    expect(back.rooms[0].width).toBeCloseTo(m.rooms[0].width, 9)
    expect(back.walls![0].x2).toBeCloseTo(m.walls![0].x2, 9)
  })
})

describe('display unit never changes geometry', () => {
  it('formatting in every unit leaves the plan untouched', () => {
    const m = normalizeFloorPlan(LEGACY)
    const before = JSON.stringify(m)
    for (const unit of UNIT_ORDER) formatMeasurement(m.rooms[0].width, unit)
    expect(JSON.stringify(m)).toBe(before)
  })

  it('re-entering a displayed value in any unit gives back the same meters', () => {
    const meters = 3.5
    for (const unit of UNIT_ORDER) {
      const shown = fromMeters(meters, unit)
      expect(toMeters(shown, unit)).toBeCloseTo(meters, 9)
      expect(parseMeasurement(String(shown), unit)).toBeCloseTo(meters, 9)
    }
  })
})

describe('legacy comment pins and briefs', () => {
  it('converts pins without coord_units from plan-feet', () => {
    const c = normalizeCommentCoords({ x: 9, y: 7, coord_units: null })
    expect(c.x).toBeCloseTo(2.7432, 9)
    expect(c.y).toBeCloseTo(2.1336, 9)
    expect(c.coord_units).toBe('metric')
  })

  it('leaves metric pins alone', () => {
    const c = { x: 2.5, y: 1, coord_units: 'metric' }
    expect(normalizeCommentCoords(c)).toBe(c)
  })

  it('maps legacy livingAreaSqft to livingAreaM2', () => {
    const q = normalizeQuestionnaire({ house: { bedrooms: 3, livingAreaSqft: 200 } })
    expect(q.house).toEqual({ bedrooms: 3, livingAreaM2: expect.closeTo(18.5806, 4) })
  })
})
