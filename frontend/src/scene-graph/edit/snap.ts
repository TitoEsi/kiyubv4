import type { Point2D, SceneDocument, Wall } from '../types'
import { NODE_EPS, dist, nearestOnWall, segmentIntersection } from './geometry'

/** Snap reach in screen pixels; converted to plan meters at the current scale. */
export const SNAP_PICK_PX = 10

export interface SnapOptions {
  grid: number
  enabled: boolean
  walls: Wall[]
  /** Snap reach in plan meters; see `snapToleranceFor`. */
  tolerance?: number
  /** Walls ignored as snap targets, e.g. those attached to a dragged endpoint. */
  excludeWallIds?: string[]
}

export type SnapKind = 'vertex' | 'intersection' | 'segment' | 'align' | 'grid' | 'none'

export interface SnapResult {
  point: Point2D
  kind: SnapKind
  guides: Array<{ x1: number; y1: number; x2: number; y2: number }>
}

/** Snap reach in meters for a plan drawn at `S` pixels per meter. */
export function snapToleranceFor(S: number): number {
  return Math.max(NODE_EPS * 1.5, SNAP_PICK_PX / Math.max(S, 1e-6))
}

function vertices(walls: Wall[]): Point2D[] {
  const out: Point2D[] = []
  for (const wall of walls) {
    for (const p of [wall.start, wall.end]) {
      if (!out.some(q => dist(p, q) < 1e-9)) out.push(p)
    }
  }
  return out
}

function crossings(walls: Wall[]): Point2D[] {
  const out: Point2D[] = []
  for (let i = 0; i < walls.length; i++) {
    for (let j = i + 1; j < walls.length; j++) {
      const hit = segmentIntersection(walls[i].start, walls[i].end, walls[j].start, walls[j].end)
      if (hit && hit.t >= 0 && hit.t <= 1 && hit.u >= 0 && hit.u <= 1) out.push(hit.point)
    }
  }
  return out
}

function nearest(points: Point2D[], p: Point2D, tol: number): Point2D | null {
  let best: Point2D | null = null
  let bestD = tol
  for (const q of points) {
    const d = dist(p, q)
    if (d <= bestD) {
      bestD = d
      best = q
    }
  }
  return best
}

/**
 * Snap a plan point measured from the raw cursor. The first match wins:
 * wall vertex, wall crossing, wall segment, vertex alignment, then grid.
 */
export function snapPoint(p: Point2D, opts: SnapOptions): SnapResult {
  if (!opts.enabled) return { point: p, kind: 'none', guides: [] }
  const tol = opts.tolerance ?? NODE_EPS * 1.5
  const exclude = new Set(opts.excludeWallIds ?? [])
  const walls = opts.walls.filter(w => !exclude.has(w.id))
  const verts = vertices(walls)

  const vertex = nearest(verts, p, tol)
  if (vertex) return { point: { ...vertex }, kind: 'vertex', guides: [] }

  const crossing = nearest(crossings(walls), p, tol)
  if (crossing) return { point: { ...crossing }, kind: 'intersection', guides: [] }

  let host: Wall | null = null
  let onHost: Point2D | null = null
  let hostD = tol
  for (const wall of walls) {
    const on = nearestOnWall(wall, p)
    const d = dist(on, p)
    if (d <= hostD) {
      hostD = d
      host = wall
      onHost = on
    }
  }
  if (host && onHost) {
    return {
      point: onHost,
      kind: 'segment',
      guides: [{ x1: host.start.x, y1: host.start.y, x2: host.end.x, y2: host.end.y }],
    }
  }

  const guides: SnapResult['guides'] = []
  let ax: Point2D | null = null
  let ay: Point2D | null = null
  for (const v of verts) {
    if (Math.abs(v.x - p.x) <= tol && (!ax || Math.abs(v.x - p.x) < Math.abs(ax.x - p.x))) ax = v
    if (Math.abs(v.y - p.y) <= tol && (!ay || Math.abs(v.y - p.y) < Math.abs(ay.y - p.y))) ay = v
  }
  const g = Math.max(opts.grid, 0.01)
  const point = {
    x: ax ? ax.x : Math.round(p.x / g) * g,
    y: ay ? ay.y : Math.round(p.y / g) * g,
  }
  if (ax) guides.push({ x1: ax.x, y1: ax.y, x2: point.x, y2: point.y })
  if (ay) guides.push({ x1: ay.x, y1: ay.y, x2: point.x, y2: point.y })
  return { point, kind: ax || ay ? 'align' : 'grid', guides }
}

export function sceneWalls(scene: SceneDocument): Wall[] {
  return scene.walls
}
