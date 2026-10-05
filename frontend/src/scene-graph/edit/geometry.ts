import type { Point2D, Wall } from '../types'

export const NODE_EPS = 0.05

export function dist(a: Point2D, b: Point2D): number {
  return Math.hypot(a.x - b.x, a.y - b.y)
}

export function add(a: Point2D, b: Point2D): Point2D {
  return { x: a.x + b.x, y: a.y + b.y }
}

export function sub(a: Point2D, b: Point2D): Point2D {
  return { x: a.x - b.x, y: a.y - b.y }
}

export function scale(a: Point2D, s: number): Point2D {
  return { x: a.x * s, y: a.y * s }
}

export function wallVec(wall: Wall): Point2D {
  return sub(wall.end, wall.start)
}

export function wallLength(wall: Wall): number {
  return dist(wall.start, wall.end)
}

export function wallDir(wall: Wall): Point2D {
  const len = wallLength(wall)
  if (len < 1e-9) return { x: 1, y: 0 }
  return scale(wallVec(wall), 1 / len)
}

export function wallPointAtT(wall: Wall, t: number): Point2D {
  return {
    x: wall.start.x + (wall.end.x - wall.start.x) * t,
    y: wall.start.y + (wall.end.y - wall.start.y) * t,
  }
}

export function projectT(wall: Wall, p: Point2D): number {
  const len2 = wallLength(wall) ** 2
  if (len2 < 1e-12) return 0
  const t = ((p.x - wall.start.x) * (wall.end.x - wall.start.x)
    + (p.y - wall.start.y) * (wall.end.y - wall.start.y)) / len2
  return Math.max(0, Math.min(1, t))
}

export function nearestOnWall(wall: Wall, p: Point2D): Point2D {
  return wallPointAtT(wall, projectT(wall, p))
}

export function quantize(p: Point2D, eps = NODE_EPS): string {
  const q = (n: number) => Math.round(n / eps) * eps
  return `${q(p.x).toFixed(4)},${q(p.y).toFixed(4)}`
}

export function nearlyEqual(a: number, b: number, eps = NODE_EPS): boolean {
  return Math.abs(a - b) <= eps
}

export function collinear(a: Wall, b: Wall, eps = 0.02): boolean {
  const da = wallDir(a)
  const db = wallDir(b)
  const parallel = Math.abs(da.x * db.y - da.y * db.x) <= eps
  if (!parallel) return false
  const toB = sub(b.start, a.start)
  return Math.abs(da.x * toB.y - da.y * toB.x) <= NODE_EPS
}

/** Intersection of segments ab and cd with their parameters, or null when parallel. */
export function segmentIntersection(
  a: Point2D, b: Point2D, c: Point2D, d: Point2D,
): { point: Point2D; t: number; u: number } | null {
  const r = sub(b, a), s = sub(d, c)
  const denom = r.x * s.y - r.y * s.x
  if (Math.abs(denom) < 1e-12) return null
  const ac = sub(c, a)
  const t = (ac.x * s.y - ac.y * s.x) / denom
  const u = (ac.x * r.y - ac.y * r.x) / denom
  return { point: add(a, scale(r, t)), t, u }
}

export function nodeIdOf(wall: Wall, which: 'start' | 'end'): string | undefined {
  const raw = wall.metadata?.[which === 'start' ? 'startNodeId' : 'endNodeId']
  return typeof raw === 'string' ? raw : undefined
}
