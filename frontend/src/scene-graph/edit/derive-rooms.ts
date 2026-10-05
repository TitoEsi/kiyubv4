import type { Point2D, SceneDocument, Wall } from '../types'
import { cloneScene, touchScene } from './clone'

interface Node {
  id: string
  p: Point2D
}

type Seg = { a: Point2D; b: Point2D; reach: number }

const MOVE_EPS = 1e-6
const MAX_CYCLE_NODES = 12
const MIN_AREA_RATIO = 0.4
const MAX_AREA_RATIO = 1.6
const REGION_PAD_M = 0.5

function area(poly: Point2D[]): number {
  let a = 0
  for (let i = 0; i < poly.length; i++) {
    const b = poly[(i + 1) % poly.length]
    a += poly[i].x * b.y - b.x * poly[i].y
  }
  return Math.abs(a) / 2
}

function bounds(poly: Point2D[]): { min: Point2D; max: Point2D } {
  const xs = poly.map(p => p.x)
  const ys = poly.map(p => p.y)
  return {
    min: { x: Math.min(...xs), y: Math.min(...ys) },
    max: { x: Math.max(...xs), y: Math.max(...ys) },
  }
}

function inside(poly: Point2D[], p: Point2D): boolean {
  let hit = false
  for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
    const a = poly[i], b = poly[j]
    if ((a.y > p.y) !== (b.y > p.y) && p.x < ((b.x - a.x) * (p.y - a.y)) / (b.y - a.y + 1e-12) + a.x) hit = !hit
  }
  return hit
}

function pointSegDist(p: Point2D, a: Point2D, b: Point2D): number {
  const dx = b.x - a.x, dy = b.y - a.y
  const len2 = dx * dx + dy * dy
  const t = len2 > 0 ? Math.max(0, Math.min(1, ((p.x - a.x) * dx + (p.y - a.y) * dy) / len2)) : 0
  return Math.hypot(p.x - (a.x + t * dx), p.y - (a.y + t * dy))
}

function segsCross(a: Point2D, b: Point2D, c: Point2D, d: Point2D): boolean {
  const o = (p: Point2D, q: Point2D, r: Point2D) => (q.x - p.x) * (r.y - p.y) - (q.y - p.y) * (r.x - p.x)
  const d1 = o(c, d, a), d2 = o(c, d, b), d3 = o(a, b, c), d4 = o(a, b, d)
  return ((d1 > 0) !== (d2 > 0)) && ((d3 > 0) !== (d4 > 0))
}

function segPolyDist(s: Seg, poly: Point2D[]): number {
  if (inside(poly, s.a) || inside(poly, s.b)) return 0
  let best = Infinity
  for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
    const c = poly[j], d = poly[i]
    if (segsCross(s.a, s.b, c, d)) return 0
    best = Math.min(best, pointSegDist(s.a, c, d), pointSegDist(s.b, c, d), pointSegDist(c, s.a, s.b), pointSegDist(d, s.a, s.b))
  }
  return best
}

/** Interior point of a room: area centroid, else the sampled point farthest from the outline. */
function anchorOf(poly: Point2D[]): Point2D {
  let a = 0, cx = 0, cy = 0
  for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
    const cross = poly[j].x * poly[i].y - poly[i].x * poly[j].y
    a += cross
    cx += (poly[j].x + poly[i].x) * cross
    cy += (poly[j].y + poly[i].y) * cross
  }
  if (Math.abs(a) > 1e-9) {
    const c = { x: cx / (3 * a), y: cy / (3 * a) }
    if (inside(poly, c)) return c
  }
  const b = bounds(poly)
  const N = 16
  let best = poly[0]
  let bestD = -1
  for (let i = 0; i < N; i++) {
    for (let j = 0; j < N; j++) {
      const p = { x: b.min.x + ((i + 0.5) / N) * (b.max.x - b.min.x), y: b.min.y + ((j + 0.5) / N) * (b.max.y - b.min.y) }
      if (!inside(poly, p)) continue
      let d = Infinity
      for (let k = 0, m = poly.length - 1; k < poly.length; m = k++) d = Math.min(d, pointSegDist(p, poly[m], poly[k]))
      if (d > bestD) { bestD = d; best = p }
    }
  }
  return best
}

function moved(a: Wall, b: Wall): boolean {
  return Math.abs(a.start.x - b.start.x) > MOVE_EPS || Math.abs(a.start.y - b.start.y) > MOVE_EPS
    || Math.abs(a.end.x - b.end.x) > MOVE_EPS || Math.abs(a.end.y - b.end.y) > MOVE_EPS
}

/** Old and new positions of walls that were added, removed or moved between `prev` and `next`. */
function changedSegments(next: SceneDocument, prev?: SceneDocument): Seg[] {
  const seg = (w: Wall): Seg => ({ a: w.start, b: w.end, reach: Math.max(w.thickness || 0, 0.15) })
  if (!prev) return next.walls.map(seg)
  const before = new Map(prev.walls.map(w => [w.id, w]))
  const after = new Map(next.walls.map(w => [w.id, w]))
  const out: Seg[] = []
  for (const w of next.walls) {
    const old = before.get(w.id)
    if (!old) out.push(seg(w))
    else if (moved(old, w)) out.push(seg(old), seg(w))
  }
  for (const w of prev.walls) if (!after.has(w.id)) out.push(seg(w))
  return out
}

/** Simple wall-graph cycles that start inside `region`. */
function cyclesIn(walls: Wall[], region: { min: Point2D; max: Point2D }): Point2D[][] {
  const nodes = new Map<string, Node>()
  const adj = new Map<string, Array<{ to: string }>>()
  const within = (p: Point2D) => p.x >= region.min.x && p.x <= region.max.x && p.y >= region.min.y && p.y <= region.max.y
  function addNode(id: string, p: Point2D) {
    if (!nodes.has(id)) nodes.set(id, { id, p })
    if (!adj.has(id)) adj.set(id, [])
  }
  for (const wall of walls) {
    if (!within(wall.start) && !within(wall.end)) continue
    const a = (wall.metadata?.startNodeId as string) || `${wall.id}-s`
    const b = (wall.metadata?.endNodeId as string) || `${wall.id}-e`
    addNode(a, wall.start)
    addNode(b, wall.end)
    adj.get(a)!.push({ to: b })
    adj.get(b)!.push({ to: a })
  }

  const cycles: Point2D[][] = []
  const seen = new Set<string>()
  for (const start of nodes.keys()) {
    if (!within(nodes.get(start)!.p)) continue
    const stack: Array<{ node: string; path: string[]; pts: Point2D[] }> = [
      { node: start, path: [start], pts: [nodes.get(start)!.p] },
    ]
    while (stack.length) {
      const cur = stack.pop()!
      if (cur.path.length > MAX_CYCLE_NODES) continue
      for (const edge of adj.get(cur.node) || []) {
        if (cur.path.length >= 3 && edge.to === start) {
          const key = [...cur.path].sort().join('|')
          if (!seen.has(key)) {
            seen.add(key)
            cycles.push(cur.pts)
          }
          continue
        }
        if (cur.path.includes(edge.to)) continue
        stack.push({ node: edge.to, path: [...cur.path, edge.to], pts: [...cur.pts, nodes.get(edge.to)!.p] })
      }
    }
  }
  return cycles
}

/**
 * Re-fit room polygons to the wall loops after a geometry edit. Only rooms touched by a wall that
 * changed since `prev` are considered, and a room only takes a loop that contains its interior point
 * and has a plausible area; otherwise its geometry is left as is.
 */
export function deriveRoomsFromWalls(scene: SceneDocument, prev?: SceneDocument): SceneDocument {
  const next = cloneScene(scene)
  const changed = changedSegments(next, prev)

  const affected = changed.length
    ? next.rooms.filter(room => room.polygon?.length >= 3 && changed.some(s => segPolyDist(s, room.polygon) <= s.reach))
    : []

  if (affected.length) {
    const pts = [...affected.flatMap(r => r.polygon), ...changed.flatMap(s => [s.a, s.b])]
    const b = bounds(pts)
    const region = {
      min: { x: b.min.x - REGION_PAD_M, y: b.min.y - REGION_PAD_M },
      max: { x: b.max.x + REGION_PAD_M, y: b.max.y + REGION_PAD_M },
    }
    const loops = cyclesIn(next.walls, region)
      .map(poly => ({ poly, area: area(poly) }))
      .filter(l => l.poly.length >= 3 && l.area > 0.5)
      .sort((x, y) => x.area - y.area)

    const used = new Set<number>()
    const ordered = [...affected].sort((x, y) => area(x.polygon) - area(y.polygon))
    for (const room of ordered) {
      const current = room.area || area(room.polygon)
      const anchor = anchorOf(room.polygon)
      const idx = loops.findIndex((l, i) =>
        !used.has(i)
        && l.area >= current * MIN_AREA_RATIO
        && l.area <= current * MAX_AREA_RATIO
        && inside(l.poly, anchor))
      if (idx < 0) continue
      used.add(idx)
      const poly = loops[idx].poly
      const bb = bounds(poly)
      room.polygon = poly.map(p => ({ ...p }))
      room.position = { ...bb.min }
      room.dimensions = { width: bb.max.x - bb.min.x, height: bb.max.y - bb.min.y }
      room.area = loops[idx].area
    }
  }

  const byRoom = new Map<string, string[]>()
  for (const wall of next.walls) {
    for (const rid of wall.roomIds) {
      const list = byRoom.get(rid) || []
      list.push(wall.id)
      byRoom.set(rid, list)
    }
  }
  for (const room of next.rooms) {
    room.wallIds = byRoom.get(room.id) || room.wallIds
  }
  return touchScene(next)
}
