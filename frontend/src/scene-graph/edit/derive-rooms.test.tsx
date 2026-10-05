import { describe, expect, it } from 'vitest'
import { renderToStaticMarkup } from 'react-dom/server'
import type { FloorPlan } from '../../types/floorplan'
import type { Point2D, SceneDocument } from '../types'
import { loadLiveScene } from './load-scene'
import { createWall, moveWall } from './wall-ops'
import { deriveRoomsFromWalls } from './derive-rooms'
import { syncOpeningsToWalls } from './opening-ops'
import ScenePlan2D from '../../components/ScenePlan2D'
import { roomFill } from '../room-colors'

const FT = 0.3048

/** Client-style plan: rooms share edges, with T-junctions where the hallway meets the rooms above/below. */
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

function load(): SceneDocument {
  const s = loadLiveScene(GRID_PLAN, { lotWidth: 20, lotDepth: 20 }, { projectId: 'p' })
  return {
    ...s,
    furniture: [
      { id: 'sofa-1', roomId: 'great', kind: 'sofa', position: { x: 1, y: 6 }, dimensions: { width: 2, height: 0.9 }, rotation: 0 },
      { id: 'bed-1', roomId: 'bed2', kind: 'bed', position: { x: 7, y: 0.5 }, dimensions: { width: 1.6, height: 2 }, rotation: 0 },
    ],
  }
}

function afterGeom(prev: SceneDocument, next: SceneDocument) {
  return deriveRoomsFromWalls(syncOpeningsToWalls(next), prev)
}

function inside(poly: Point2D[], p: Point2D) {
  let hit = false
  for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
    const a = poly[i], b = poly[j]
    if ((a.y > p.y) !== (b.y > p.y) && p.x < ((b.x - a.x) * (p.y - a.y)) / (b.y - a.y) + a.x) hit = !hit
  }
  return hit
}

const roomCenter = (r: SceneDocument['rooms'][number]) => ({
  x: r.position.x + r.dimensions.width / 2,
  y: r.position.y + r.dimensions.height / 2,
})

function render(scene: SceneDocument) {
  return renderToStaticMarkup(
    <ScenePlan2D
      scene={scene}
      lot={{ width: 20, depth: 20 }}
      tool="wall"
      snapEnabled
      grid={0.3}
      editingEnabled
      selected={null}
      onSelect={() => {}}
      zoom={1}
      pan={{ x: 0, y: 0 }}
    />,
  )
}

describe('room re-derivation after an Architect edit', () => {
  it('keeps every room in place when one wall is added outside the building', () => {
    const before = load()
    const after = afterGeom(before, createWall(before, { x: 15, y: 15 }, { x: 18, y: 15 }))
    expect(after.walls.length).toBe(before.walls.length + 1)
    expect(after.rooms.length).toBe(before.rooms.length)
    expect(after.furniture).toEqual(before.furniture)
    expect(after.openings.length).toBe(before.openings.length)
    for (const room of before.rooms) {
      const r = after.rooms.find(x => x.id === room.id)!
      expect(r.name).toBe(room.name)
      expect(r.type).toBe(room.type)
      expect(r.polygon).toEqual(room.polygon)
      expect(r.position).toEqual(room.position)
      expect(r.dimensions).toEqual(room.dimensions)
    }
  })

  it('only lets the room containing a new wall change', () => {
    const before = load()
    const great = before.rooms.find(r => r.id === 'great')!
    const c = roomCenter(great)
    const after = afterGeom(before, createWall(before, { x: c.x - 1, y: c.y }, { x: c.x + 1, y: c.y }))
    for (const room of before.rooms) {
      const r = after.rooms.find(x => x.id === room.id)!
      if (room.id !== 'great') expect(r.polygon).toEqual(room.polygon)
      expect(inside(r.polygon, roomCenter(room))).toBe(true)
    }
  })

  it('without a previous scene, still never hands a room a loop away from it', () => {
    const before = load()
    const after = deriveRoomsFromWalls(syncOpeningsToWalls(createWall(before, { x: 15, y: 15 }, { x: 18, y: 15 })))
    for (const room of before.rooms) {
      const r = after.rooms.find(x => x.id === room.id)!
      expect(inside(r.polygon, roomCenter(room))).toBe(true)
      expect(r.area).toBeCloseTo(room.area, 3)
    }
  })

  it('updates the adjacent room when its outer wall moves', () => {
    const before = load()
    const kitchen = before.rooms.find(r => r.id === 'kitchen')!
    const east = before.walls.find(w =>
      Math.abs(w.start.x - 32 * FT) < 1e-6 && Math.abs(w.end.x - 32 * FT) < 1e-6 && w.roomIds.includes('kitchen'))!
    const after = afterGeom(before, moveWall(before, east.id, { x: 0.6, y: 0 }))
    const k = after.rooms.find(r => r.id === 'kitchen')!
    expect(k.area).toBeGreaterThan(kitchen.area)
    expect(after.rooms.find(r => r.id === 'garage')!.polygon).toEqual(before.rooms.find(r => r.id === 'garage')!.polygon)
  })

  it('renders the same presentation plus one wall after adding a wall', () => {
    const before = load()
    const after = afterGeom(before, createWall(before, { x: 15, y: 15 }, { x: 18, y: 15 }))
    const a = render(before)
    const b = render(after)
    const layers = (h: string) => [...h.matchAll(/data-layer="([a-z]+)"/g)].map(m => m[1])
    const count = (h: string, re: RegExp) => (h.match(re) ?? []).length
    expect(layers(b)).toEqual(layers(a))
    expect(count(b, /class="plan-room-label"/g)).toBe(count(a, /class="plan-room-label"/g))
    for (const room of after.rooms) expect(b).toContain(`fill="${roomFill(room.type)}"`)
    const roomLabels = (h: string) => [...h.matchAll(/<tspan[^>]*>([^<]+)<\/tspan>/g)].map(m => m[1]).sort()
    expect(roomLabels(b)).toEqual(roomLabels(a))
    for (const kind of ['sofa', 'bed']) expect(b).not.toMatch(new RegExp(`>\\s*${kind}\\s*<`))
    const walls = (h: string) => count(h.slice(h.indexOf('data-layer="walls"'), h.indexOf('data-layer="openings"')), /<line /g)
    expect(walls(b)).toBe(walls(a) + 1)
    expect(count(b, /class="north-indicator"/g)).toBe(1)
  })
})
