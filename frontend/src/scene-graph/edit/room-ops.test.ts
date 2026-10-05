import { describe, expect, it } from 'vitest'
import type { FloorPlan } from '../../types/floorplan'
import type { SceneDocument } from '../types'
import { loadLiveScene } from './load-scene'
import { resizeRoom, ROOM_MIN_M } from './room-ops'
import { deriveRoomsFromWalls } from './derive-rooms'
import { createOpening, syncOpeningsToWalls } from './opening-ops'
import { dist, wallLength } from './geometry'

const FT = 0.3048

const GRID_PLAN: FloorPlan = {
  id: 'grid',
  name: 'Grid',
  totalWidth: 40,
  totalHeight: 30,
  ceilingHeight: 9,
  rooms: [
    { id: 'garage', name: '2-Car Garage', type: 'garage', x: 0, y: 0, width: 14, height: 12, color: '#ccc' },
    { id: 'foyer', name: 'Entry Foyer', type: 'entry', x: 14, y: 0, width: 6, height: 12, color: '#ccc' },
    { id: 'bed2', name: 'Bedroom 2', type: 'bedroom', x: 20, y: 0, width: 12, height: 12, color: '#ccc' },
    { id: 'hall', name: 'Main Hallway', type: 'hallway', x: 0, y: 12, width: 32, height: 4, color: '#ccc' },
    { id: 'great', name: 'Great Room', type: 'living_room', x: 0, y: 16, width: 18, height: 14, color: '#ccc' },
    { id: 'kitchen', name: 'Kitchen', type: 'kitchen', x: 18, y: 16, width: 14, height: 14, color: '#ccc' },
  ],
  doors: [],
}

const load = () => loadLiveScene(GRID_PLAN, { lotWidth: 20, lotDepth: 20 }, { projectId: 'p' })
const room = (s: SceneDocument, id: string) => s.rooms.find(r => r.id === id)!
const afterGeom = (prev: SceneDocument, next: SceneDocument) => deriveRoomsFromWalls(syncOpeningsToWalls(next), prev)

describe('resizeRoom', () => {
  it('widens a room by moving its right wall, keeping the top-left corner', () => {
    const before = load()
    const k0 = room(before, 'kitchen')
    const after = resizeRoom(before, 'kitchen', 'width', k0.dimensions.width + 1)
    const k = room(after, 'kitchen')
    expect(k.position.x).toBeCloseTo(k0.position.x, 6)
    expect(k.position.y).toBeCloseTo(k0.position.y, 6)
    expect(k.dimensions.width).toBeCloseTo(k0.dimensions.width + 1, 6)
    expect(k.dimensions.height).toBeCloseTo(k0.dimensions.height, 6)
    expect(k.area).toBeCloseTo((k0.dimensions.width + 1) * k0.dimensions.height, 6)
    expect(Math.max(...k.polygon.map(p => p.x))).toBeCloseTo(32 * FT + 1, 6)
    expect(after.walls.some(w => Math.abs(w.start.x - (32 * FT + 1)) < 1e-6 && Math.abs(w.end.x - (32 * FT + 1)) < 1e-6)).toBe(true)
    expect(after.walls.some(w => Math.abs(w.start.x - 32 * FT) < 1e-6 && Math.abs(w.end.x - 32 * FT) < 1e-6)).toBe(false)
  })

  it('changes depth by moving the bottom wall and leaves unrelated rooms alone', () => {
    const before = load()
    const g0 = room(before, 'great')
    const after = resizeRoom(before, 'great', 'depth', g0.dimensions.height - 0.5)
    expect(room(after, 'great').dimensions.height).toBeCloseTo(g0.dimensions.height - 0.5, 6)
    expect(room(after, 'great').dimensions.width).toBeCloseTo(g0.dimensions.width, 6)
    for (const id of ['garage', 'foyer', 'bed2', 'hall']) {
      expect(room(after, id).polygon).toEqual(room(before, id).polygon)
    }
  })

  it('resizes the neighbour that shares the moved wall', () => {
    const before = load()
    const f0 = room(before, 'foyer')
    const b0 = room(before, 'bed2')
    const after = resizeRoom(before, 'foyer', 'width', f0.dimensions.width + 0.5)
    expect(room(after, 'foyer').dimensions.width).toBeCloseTo(f0.dimensions.width + 0.5, 6)
    expect(room(after, 'bed2').dimensions.width).toBeCloseTo(b0.dimensions.width - 0.5, 6)
    expect(room(after, 'bed2').position.x).toBeCloseTo(b0.position.x + 0.5, 6)
    expect(room(after, 'garage').polygon).toEqual(room(before, 'garage').polygon)
  })

  it('keeps the new geometry through room re-derivation', () => {
    const before = load()
    const k0 = room(before, 'kitchen')
    const after = afterGeom(before, resizeRoom(before, 'kitchen', 'depth', k0.dimensions.height + 0.8))
    expect(room(after, 'kitchen').dimensions.height).toBeCloseTo(k0.dimensions.height + 0.8, 6)
    expect(room(after, 'kitchen').area).toBeCloseTo(k0.dimensions.width * (k0.dimensions.height + 0.8), 4)
  })

  it('keeps openings hosted on the moved wall', () => {
    let s = load()
    const east = s.walls.find(w =>
      Math.abs(w.start.x - 32 * FT) < 1e-6 && Math.abs(w.end.x - 32 * FT) < 1e-6 && Math.min(w.start.y, w.end.y) >= 16 * FT - 1e-6)!
    s = createOpening(s, east.id, 'window', 0.5)
    const win = s.openings.find(o => o.type === 'window')!
    const after = resizeRoom(s, 'kitchen', 'width', room(s, 'kitchen').dimensions.width + 1)
    const moved = after.openings.find(o => o.id === win.id)!
    const host = after.walls.find(w => w.id === moved.wallId)!
    expect(moved.wallId).toBe(east.id)
    expect(dist(moved.position, host.start) + dist(moved.position, host.end)).toBeCloseTo(wallLength(host), 3)
    expect(moved.position.x).toBeCloseTo(32 * FT + 1, 3)
  })

  it('rejects impossible edits by returning the same scene', () => {
    const s = load()
    expect(resizeRoom(s, 'nope', 'width', 4)).toBe(s)
    expect(resizeRoom(s, 'kitchen', 'width', ROOM_MIN_M - 0.1)).toBe(s)
    expect(resizeRoom(s, 'kitchen', 'width', Number.NaN)).toBe(s)
    expect(resizeRoom(s, 'kitchen', 'width', room(s, 'kitchen').dimensions.width)).toBe(s)
    // Bedroom 2 is 12 ft wide; growing the foyer by 3 m would crush it.
    expect(resizeRoom(s, 'foyer', 'width', room(s, 'foyer').dimensions.width + 3)).toBe(s)
  })
})
