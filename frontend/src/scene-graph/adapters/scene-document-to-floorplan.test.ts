import { describe, expect, it } from 'vitest'
import type { FloorPlan } from '../../types/floorplan'
import { floorPlanToSceneDocument } from './floorplan-to-scene-document'
import { sceneDocumentToFloorPlan } from './scene-document-to-floorplan'
import { loadLiveScene } from '../edit/load-scene'

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
  it('round-trips wall endpoints within epsilon', () => {
    const scene = floorPlanToSceneDocument(PLAN, { lotWidth: 20, lotDepth: 30 })
    const back = sceneDocumentToFloorPlan(scene)
    expect(back.walls?.[0].x1).toBeCloseTo(10, 2)
    expect(back.walls?.[0].x2).toBeCloseTo(24, 2)
    expect(back.openings?.[0].wallId).toBe('w0')
    expect(back.doors[0].wallId).toBe('w0')
    expect(back.rooms[0].width).toBeCloseTo(14, 2)
  })

  it('bootstraps walls when the engine omitted them', () => {
    const empty: FloorPlan = { ...PLAN, walls: [], openings: [] }
    const scene = loadLiveScene(empty, { lotWidth: 20, lotDepth: 30 })
    expect(scene.walls.length).toBeGreaterThan(0)
    expect(floorPlanToSceneDocument(empty, { lotWidth: 20, lotDepth: 30 }).walls).toEqual([])
  })
})
