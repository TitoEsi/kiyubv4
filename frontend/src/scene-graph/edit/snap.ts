import type { Point2D, SceneDocument, Wall } from '../types'
import { NODE_EPS, dist, nearestOnWall, nearlyEqual, wallDir } from './geometry'

export interface SnapOptions {
  grid: number
  enabled: boolean
  walls: Wall[]
}

export interface SnapResult {
  point: Point2D
  guides: Array<{ x1: number; y1: number; x2: number; y2: number }>
}

export function snapPoint(p: Point2D, opts: SnapOptions): SnapResult {
  if (!opts.enabled) return { point: p, guides: [] }
  let point = { ...p }
  const guides: SnapResult['guides'] = []
  const g = Math.max(opts.grid, 0.01)
  point = {
    x: Math.round(point.x / g) * g,
    y: Math.round(point.y / g) * g,
  }

  let best: Point2D | null = null
  let bestD = NODE_EPS * 1.5
  for (const wall of opts.walls) {
    for (const end of [wall.start, wall.end]) {
      const d = dist(point, end)
      if (d < bestD) {
        bestD = d
        best = end
      }
    }
  }
  if (best) {
    point = { ...best }
    return { point, guides }
  }

  for (const wall of opts.walls) {
    const on = nearestOnWall(wall, point)
    if (dist(on, point) < NODE_EPS * 1.5) {
      point = on
      const dir = wallDir(wall)
      if (nearlyEqual(Math.abs(dir.x), 0) || nearlyEqual(Math.abs(dir.y), 0)) {
        guides.push({
          x1: wall.start.x, y1: wall.start.y, x2: wall.end.x, y2: wall.end.y,
        })
      }
      break
    }
  }

  for (const wall of opts.walls) {
    if (Math.abs(point.x - wall.start.x) < NODE_EPS) {
      point.x = wall.start.x
      guides.push({ x1: point.x, y1: Math.min(point.y, wall.start.y) - 2, x2: point.x, y2: Math.max(point.y, wall.end.y) + 2 })
    }
    if (Math.abs(point.y - wall.start.y) < NODE_EPS) {
      point.y = wall.start.y
      guides.push({ x1: Math.min(point.x, wall.start.x) - 2, y1: point.y, x2: Math.max(point.x, wall.end.x) + 2, y2: point.y })
    }
  }
  return { point, guides }
}

export function sceneWalls(scene: SceneDocument): Wall[] {
  return scene.walls
}
