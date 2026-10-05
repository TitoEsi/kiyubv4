import type { Point2D, Room, SceneDocument, Wall } from '../types'
import { cloneScene, touchScene } from './clone'
import { assignJunctions } from './bootstrap-walls'
import { syncOpeningsToWalls } from './opening-ops'
import { NODE_EPS } from './geometry'

export const ROOM_MIN_M = 1.8288
export const ROOM_MAX_M = 18.288

export type RoomAxis = 'width' | 'depth'

type Coord = 'x' | 'y'

function roomPoly(room: Room): Point2D[] {
  if (room.polygon?.length >= 3) return room.polygon
  const { x, y } = room.position
  const { width, height } = room.dimensions
  return [{ x, y }, { x: x + width, y }, { x: x + width, y: y + height }, { x, y: y + height }]
}

function extent(pts: Point2D[], c: Coord): { min: number; max: number } {
  const v = pts.map(p => p[c])
  return { min: Math.min(...v), max: Math.max(...v) }
}

function polyArea(poly: Point2D[]): number {
  let a = 0
  for (let i = 0; i < poly.length; i++) {
    const b = poly[(i + 1) % poly.length]
    a += poly[i].x * b.y - b.x * poly[i].y
  }
  return Math.abs(a) / 2
}

function span(w: Wall, c: Coord): [number, number] {
  return [Math.min(w.start[c], w.end[c]), Math.max(w.start[c], w.end[c])]
}

/**
 * Sets a room's width (x) or depth (y) by moving its right / bottom edge, as if that wall were dragged:
 * the whole straight run of walls on that line moves, attached walls stretch, and rooms sharing the
 * line resize with it. Returns `scene` unchanged when the edit is impossible or would crush a room.
 */
export function resizeRoom(scene: SceneDocument, roomId: string, axis: RoomAxis, sizeM: number): SceneDocument {
  const room = scene.rooms.find(r => r.id === roomId)
  if (!room || !Number.isFinite(sizeM) || sizeM < ROOM_MIN_M - 1e-9 || sizeM > ROOM_MAX_M + 1e-9) return scene
  const k: Coord = axis === 'width' ? 'x' : 'y'
  const o: Coord = axis === 'width' ? 'y' : 'x'
  const pts = roomPoly(room)
  const along = extent(pts, k)
  const across = extent(pts, o)
  const line = along.max
  const delta = sizeM - (along.max - along.min)
  if (Math.abs(delta) < 1e-9) return scene

  const onLine = (p: Point2D) => Math.abs(p[k] - line) <= NODE_EPS
  const candidates = scene.walls.filter(w => onLine(w.start) && onLine(w.end))
  const run = candidates.filter(w => {
    const [a, b] = span(w, o)
    return Math.min(b, across.max) - Math.max(a, across.min) > NODE_EPS
  })
  if (!run.length) return scene

  let lo = Math.min(...run.map(w => span(w, o)[0]))
  let hi = Math.max(...run.map(w => span(w, o)[1]))
  for (let grew = true; grew;) {
    grew = false
    for (const w of candidates) {
      if (run.includes(w)) continue
      const [a, b] = span(w, o)
      if (a <= hi + NODE_EPS && b >= lo - NODE_EPS) {
        run.push(w)
        lo = Math.min(lo, a)
        hi = Math.max(hi, b)
        grew = true
      }
    }
  }

  const moves = (p: Point2D) => onLine(p) && p[o] >= lo - NODE_EPS && p[o] <= hi + NODE_EPS
  const shift = (p: Point2D): Point2D => (moves(p) ? { ...p, [k]: p[k] + delta } : { ...p })

  const next = cloneScene(scene)
  for (const w of next.walls) {
    w.start = shift(w.start)
    w.end = shift(w.end)
  }

  for (const r of next.rooms) {
    const before = roomPoly(r)
    const moved = before.filter(moves)
    if (!moved.length) continue
    const fixed = before.filter(p => !moves(p))
    if (fixed.length) {
      const old = extent(before, k)
      const side = Math.sign(line - fixed.reduce((s, p) => s + p[k], 0) / fixed.length)
      const ref = side > 0 ? extent(fixed, k).min : extent(fixed, k).max
      const newSize = side * (line + delta - ref)
      if (newSize < Math.min(ROOM_MIN_M, old.max - old.min) - 1e-6) return scene
    }
    const poly = before.map(shift)
    const area = polyArea(poly)
    if (area < 1e-6) return scene
    const ex = extent(poly, 'x')
    const ey = extent(poly, 'y')
    r.polygon = poly
    r.position = { x: ex.min, y: ey.min }
    r.dimensions = { width: ex.max - ex.min, height: ey.max - ey.min }
    r.area = area
  }

  return assignJunctions(syncOpeningsToWalls(touchScene(next)))
}
