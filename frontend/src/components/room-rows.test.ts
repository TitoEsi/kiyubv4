import { describe, expect, it } from 'vitest'
import { DEFAULT_CEILING_M, planRoomRows, planSummary, sceneRoomRows, sceneSummary } from './room-rows'
import { resizeRoom } from '../scene-graph/edit/room-ops'
import { FIDELITY_PLAN } from '../scene-graph/adapters/fidelity.fixture'
import { floorPlanToSceneDocument } from '../scene-graph/adapters/floorplan-to-scene-document'
import type { SceneDocument } from '../scene-graph/types'

const scene = floorPlanToSceneDocument(FIDELITY_PLAN, { lotWidth: 15, lotDepth: 20, stories: 1 })

function withRoom(doc: SceneDocument, id: string, patch: Partial<SceneDocument['rooms'][number]>): SceneDocument {
  return { ...doc, rooms: doc.rooms.map(r => (r.id === id ? { ...r, ...patch } : r)) }
}

describe('planRoomRows', () => {
  it('uses width x height for area, as the Client list always has', () => {
    const rows = planRoomRows(FIDELITY_PLAN.rooms)
    FIDELITY_PLAN.rooms.forEach((r, i) => {
      expect(rows[i]).toEqual({ id: r.id, name: r.name, color: r.color, width: r.width, depth: r.height, area: r.width * r.height })
    })
  })
})

describe('sceneRoomRows', () => {
  const first = scene.rooms[0]

  it('lists every scene room with its dimensions, area and color', () => {
    const rows = sceneRoomRows(scene)
    expect(rows.map(r => r.id)).toEqual(scene.rooms.map(r => r.id))
    expect(rows[0].width).toBe(first.dimensions.width)
    expect(rows[0].depth).toBe(first.dimensions.height)
    expect(rows[0].area).toBe(first.area || first.dimensions.width * first.dimensions.height)
    expect(rows[0].color).toBe(first.metadata?.color)
  })

  it('reflects renames, resizes and recolors', () => {
    const next = withRoom(scene, first.id, {
      name: 'Studio',
      dimensions: { width: 5, height: 4 },
      area: 20,
      metadata: { ...first.metadata, color: '#123456' },
    })
    const row = sceneRoomRows(next)[0]
    expect(row).toMatchObject({ name: 'Studio', width: 5, depth: 4, area: 20, color: '#123456' })
  })

  it('falls back to width x depth when area is missing', () => {
    const row = sceneRoomRows(withRoom(scene, first.id, { dimensions: { width: 3, height: 2 }, area: 0 }))[0]
    expect(row.area).toBe(6)
  })

  it('follows added and removed rooms', () => {
    const added = { ...scene, rooms: [...scene.rooms, { ...first, id: 'new-room', name: 'New Room' }] }
    expect(sceneRoomRows(added).map(r => r.id)).toContain('new-room')
    const removed = { ...scene, rooms: scene.rooms.slice(1) }
    expect(sceneRoomRows(removed).map(r => r.id)).not.toContain(first.id)
  })
})

describe('planSummary', () => {
  it('keeps the Client calculation', () => {
    const s = planSummary(FIDELITY_PLAN)
    const living = FIDELITY_PLAN.rooms
      .filter(r => !['garage', 'patio', 'deck', 'rear_patio', 'outdoor_living', 'front_porch'].includes(r.type))
      .reduce((sum, r) => sum + r.width * r.height, 0)
    expect(s).toEqual({
      roomCount: FIDELITY_PLAN.rooms.length,
      livingAreaM2: living,
      footprintW: FIDELITY_PLAN.totalWidth,
      footprintD: FIDELITY_PLAN.totalHeight,
      ceilingM: FIDELITY_PLAN.ceilingHeight || DEFAULT_CEILING_M,
    })
  })
})

describe('sceneSummary', () => {
  it('counts rooms and follows additions and removals', () => {
    expect(sceneSummary(scene).roomCount).toBe(scene.rooms.length)
    const removed = { ...scene, rooms: scene.rooms.slice(1) }
    expect(sceneSummary(removed).roomCount).toBe(scene.rooms.length - 1)
  })

  it('excludes non-living rooms from living area', () => {
    const garage = { ...scene.rooms[0], id: 'g', type: 'garage' as const, metadata: { sourceType: 'garage' }, area: 30 }
    const withGarage = { ...scene, rooms: [...scene.rooms, garage] }
    expect(sceneSummary(withGarage).livingAreaM2).toBeCloseTo(sceneSummary(scene).livingAreaM2, 6)
  })

  it('recalculates living area and footprint after a room resize', () => {
    const before = sceneSummary(scene)
    const xs = scene.walls.flatMap(w => [w.start.x, w.end.x])
    const room = scene.rooms.find(r => r.position.x + r.dimensions.width >= Math.max(...xs) - 0.01)!
    const after = resizeRoom(scene, room.id, 'width', room.dimensions.width + 1)
    expect(after).not.toBe(scene)
    const s = sceneSummary(after)
    expect(s.footprintW).toBeCloseTo(before.footprintW + 1, 6)
    expect(s.livingAreaM2).toBeGreaterThan(before.livingAreaM2)
    expect(s.roomCount).toBe(before.roomCount)
  })
})
