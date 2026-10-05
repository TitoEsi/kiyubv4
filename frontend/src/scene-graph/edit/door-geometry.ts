import type { Opening, OpeningType, Point2D, Room, SceneDocument, Wall } from '../types'
import { projectT, wallDir, wallLength, wallPointAtT } from './geometry'

/** Jamb the leaf hangs from: the end of the opening nearer `wall.start` or `wall.end`. */
export type DoorHinge = 'start' | 'end'
/** Side of the host wall the leaf opens to, relative to the wall normal n = (-dir.y, dir.x). */
export type DoorSwingSide = 1 | -1

export interface DoorSwing {
  hinge: DoorHinge
  swingSide: DoorSwingSide
}

export interface DoorGeometry {
  hinge: Point2D
  /** Free end of the leaf when closed (the other jamb). */
  latch: Point2D
  /** Free end of the leaf opened 90°. */
  openEnd: Point2D
  radius: number
  /** SVG arc sweep flag for an arc from `latch` to `openEnd` centred on `hinge` (y-down coordinates). */
  sweep: 0 | 1
}

const SIDE_PROBE_M = 0.3
const CIRCULATION = new Set(['hallway', 'corridor', 'entry', 'stairs'])
const OUTDOOR = new Set(['porch', 'balcony'])
const OUTDOOR_NAME = /\b(patio|deck|terrace|porch|balcony|yard|garden)\b/i

export function isSwingDoor(type: OpeningType): boolean {
  return type === 'door'
}

export function openingT(opening: Opening, wall: Wall): number {
  if (typeof opening.metadata?.t === 'number') return opening.metadata.t as number
  return projectT(wall, opening.position)
}

export function wallNormal(wall: Wall): Point2D {
  const d = wallDir(wall)
  return { x: -d.y, y: d.x }
}

/** Ends of the opening along the host wall: `a` toward wall.start, `b` toward wall.end. */
export function openingEnds(opening: Opening, wall: Wall): { t0: number; t1: number; a: Point2D; b: Point2D } {
  const len = Math.max(wallLength(wall), 1e-6)
  const t = openingT(opening, wall)
  const half = opening.width / 2 / len
  const t0 = Math.max(0, t - half)
  const t1 = Math.min(1, t + half)
  return { t0, t1, a: wallPointAtT(wall, t0), b: wallPointAtT(wall, t1) }
}

function storedHinge(opening: Opening): DoorHinge | null {
  const h = opening.metadata?.hinge
  if (h === 'start' || h === 'end') return h
  if (h === 'right') return 'end'
  if (h === 'left') return 'start'
  return null
}

function storedSide(opening: Opening): DoorSwingSide | null {
  const s = opening.metadata?.swingSide
  return s === 1 || s === -1 ? s : null
}

/** Stored configuration; missing parts fall back to the legacy renderer's start hinge / +normal side. */
export function doorSwing(opening: Opening): DoorSwing {
  return { hinge: storedHinge(opening) ?? 'start', swingSide: storedSide(opening) ?? 1 }
}

export function doorGeometry(opening: Opening, wall: Wall): DoorGeometry {
  const { a, b } = openingEnds(opening, wall)
  const { hinge: side, swingSide } = doorSwing(opening)
  const hinge = side === 'start' ? a : b
  const latch = side === 'start' ? b : a
  const radius = Math.hypot(latch.x - hinge.x, latch.y - hinge.y)
  const n = wallNormal(wall)
  const openEnd = { x: hinge.x + n.x * swingSide * radius, y: hinge.y + n.y * swingSide * radius }
  const c = { x: latch.x - hinge.x, y: latch.y - hinge.y }
  const o = { x: openEnd.x - hinge.x, y: openEnd.y - hinge.y }
  const cross = c.x * o.y - c.y * o.x
  return { hinge, latch, openEnd, radius, sweep: cross > 0 ? 1 : 0 }
}

function roomPoly(room: Room): Point2D[] {
  if (room.polygon?.length) return room.polygon
  const { x, y } = room.position
  const { width, height } = room.dimensions
  return [{ x, y }, { x: x + width, y }, { x: x + width, y: y + height }, { x, y: y + height }]
}

function inside(poly: Point2D[], p: Point2D): boolean {
  let hit = false
  for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
    const u = poly[i], v = poly[j]
    if ((u.y > p.y) !== (v.y > p.y) && p.x < ((v.x - u.x) * (p.y - u.y)) / (v.y - u.y + 1e-12) + u.x) hit = !hit
  }
  return hit
}

function polyArea(poly: Point2D[]): number {
  let s = 0
  for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) s += poly[j].x * poly[i].y - poly[i].x * poly[j].y
  return Math.abs(s) / 2
}

function roomAt(rooms: Room[], p: Point2D, prefer: string[]): Room | null {
  const hits = rooms.filter(r => inside(roomPoly(r), p))
  return hits.find(r => prefer.includes(r.id)) ?? hits[0] ?? null
}

const isOutdoor = (r: Room | null) => !r || OUTDOOR.has(r.type) || OUTDOOR_NAME.test(r.name || '')

/**
 * Conventional residential configuration: exterior doors open inward, interior doors open away from
 * circulation (else into the smaller room), hinged on the jamb nearer the closer wall end.
 */
export function deriveDoorSwing(opening: Opening, wall: Wall, rooms: Room[]): DoorSwing {
  const { t0, t1 } = openingEnds(opening, wall)
  const hinge: DoorHinge = t0 <= 1 - t1 ? 'start' : 'end'
  const centre = wallPointAtT(wall, (t0 + t1) / 2)
  const n = wallNormal(wall)
  const prefer = (opening.metadata?.roomIds as string[] | undefined) ?? wall.roomIds ?? []
  const pos = roomAt(rooms, { x: centre.x + n.x * SIDE_PROBE_M, y: centre.y + n.y * SIDE_PROBE_M }, prefer)
  const neg = roomAt(rooms, { x: centre.x - n.x * SIDE_PROBE_M, y: centre.y - n.y * SIDE_PROBE_M }, prefer)

  let swingSide: DoorSwingSide = 1
  if (isOutdoor(pos) !== isOutdoor(neg)) swingSide = isOutdoor(pos) ? -1 : 1
  else if (pos && neg) {
    const pc = CIRCULATION.has(pos.type), nc = CIRCULATION.has(neg.type)
    if (pc !== nc) swingSide = pc ? -1 : 1
    else swingSide = polyArea(roomPoly(pos)) <= polyArea(roomPoly(neg)) ? 1 : -1
  }
  return { hinge, swingSide }
}

/** Fills in missing hinge / swing side. Explicit `right` hinges were user flips and are kept. */
export function normalizeDoorSwings(scene: SceneDocument): SceneDocument {
  const walls = new Map(scene.walls.map(w => [w.id, w]))
  let changed = false
  const openings = scene.openings.map(o => {
    if (!isSwingDoor(o.type)) return o
    const hinge = o.metadata?.hinge
    const side = storedSide(o)
    if (side && (hinge === 'start' || hinge === 'end')) return o
    const wall = walls.get(o.wallId)
    if (!wall) return o
    const derived = deriveDoorSwing(o, wall, scene.rooms)
    changed = true
    return {
      ...o,
      metadata: {
        ...(o.metadata || {}),
        hinge: hinge === 'right' || hinge === 'end' ? 'end' : hinge === 'start' && side ? 'start' : derived.hinge,
        swingSide: side ?? derived.swingSide,
      },
    }
  })
  return changed ? { ...scene, openings } : scene
}
