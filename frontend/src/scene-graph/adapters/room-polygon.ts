import type { FootprintPart, Room as FloorPlanRoom } from '../../types/floorplan'
import type { Point2D } from '../types'

/** Vertex snap tolerance in meters. */
const EPS = 0.012

function q(n: number): number {
  return Math.round(n / EPS) * EPS
}

function key(p: Point2D): string {
  return `${q(p.x)},${q(p.y)}`
}

function dist(a: Point2D, b: Point2D): number {
  return Math.hypot(a.x - b.x, a.y - b.y)
}

function rectPolygon(x: number, y: number, width: number, height: number): Point2D[] {
  return [
    { x, y },
    { x: x + width, y },
    { x: x + width, y: y + height },
    { x, y: y + height },
  ]
}

export function polygonFromBoundary(segs: Array<{ x1: number; y1: number; x2: number; y2: number }>): Point2D[] {
  if (!segs.length) return []
  const unused = segs.map(s => ({ a: { x: s.x1, y: s.y1 }, b: { x: s.x2, y: s.y2 } }))
  const pts: Point2D[] = [unused[0].a, unused[0].b]
  unused.splice(0, 1)
  while (unused.length) {
    const last = pts[pts.length - 1]
    const idx = unused.findIndex(e => dist(e.a, last) < EPS || dist(e.b, last) < EPS)
    if (idx < 0) break
    const e = unused.splice(idx, 1)[0]
    const next = dist(e.a, last) < EPS ? e.b : e.a
    if (dist(next, pts[0]) < EPS) break
    pts.push(next)
  }
  return pts.length >= 3 ? pts : []
}

export function polygonFromParts(parts: FootprintPart[]): Point2D[] {
  if (!parts.length) return []
  if (parts.length === 1) return rectPolygon(parts[0].x, parts[0].y, parts[0].width, parts[0].height)

  const counts = new Map<string, { a: Point2D; b: Point2D; n: number }>()
  for (const p of parts) {
    const corners = rectPolygon(p.x, p.y, p.width, p.height)
    for (let i = 0; i < 4; i++) {
      const a = corners[i]
      const b = corners[(i + 1) % 4]
      const undirected = [key(a), key(b)].sort().join('|')
      const cur = counts.get(undirected)
      if (cur) cur.n += 1
      else counts.set(undirected, { a, b, n: 1 })
    }
  }
  const leftover = Array.from(counts.values()).filter(e => e.n % 2 === 1)
  if (!leftover.length) return rectPolygon(parts[0].x, parts[0].y, parts[0].width, parts[0].height)
  return polygonFromBoundary(leftover.map(e => ({ x1: e.a.x, y1: e.a.y, x2: e.b.x, y2: e.b.y })))
}

export function roomPolygonFromFloorPlan(room: FloorPlanRoom): Point2D[] {
  const fp = room.footprint
  if (fp?.boundary?.length) {
    const poly = polygonFromBoundary(fp.boundary)
    if (poly.length >= 3) return poly
  }
  if (fp?.parts?.length) {
    const poly = polygonFromParts(fp.parts)
    if (poly.length >= 3) return poly
  }
  return rectPolygon(room.x, room.y, room.width, room.height)
}

export function polygonArea(poly: Point2D[]): number {
  let a = 0
  for (let i = 0; i < poly.length; i++) {
    const b = poly[(i + 1) % poly.length]
    a += poly[i].x * b.y - b.x * poly[i].y
  }
  return Math.abs(a) / 2
}

export function polygonBounds(poly: Point2D[]): { min: Point2D; max: Point2D } {
  return {
    min: { x: Math.min(...poly.map(p => p.x)), y: Math.min(...poly.map(p => p.y)) },
    max: { x: Math.max(...poly.map(p => p.x)), y: Math.max(...poly.map(p => p.y)) },
  }
}

export function scalePolygon(poly: Point2D[], factor: number): Point2D[] {
  return poly.map(p => ({ x: p.x * factor, y: p.y * factor }))
}
