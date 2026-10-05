import { describe, expect, it } from 'vitest'
import type { FloorPlan } from '../../types/floorplan'
import { loadLiveScene } from './load-scene'
import { createWall, deleteWall, joinWalls, moveEndpoint, moveWall, setWallLength, setWallThickness, splitWall } from './wall-ops'
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
    const corner = { x: 3, y: 0 }
    const h = s.walls.find(w => dist(w.end, corner) < 1e-9 && Math.abs(w.start.y - w.end.y) < 0.01)!
    const v = s.walls.find(w => dist(w.start, corner) < 1e-9 && Math.abs(w.start.x - w.end.x) < 0.01)!
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
    const prev = s
    s = moveWall(s, wall.id, { x: 0.2, y: 0 })
    s = deriveRoomsFromWalls(s, prev)
    const after = s.rooms.find(r => r.id === 'living')
    expect(after?.polygon.length).toBeGreaterThan(2)
    expect(after?.id).toBe('living')
    expect(typeof after?.area).toBe('number')
    expect(before).toBeGreaterThan(0)
  })
})

describe('new wall trim and topology', () => {
  function box(s: ReturnType<typeof scene>) {
    const xs = s.walls.flatMap(w => [w.start.x, w.end.x])
    const ys = s.walls.flatMap(w => [w.start.y, w.end.y])
    return { left: Math.min(...xs), right: Math.max(...xs), top: Math.min(...ys), bottom: Math.max(...ys) }
  }
  const at = (p: { x: number; y: number }, q: { x: number; y: number }) => dist(p, q) < 1e-9
  const wallsAt = (s: ReturnType<typeof scene>, p: { x: number; y: number }) =>
    s.walls.filter(w => at(w.start, p) || at(w.end, p))
  const nodeAt = (w: ReturnType<typeof scene>['walls'][number], p: { x: number; y: number }) =>
    w.metadata?.[at(w.start, p) ? 'startNodeId' : 'endNodeId']

  it('splits the host walls at a T-junction so the endpoints share one node', () => {
    const s0 = scene()
    const b = box(s0)
    const x = b.left + (b.right - b.left) / 3
    const top = { x, y: b.top }, bottom = { x, y: b.bottom }
    const s = createWall(s0, top, bottom)
    expect(s.walls.length).toBe(s0.walls.length + 3)
    for (const p of [top, bottom]) {
      const meeting = wallsAt(s, p)
      expect(meeting).toHaveLength(3)
      expect(new Set(meeting.map(w => nodeAt(w, p))).size).toBe(1)
    }
  })

  it('re-derives the room after a wall is drawn across it', () => {
    const s0 = scene()
    const b = box(s0)
    const before = s0.rooms.find(r => r.id === 'living')!.area
    const x = b.left + (b.right - b.left) / 3
    const s = deriveRoomsFromWalls(createWall(s0, { x, y: b.top }, { x, y: b.bottom }), s0)
    const living = s.rooms.find(r => r.id === 'living')!
    expect(living.area).toBeCloseTo(before * 2 / 3, 6)
    expect(Math.min(...living.polygon.map(p => p.x))).toBeCloseTo(x, 9)
  })

  it('splits both walls where a new wall crosses an existing one', () => {
    const s0 = scene()
    const b = box(s0)
    const y = (b.top + b.bottom) / 2
    const s = createWall(s0, { x: b.left - 1, y }, { x: b.right + 1, y })
    expect(s.walls.length).toBe(s0.walls.length + 2 + 3)
    for (const p of [{ x: b.left, y }, { x: b.right, y }]) {
      const meeting = wallsAt(s, p)
      expect(meeting).toHaveLength(4)
      expect(new Set(meeting.map(w => nodeAt(w, p))).size).toBe(1)
    }
  })

  it('trims a stub that overshoots the crossed wall by no more than its thickness', () => {
    const s0 = scene()
    const b = box(s0)
    const x = (b.left + b.right) / 2
    const s = createWall(s0, { x, y: b.top - 0.1 }, { x, y: b.top + 2 })
    const added = s.walls.filter(w => !s0.walls.some(o => o.id === w.id) && at(w.end, { x, y: b.top + 2 }))
    expect(added).toHaveLength(1)
    expect(added[0].start).toEqual({ x, y: b.top })
    expect(s.walls.some(w => w.start.y < b.top - 1e-9 || w.end.y < b.top - 1e-9)).toBe(false)
  })

  it('uses the crossed wall thickness as the trim limit', () => {
    const s0 = scene()
    const b = box(s0)
    const x = (b.left + b.right) / 2
    const topWall = s0.walls.find(w => Math.abs(w.start.y - b.top) < 1e-9 && Math.abs(w.end.y - b.top) < 1e-9)!
    const thick = setWallThickness(s0, topWall.id, 0.3)
    const stubOutside = (s: ReturnType<typeof scene>) => s.walls.some(w => Math.min(w.start.y, w.end.y) < b.top - 1e-9)
    expect(stubOutside(createWall(thick, { x, y: b.top - 0.25 }, { x, y: b.top + 2 }))).toBe(false)
    expect(stubOutside(createWall(s0, { x, y: b.top - 0.25 }, { x, y: b.top + 2 }))).toBe(true)
  })

  it('drops a wall already covered by a collinear wall and clips a partial overlap', () => {
    const s0 = scene()
    const b = box(s0)
    expect(createWall(s0, { x: b.left + 0.5, y: b.top }, { x: b.right - 0.5, y: b.top })).toBe(s0)
    const s = createWall(s0, { x: b.right - 1, y: b.top }, { x: b.right + 2, y: b.top })
    const added = s.walls.filter(w => !s0.walls.some(o => o.id === w.id))
    expect(added).toHaveLength(1)
    expect(added[0].start).toEqual({ x: b.right, y: b.top })
    expect(added[0].end).toEqual({ x: b.right + 2, y: b.top })
  })

  it('keeps a door on the correct half of a split host wall', () => {
    const s0 = scene()
    const b = box(s0)
    const topWall = s0.walls.find(w => Math.abs(w.start.y - b.top) < 1e-9 && Math.abs(w.end.y - b.top) < 1e-9)!
    let s = createOpening(s0, topWall.id, 'door', 0.8)
    const door = s.openings.find(o => o.type === 'door')!
    const x = b.left + (b.right - b.left) / 3
    s = createWall(s, { x, y: b.top }, { x, y: b.bottom })
    const after = s.openings.find(o => o.id === door.id)!
    const host = s.walls.find(w => w.id === after.wallId)!
    expect(dist(after.position, door.position)).toBeLessThan(1e-6)
    expect(Math.min(host.start.x, host.end.x)).toBeLessThanOrEqual(door.position.x)
    expect(Math.max(host.start.x, host.end.x)).toBeGreaterThanOrEqual(door.position.x)
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
