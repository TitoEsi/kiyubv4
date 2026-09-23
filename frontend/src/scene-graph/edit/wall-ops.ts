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

export function createWall(scene: SceneDocument, start: Point2D, end: Point2D): SceneDocument {
  if (dist(start, end) < NODE_EPS) return scene
  const next = cloneScene(scene)
  const floorId = next.floorData[0]?.id || 'floor-1'
  const height = next.walls[0]?.height || next.floorData[0]?.height || 2.74
  const wall: Wall = {
    id: newId('wall'),
    floorId,
    type: 'interior',
    start: { ...start },
    end: { ...end },
    thickness: 0.15,
    height,
    roomIds: [],
    openingIds: [],
    metadata: {},
  }
  next.walls.push(wall)
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
  for (const w of next.walls) {
    if (nodeIdOf(w, 'start') === startId || (w.id === wallId && !startId)) {
      w.start = add(w.start, delta)
    }
    if (nodeIdOf(w, 'end') === endId || (w.id === wallId && !endId)) {
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
  const mid = wallPointAtT(wall, clamped)
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
  rewireFloor(next)
  return assignJunctions(syncOpeningsToWalls(touchScene(next)))
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
