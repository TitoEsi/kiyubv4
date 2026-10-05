import type { Point2D, SceneDocument, Wall } from '../types'
import { cloneScene, touchScene } from './clone'
import { assignJunctions } from './bootstrap-walls'
import { syncOpeningsToWalls } from './opening-ops'
import {
  NODE_EPS,
  add,
  collinear,
  dist,
  nodeIdOf,
  scale,
  segmentIntersection,
  sub,
  wallLength,
  wallPointAtT,
} from './geometry'

function newId(prefix: string): string {
  return `${prefix}-${Math.random().toString(36).slice(2, 10)}`
}

function rewireFloor(scene: SceneDocument) {
  if (scene.floorData[0]) {
    scene.floorData[0].wallIds = scene.walls.map(w => w.id)
    scene.floorData[0].openingIds = scene.openings.map(o => o.id)
  }
}

/** Distance at which a point counts as lying on a wall centerline. */
const ON_EPS = NODE_EPS / 5

function pointSegDist(p: Point2D, a: Point2D, b: Point2D): number {
  const d = sub(b, a)
  const len2 = d.x * d.x + d.y * d.y
  const t = len2 > 0 ? Math.max(0, Math.min(1, ((p.x - a.x) * d.x + (p.y - a.y) * d.y) / len2)) : 0
  return dist(p, add(a, scale(d, t)))
}

/** True when `p` lies on the wall but away from both of its ends. */
function onWallInterior(wall: Wall, p: Point2D): boolean {
  return pointSegDist(p, wall.start, wall.end) <= ON_EPS
    && dist(p, wall.start) > ON_EPS && dist(p, wall.end) > ON_EPS
}

/** Parameter intervals of a→b already covered by collinear walls. */
function coveredIntervals(walls: Wall[], a: Point2D, b: Point2D): Array<[number, number]> {
  const d = sub(b, a)
  const len = Math.hypot(d.x, d.y)
  const u = scale(d, 1 / len)
  const param = (p: Point2D) => ((p.x - a.x) * u.x + (p.y - a.y) * u.y) / len
  const offset = (p: Point2D) => Math.abs((p.x - a.x) * u.y - (p.y - a.y) * u.x)
  const out: Array<[number, number]> = []
  for (const w of walls) {
    if (offset(w.start) > ON_EPS || offset(w.end) > ON_EPS) continue
    const lo = Math.max(0, Math.min(param(w.start), param(w.end)))
    const hi = Math.min(1, Math.max(param(w.start), param(w.end)))
    if ((hi - lo) * len > ON_EPS) out.push([lo, hi])
  }
  return out.sort((x, y) => x[0] - y[0])
}

function uncovered(covered: Array<[number, number]>): Array<[number, number]> {
  const out: Array<[number, number]> = []
  let cursor = 0
  for (const [lo, hi] of covered) {
    if (lo > cursor) out.push([cursor, lo])
    cursor = Math.max(cursor, hi)
  }
  if (cursor < 1) out.push([cursor, 1])
  return out
}

interface Cut { t: number; point: Point2D; thickness: number }

/** Points along a→b where existing walls meet or cross it, with the thickness of the wall met. */
function cutsAlong(walls: Wall[], a: Point2D, b: Point2D): Cut[] {
  const len = dist(a, b)
  const cuts: Cut[] = []
  const push = (t: number, point: Point2D, thickness: number) => {
    if (t * len <= ON_EPS || (1 - t) * len <= ON_EPS) return
    const same = cuts.find(c => Math.abs(c.t - t) * len <= ON_EPS)
    if (same) same.thickness = Math.max(same.thickness, thickness)
    else cuts.push({ t, point, thickness })
  }
  for (const w of walls) {
    for (const v of [w.start, w.end]) {
      if (pointSegDist(v, a, b) <= ON_EPS) {
        const t = ((v.x - a.x) * (b.x - a.x) + (v.y - a.y) * (b.y - a.y)) / (len * len)
        push(t, { ...v }, w.thickness)
      }
    }
    const hit = segmentIntersection(a, b, w.start, w.end)
    if (!hit || hit.u < 0 || hit.u > 1) continue
    const wl = wallLength(w)
    if (hit.u * wl <= ON_EPS || (1 - hit.u) * wl <= ON_EPS) continue
    push(hit.t, hit.point, w.thickness)
  }
  return cuts.sort((x, y) => x.t - y.t)
}

function touchesWalls(walls: Wall[], p: Point2D): boolean {
  return walls.some(w => pointSegDist(p, w.start, w.end) <= ON_EPS)
}

/**
 * Add a wall from `start` to `end` and keep the wall graph connected: parts already covered by a
 * collinear wall are dropped, the new wall is cut where it meets or crosses existing walls, those
 * walls are split at the same points, and a free end that overshoots a crossing by no more than the
 * crossed wall's thickness is trimmed back to it.
 */
export function createWall(scene: SceneDocument, start: Point2D, end: Point2D): SceneDocument {
  if (dist(start, end) < NODE_EPS) return scene
  const next = cloneScene(scene)
  const existing = [...next.walls]
  const floorId = next.floorData[0]?.id || 'floor-1'
  const height = next.walls[0]?.height || next.floorData[0]?.height || 2.74
  const along = (t: number) => add(start, scale(sub(end, start), t))

  const added: Wall[] = []
  for (const [lo, hi] of uncovered(coveredIntervals(existing, start, end))) {
    const a = lo === 0 ? { ...start } : along(lo)
    const b = hi === 1 ? { ...end } : along(hi)
    if (dist(a, b) < NODE_EPS) continue
    const cuts = cutsAlong(existing, a, b)
    const pts = [a, ...cuts.map(c => c.point), b]
    let from = 0, to = pts.length - 1
    if (cuts.length && !touchesWalls(existing, a) && dist(a, cuts[0].point) <= cuts[0].thickness) from = 1
    const last = cuts[cuts.length - 1]
    if (cuts.length && !touchesWalls(existing, b) && dist(b, last.point) <= last.thickness) to = pts.length - 2
    for (let i = from; i < to; i++) {
      if (dist(pts[i], pts[i + 1]) < NODE_EPS) continue
      added.push({
        id: newId('wall'),
        floorId,
        type: 'interior',
        start: { ...pts[i] },
        end: { ...pts[i + 1] },
        thickness: 0.15,
        height,
        roomIds: [],
        openingIds: [],
        metadata: {},
      })
    }
  }
  if (!added.length) return scene

  for (const p of added.flatMap(w => [w.start, w.end])) {
    const host = next.walls.find(w => onWallInterior(w, p))
    if (host) splitWallAt(next, host, p)
  }
  next.walls.push(...added)
  rewireFloor(next)
  return assignJunctions(syncOpeningsToWalls(touchScene(next)))
}

export function deleteWall(scene: SceneDocument, wallId: string): SceneDocument {
  const next = cloneScene(scene)
  next.walls = next.walls.filter(w => w.id !== wallId)
  next.openings = next.openings.filter(o => o.wallId !== wallId)
  for (const room of next.rooms) {
    room.wallIds = room.wallIds.filter(id => id !== wallId)
    room.openingIds = room.openingIds.filter(id => next.openings.some(o => o.id === id))
  }
  rewireFloor(next)
  return assignJunctions(syncOpeningsToWalls(touchScene(next)))
}

export function moveWall(scene: SceneDocument, wallId: string, delta: Point2D): SceneDocument {
  const next = cloneScene(scene)
  const wall = next.walls.find(w => w.id === wallId)
  if (!wall) return scene
  const startId = nodeIdOf(wall, 'start')
  const endId = nodeIdOf(wall, 'end')
  const junctions = new Set([startId, endId].filter((id): id is string => !!id))
  for (const w of next.walls) {
    const s = nodeIdOf(w, 'start'), e = nodeIdOf(w, 'end')
    if ((s && junctions.has(s)) || (w.id === wallId && !startId)) {
      w.start = add(w.start, delta)
    }
    if ((e && junctions.has(e)) || (w.id === wallId && !endId)) {
      w.end = add(w.end, delta)
    }
  }
  return assignJunctions(syncOpeningsToWalls(touchScene(next)))
}

export function moveEndpoint(
  scene: SceneDocument,
  wallId: string,
  which: 'start' | 'end',
  to: Point2D,
): SceneDocument {
  const next = cloneScene(scene)
  const wall = next.walls.find(w => w.id === wallId)
  if (!wall) return scene
  const nodeId = nodeIdOf(wall, which)
  if (nodeId) {
    for (const w of next.walls) {
      if (nodeIdOf(w, 'start') === nodeId) w.start = { ...to }
      if (nodeIdOf(w, 'end') === nodeId) w.end = { ...to }
    }
  } else {
    wall[which] = { ...to }
  }
  if (wallLength(wall) < NODE_EPS) return scene
  return assignJunctions(syncOpeningsToWalls(touchScene(next)))
}

export function splitWall(scene: SceneDocument, wallId: string, t: number): SceneDocument {
  const clamped = Math.max(0.05, Math.min(0.95, t))
  const next = cloneScene(scene)
  const wall = next.walls.find(w => w.id === wallId)
  if (!wall) return scene
  splitWallAt(next, wall, wallPointAtT(wall, clamped))
  rewireFloor(next)
  return assignJunctions(syncOpeningsToWalls(touchScene(next)))
}

/** Split `wall` (owned by the mutable `next`) exactly at `point`, which must lie on it. */
function splitWallAt(next: SceneDocument, wall: Wall, point: Point2D): Wall {
  const wallId = wall.id
  const len = wallLength(wall)
  const clamped = len > 0 ? dist(wall.start, point) / len : 0.5
  const mid = { ...point }
  const second: Wall = {
    id: newId('wall'),
    floorId: wall.floorId,
    type: wall.type,
    start: { ...mid },
    end: { ...wall.end },
    thickness: wall.thickness,
    height: wall.height,
    roomIds: [...wall.roomIds],
    openingIds: [],
    metadata: { ...(wall.metadata || {}) },
  }
  wall.end = { ...mid }
  wall.openingIds = []
  next.walls.push(second)
  for (const opening of next.openings.filter(o => o.wallId === wallId)) {
    const ot = typeof opening.metadata?.t === 'number' ? opening.metadata.t as number : 0.5
    if (ot > clamped) {
      opening.wallId = second.id
      const nt = (ot - clamped) / (1 - clamped)
      opening.metadata = { ...(opening.metadata || {}), t: nt }
      second.openingIds.push(opening.id)
    } else {
      const nt = clamped < 1e-6 ? 0 : ot / clamped
      opening.metadata = { ...(opening.metadata || {}), t: nt }
      wall.openingIds.push(opening.id)
    }
  }
  return second
}

export function joinWalls(scene: SceneDocument, aId: string, bId: string): SceneDocument {
  if (aId === bId) return scene
  const next = cloneScene(scene)
  const a = next.walls.find(w => w.id === aId)
  const b = next.walls.find(w => w.id === bId)
  if (!a || !b || !collinear(a, b)) return scene
  const pts = [a.start, a.end, b.start, b.end]
  let maxD = -1
  let start = a.start
  let end = a.end
  for (const p of pts) {
    for (const q of pts) {
      const d = dist(p, q)
      if (d > maxD) {
        maxD = d
        start = p
        end = q
      }
    }
  }
  a.start = { ...start }
  a.end = { ...end }
  a.roomIds = Array.from(new Set([...a.roomIds, ...b.roomIds]))
  a.type = a.roomIds.length > 1 ? 'interior' : 'exterior'
  for (const opening of next.openings.filter(o => o.wallId === b.id)) {
    opening.wallId = a.id
    const meta: Record<string, unknown> = { ...(opening.metadata || {}) }
    delete meta.t
    opening.metadata = meta
    a.openingIds.push(opening.id)
  }
  next.walls = next.walls.filter(w => w.id !== b.id)
  rewireFloor(next)
  return assignJunctions(syncOpeningsToWalls(touchScene(next)))
}

export function setWallLength(scene: SceneDocument, wallId: string, lengthM: number): SceneDocument {
  const next = cloneScene(scene)
  const wall = next.walls.find(w => w.id === wallId)
  if (!wall || lengthM <= NODE_EPS) return scene
  const dir = scale(sub(wall.end, wall.start), 1 / wallLength(wall))
  return moveEndpoint(next, wallId, 'end', add(wall.start, scale(dir, lengthM)))
}

export function setWallThickness(scene: SceneDocument, wallId: string, thickness: number): SceneDocument {
  const next = cloneScene(scene)
  const wall = next.walls.find(w => w.id === wallId)
  if (!wall) return scene
  wall.thickness = Math.max(0.05, thickness)
  return touchScene(next)
}
