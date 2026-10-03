import { describe, expect, it } from 'vitest'
import type { FloorPlan } from '../../types/floorplan'
import { floorPlanToSceneDocument } from './floorplan-to-scene-document'
import { sceneDocumentToFloorPlan } from './scene-document-to-floorplan'
import { loadLiveScene } from '../edit/load-scene'
import { normalizeFloorPlan } from '../../units/legacy'

const PLAN: FloorPlan = {
  id: 'baseline',
  name: 'KIYUB v4 baseline',
  totalWidth: 55.5,
  totalHeight: 88.3,
  ceilingHeight: 9,
  rooms: [
    { id: 'living', name: 'Living Room', type: 'living_room', x: 10, y: 10, width: 14, height: 16, color: '#ccc' },
    { id: 'kitchen', name: 'Kitchen', type: 'kitchen', x: 24, y: 10, width: 12, height: 12, color: '#ddd' },
  ],
  doors: [],
  walls: [
    { id: 'w0', x1: 10, y1: 10, x2: 24, y2: 10, kind: 'exterior', roomIds: ['living'] },
  ],
  openings: [
    { id: 'd0', wallId: 'w0', kind: 'door', x: 16, y: 10, width: 3, isVertical: false, roomIds: ['living'] },
  ],
}

describe('sceneDocumentToFloorPlan', () => {
  it('round-trips wall endpoints within epsilon, in meters', () => {
    const scene = floorPlanToSceneDocument(PLAN, { lotWidth: 20, lotDepth: 30 })
    const back = sceneDocumentToFloorPlan(scene)
    const m = normalizeFloorPlan(PLAN)
    expect(back.units).toBe('metric')
    expect(back.walls?.[0].x1).toBeCloseTo(m.walls![0].x1, 6)
    expect(back.walls?.[0].x2).toBeCloseTo(m.walls![0].x2, 6)
    expect(back.openings?.[0].wallId).toBe('w0')
    expect(back.doors[0].wallId).toBe('w0')
    expect(back.rooms[0].width).toBeCloseTo(m.rooms[0].width, 6)
    expect(back.totalWidth).toBeCloseTo(m.totalWidth, 6)
  })

  it('reads the legacy envelopeWidthFt metadata as feet', () => {
    const scene = floorPlanToSceneDocument(PLAN, { lotWidth: 20, lotDepth: 30 })
    const extra = { ...scene.metadata.extra, envelopeWidthFt: 40, envelopeDepthFt: 30 } as Record<string, unknown>
    delete extra.envelopeWidthM
    delete extra.envelopeDepthM
    const back = sceneDocumentToFloorPlan({ ...scene, metadata: { ...scene.metadata, extra } })
    expect(back.totalWidth).toBeCloseTo(12.192, 9)
    expect(back.totalHeight).toBeCloseTo(9.144, 9)
  })

  it('bootstraps walls when the engine omitted them', () => {
    const empty: FloorPlan = { ...PLAN, walls: [], openings: [] }
    const scene = loadLiveScene(empty, { lotWidth: 20, lotDepth: 30 })
    expect(scene.walls.length).toBeGreaterThan(0)
    expect(floorPlanToSceneDocument(empty, { lotWidth: 20, lotDepth: 30 }).walls).toEqual([])
  })
})
