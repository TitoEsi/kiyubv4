import type { Opening, OpeningType, SceneDocument, Wall } from '../types'
import { cloneScene, touchScene } from './clone'
import { NODE_EPS, nearestOnWall, wallDir, wallLength, wallPointAtT } from './geometry'
import { deriveDoorSwing, doorSwing, isSwingDoor, openingT, wallNormal, type DoorHinge, type DoorSwingSide } from './door-geometry'

export { openingT }

function newId(prefix: string): string {
  return `${prefix}-${Math.random().toString(36).slice(2, 10)}`
}

/** Keeps a door's world-space hinge end and opening direction when it changes host wall. */
function rehostSwing(opening: Opening, from: Wall | undefined, to: Wall) {
  if (!from || !isSwingDoor(opening.type) || wallLength(from) < 1e-9) return
  const { hinge, swingSide } = doorSwing(opening)
  const df = wallDir(from), dt = wallDir(to)
  const nf = wallNormal(from), nt = wallNormal(to)
  const sameDir = df.x * dt.x + df.y * dt.y >= 0
  const sameSide = (nf.x * swingSide) * nt.x + (nf.y * swingSide) * nt.y >= 0
  opening.metadata = {
    ...(opening.metadata || {}),
    hinge: sameDir ? hinge : hinge === 'start' ? 'end' : 'start',
    swingSide: sameSide ? 1 : -1,
  }
}

export function syncOpeningsToWalls(scene: SceneDocument): SceneDocument {
  const next = cloneScene(scene)
  const byId = new Map(next.walls.map(w => [w.id, w]))
  const keep: Opening[] = []
  for (const opening of next.openings) {
    let wall = byId.get(opening.wallId)
    if (!wall || wallLength(wall) < NODE_EPS * 2) {
      const previous = wall
      wall = nearestHostWall(next, opening.position)
      if (!wall) continue
      rehostSwing(opening, previous, wall)
      opening.wallId = wall.id
      if (opening.metadata) delete opening.metadata.t
    }
    const t = openingT(opening, wall)
    const half = (opening.width / 2) / wallLength(wall)
    const clamped = Math.max(half + 0.02, Math.min(1 - half - 0.02, t))
    opening.metadata = { ...(opening.metadata || {}), t: clamped }
    opening.position = wallPointAtT(wall, clamped)
    const ang = Math.atan2(wall.end.y - wall.start.y, wall.end.x - wall.start.x) * 180 / Math.PI
    opening.rotation = ang
    keep.push(opening)
  }
  next.openings = keep
  for (const wall of next.walls) {
    wall.openingIds = keep.filter(o => o.wallId === wall.id).map(o => o.id)
  }
  return next
}

function nearestHostWall(scene: SceneDocument, p: { x: number; y: number }): Wall | undefined {
  let best: Wall | undefined
  let bestD = Infinity
  for (const wall of scene.walls) {
    if (wallLength(wall) < NODE_EPS * 2) continue
    const on = nearestOnWall(wall, p)
    const d = Math.hypot(on.x - p.x, on.y - p.y)
    if (d < bestD) {
      bestD = d
      best = wall
    }
  }
  return best
}

export function createOpening(
  scene: SceneDocument,
  wallId: string,
  type: OpeningType,
  t: number,
  widthM = type === 'window' ? 1.2 : 0.9,
): SceneDocument {
  const next = cloneScene(scene)
  const wall = next.walls.find(w => w.id === wallId)
  if (!wall) return scene
  const opening: Opening = {
    id: newId(type === 'window' ? 'win' : 'door'),
    floorId: wall.floorId,
    wallId,
    type,
    position: wallPointAtT(wall, t),
    width: widthM,
    height: type === 'window' ? 1.2 : 2.1,
    sillHeight: type === 'window' ? 0.9 : 0,
    rotation: 0,
    metadata: { t, roomIds: [...wall.roomIds] },
  }
  if (isSwingDoor(type)) {
    const swing = deriveDoorSwing(opening, wall, next.rooms)
    opening.metadata = { ...opening.metadata, hinge: swing.hinge, swingSide: swing.swingSide }
  }
  next.openings.push(opening)
  wall.openingIds.push(opening.id)
  return syncOpeningsToWalls(touchScene(next))
}

export function moveOpening(scene: SceneDocument, openingId: string, t: number): SceneDocument {
  const next = cloneScene(scene)
  const opening = next.openings.find(o => o.id === openingId)
  if (!opening) return scene
  opening.metadata = { ...(opening.metadata || {}), t }
  return syncOpeningsToWalls(touchScene(next))
}

export function resizeOpening(scene: SceneDocument, openingId: string, widthM: number): SceneDocument {
  const next = cloneScene(scene)
  const opening = next.openings.find(o => o.id === openingId)
  if (!opening) return scene
  opening.width = Math.max(0.4, widthM)
  return syncOpeningsToWalls(touchScene(next))
}

function setSwing(scene: SceneDocument, openingId: string, update: (hinge: DoorHinge, side: DoorSwingSide) => [DoorHinge, DoorSwingSide]): SceneDocument {
  const next = cloneScene(scene)
  const opening = next.openings.find(o => o.id === openingId)
  if (!opening) return scene
  const { hinge, swingSide } = doorSwing(opening)
  const [h, s] = update(hinge, swingSide)
  opening.metadata = { ...(opening.metadata || {}), hinge: h, swingSide: s }
  return touchScene(next)
}

export function flipDoorHinge(scene: SceneDocument, openingId: string): SceneDocument {
  return setSwing(scene, openingId, (h, s) => [h === 'start' ? 'end' : 'start', s])
}

export function flipDoorSwing(scene: SceneDocument, openingId: string): SceneDocument {
  return setSwing(scene, openingId, (h, s) => [h, s === 1 ? -1 : 1])
}

const ROTATE_CYCLE: Array<[DoorHinge, DoorSwingSide]> = [['start', 1], ['end', 1], ['end', -1], ['start', -1]]

/** Steps the door leaf through its four quadrants. */
export function rotateOpening(scene: SceneDocument, openingId: string): SceneDocument {
  return setSwing(scene, openingId, (h, s) => {
    const i = ROTATE_CYCLE.findIndex(([ch, cs]) => ch === h && cs === s)
    return ROTATE_CYCLE[(i + 1) % ROTATE_CYCLE.length]
  })
}

export function deleteOpening(scene: SceneDocument, openingId: string): SceneDocument {
  const next = cloneScene(scene)
  next.openings = next.openings.filter(o => o.id !== openingId)
  for (const wall of next.walls) {
    wall.openingIds = wall.openingIds.filter(id => id !== openingId)
  }
  return touchScene(next)
}

export function setOpeningType(scene: SceneDocument, openingId: string, type: OpeningType): SceneDocument {
  const next = cloneScene(scene)
  const opening = next.openings.find(o => o.id === openingId)
  if (!opening) return scene
  opening.type = type
  const wall = next.walls.find(w => w.id === opening.wallId)
  if (wall && isSwingDoor(type) && opening.metadata?.swingSide == null) {
    const swing = deriveDoorSwing(opening, wall, next.rooms)
    opening.metadata = { ...(opening.metadata || {}), hinge: swing.hinge, swingSide: swing.swingSide }
  }
  return touchScene(next)
}
