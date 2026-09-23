import { describe, expect, it } from 'vitest'
import type { FloorPlan } from '../../types/floorplan'
import { loadLiveScene } from './load-scene'
import { createWall, deleteWall, joinWalls, moveEndpoint, moveWall, setWallLength, splitWall } from './wall-ops'
import { createOpening, deleteOpening, moveOpening, resizeOpening } from './opening-ops'
import { deleteFurniture, moveFurniture, rotateFurniture } from './furniture-ops'
import { wallLength, dist } from './geometry'
import { createHistory, commit, undo, redo } from './history'
import { deriveRoomsFromWalls } from './derive-rooms'
import { snapPoint } from './snap'

const PLAN: FloorPlan = {
  id: 'p',
  name: 'Edit',
  totalWidth: 40,
  totalHeight: 30,
  ceilingHeight: 9,
  rooms: [
    { id: 'living', name: 'Living', type: 'living_room', x: 2, y: 2, width: 16, height: 14, color: '#ccc' },
  ],
  doors: [],
}

function scene() {
  return loadLiveScene(PLAN, { lotWidth: 20, lotDepth: 20 }, { projectId: 'p' })
}

describe('wall graph ops', () => {
  it('creates, moves, extends, shortens, splits, joins, and deletes walls', () => {
    let s = scene()
    const before = s.walls.length
    s = createWall(s, { x: 1, y: 1 }, { x: 4, y: 1 })
    expect(s.walls.length).toBe(before + 1)
    const id = s.walls[s.walls.length - 1].id
    const start = { ...s.walls.find(w => w.id === id)!.start }
    s = moveWall(s, id, { x: 0.5, y: 0 })
    expect(s.walls.find(w => w.id === id)!.start.x).toBeCloseTo(start.x + 0.5, 5)
    s = moveEndpoint(s, id, 'end', { x: 6, y: 1 })
    expect(wallLength(s.walls.find(w => w.id === id)!)).toBeGreaterThan(4)
    s = setWallLength(s, id, 2)
    expect(wallLength(s.walls.find(w => w.id === id)!)).toBeCloseTo(2, 2)
    s = splitWall(s, id, 0.5)
    expect(s.walls.length).toBe(before + 2)
    const a = s.walls[s.walls.length - 2]
    const b = s.walls[s.walls.length - 1]
    s = joinWalls(s, a.id, b.id)
    expect(s.walls.some(w => w.id === b.id)).toBe(false)
    s = deleteWall(s, a.id)
    expect(s.walls.some(w => w.id === a.id)).toBe(false)
  })

  it('moves a shared junction when connected endpoints move', () => {
    let s = createWall(scene(), { x: 0, y: 0 }, { x: 3, y: 0 })
    s = createWall(s, { x: 3, y: 0 }, { x: 3, y: 3 })
    const h = s.walls.find(w => Math.abs(w.start.y - w.end.y) < 0.01)!
    const v = s.walls.find(w => Math.abs(w.start.x - w.end.x) < 0.01)!
    s = moveEndpoint(s, h.id, 'end', { x: 4, y: 0 })
    const v2 = s.walls.find(w => w.id === v.id)!
    expect(dist(v2.start, { x: 4, y: 0 }) < 0.2 || dist(v2.end, { x: 4, y: 0 }) < 0.2).toBe(true)
  })
})

describe('openings stay hosted on walls', () => {
  it('creates, moves, resizes, and deletes a door on a wall', () => {
    let s = scene()
    const wall = s.walls[0]
    s = createOpening(s, wall.id, 'door', 0.5)
    const door = s.openings.find(o => o.type === 'door')
    expect(door?.wallId).toBe(wall.id)
    s = moveOpening(s, door!.id, 0.3)
    expect(s.openings[0].wallId).toBe(wall.id)
    s = resizeOpening(s, door!.id, 1.2)
    expect(s.openings[0].width).toBeCloseTo(1.2, 5)
    s = deleteOpening(s, door!.id)
    expect(s.openings.find(o => o.id === door!.id)).toBeUndefined()
  })

  it('keeps the opening on the wall after the wall moves', () => {
    let s = scene()
    const wall = s.walls[0]
    s = createOpening(s, wall.id, 'window', 0.4)
    s = moveWall(s, wall.id, { x: 0.4, y: 0 })
    const opening = s.openings.find(o => o.type === 'window')!
    const moved = s.walls.find(w => w.id === wall.id)!
    expect(opening.wallId).toBe(wall.id)
    expect(dist(opening.position, moved.start) + dist(opening.position, moved.end))
      .toBeCloseTo(wallLength(moved), 1)
  })
})

describe('history', () => {
  it('undoes and redoes a wall create', () => {
    const base = scene()
    let h = createHistory(base)
    const next = createWall(base, { x: 0, y: 0 }, { x: 2, y: 0 })
    h = commit(h, next)
    expect(h.present.walls.length).toBeGreaterThan(base.walls.length)
    h = undo(h)
    expect(h.present.walls.length).toBe(base.walls.length)
    h = redo(h)
    expect(h.present.walls.length).toBe(next.walls.length)
  })
})

describe('derived rooms', () => {
  it('updates room polygons after a wall moves', () => {
    let s = scene()
    const living = s.rooms.find(r => r.id === 'living')
    expect(living).toBeTruthy()
    const before = living!.area
    const wall = s.walls[0]
    s = moveWall(s, wall.id, { x: 0.2, y: 0 })
    s = deriveRoomsFromWalls(s)
    const after = s.rooms.find(r => r.id === 'living')
    expect(after?.polygon.length).toBeGreaterThan(2)
    expect(after?.id).toBe('living')
    expect(typeof after?.area).toBe('number')
    expect(before).toBeGreaterThan(0)
  })
})

describe('snap', () => {
  it('snaps to grid and nearby endpoints when enabled', () => {
    const s = scene()
    const end = s.walls[0].start
    const snapped = snapPoint({ x: end.x + 0.01, y: end.y + 0.01 }, {
      grid: 0.3,
      enabled: true,
      walls: s.walls,
    })
    expect(snapped.point.x).toBeCloseTo(end.x, 2)
    expect(snapped.point.y).toBeCloseTo(end.y, 2)
    const raw = snapPoint({ x: 1.11, y: 2.22 }, { grid: 0.3, enabled: false, walls: s.walls })
    expect(raw.point.x).toBeCloseTo(1.11, 5)
  })
})

describe('furniture ops', () => {
  it('moves, rotates, and deletes furniture without dropping it from the scene graph', () => {
    let s = scene()
    s = {
      ...s,
      furniture: [{
        id: 'sofa-1',
        roomId: 'living',
        kind: 'sofa',
        position: { x: 1, y: 1 },
        dimensions: { width: 2, height: 0.9 },
        rotation: 0,
      }],
    }
    s = moveFurniture(s, 'sofa-1', { x: 1.4, y: 1.1 })
    expect(s.furniture[0].position.x).toBeCloseTo(1.4, 5)
    s = rotateFurniture(s, 'sofa-1', 90)
    expect(s.furniture[0].rotation).toBe(90)
    s = deleteFurniture(s, 'sofa-1')
    expect(s.furniture).toHaveLength(0)
  })
})
