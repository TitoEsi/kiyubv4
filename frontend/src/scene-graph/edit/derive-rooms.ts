import type { Point2D, Room, SceneDocument } from '../types'
import { cloneScene, touchScene } from './clone'
import { dist } from './geometry'

interface Node {
  id: string
  p: Point2D
}

function centroid(poly: Point2D[]): Point2D {
  if (!poly.length) return { x: 0, y: 0 }
  const s = poly.reduce((acc, p) => ({ x: acc.x + p.x, y: acc.y + p.y }), { x: 0, y: 0 })
  return { x: s.x / poly.length, y: s.y / poly.length }
}

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

/** Walk planar cycles from wall junctions and remap existing rooms by centroid. */
export function deriveRoomsFromWalls(scene: SceneDocument): SceneDocument {
  const next = cloneScene(scene)
  const nodes = new Map<string, Node>()
  const adj = new Map<string, Array<{ to: string; wallId: string }>>()

  function addNode(id: string, p: Point2D) {
    if (!nodes.has(id)) nodes.set(id, { id, p })
    if (!adj.has(id)) adj.set(id, [])
  }

  for (const wall of next.walls) {
    const a = (wall.metadata?.startNodeId as string) || `${wall.id}-s`
    const b = (wall.metadata?.endNodeId as string) || `${wall.id}-e`
    addNode(a, wall.start)
    addNode(b, wall.end)
    adj.get(a)!.push({ to: b, wallId: wall.id })
    adj.get(b)!.push({ to: a, wallId: wall.id })
  }

  const cycles: Point2D[][] = []
  const seen = new Set<string>()
  for (const start of nodes.keys()) {
    const stack: Array<{ node: string; path: string[]; pts: Point2D[] }> = [
      { node: start, path: [start], pts: [nodes.get(start)!.p] },
    ]
    while (stack.length) {
      const cur = stack.pop()!
      if (cur.path.length > 12) continue
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
        stack.push({
          node: edge.to,
          path: [...cur.path, edge.to],
          pts: [...cur.pts, nodes.get(edge.to)!.p],
        })
      }
    }
  }

  const loops = cycles
    .filter(poly => poly.length >= 3 && area(poly) > 0.5)
    .sort((a, b) => area(a) - area(b))

  const used = new Set<string>()
  for (const poly of loops) {
    const c = centroid(poly)
    let best: Room | undefined
    let bestD = Infinity
    for (const room of next.rooms) {
      if (used.has(room.id)) continue
      const rc = centroid(room.polygon)
      const d = dist(c, rc)
      if (d < bestD) {
        bestD = d
        best = room
      }
    }
    if (best && bestD < 8) {
      const existingArea = best.area || area(best.polygon)
      const newArea = area(poly)
      const weakerAabb = best.polygon.length > 4 && newArea > existingArea * 1.25
      if (!weakerAabb) {
        used.add(best.id)
        const b = bounds(poly)
        best.polygon = poly.map(p => ({ ...p }))
        best.position = { ...b.min }
        best.dimensions = { width: b.max.x - b.min.x, height: b.max.y - b.min.y }
        best.area = newArea
      }
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
