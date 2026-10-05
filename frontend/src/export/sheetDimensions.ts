import { sceneFootprint } from '../components/room-rows'
import type { SceneDocument, Wall } from '../scene-graph/types'

export interface SheetDimension {
  role: 'overall' | 'segment'
  a: { x: number; y: number }
  b: { x: number; y: number }
  /** Unit normal pointing away from the building, in plan space (y down). */
  outward: { x: number; y: number }
  lengthM: number
}

const EPS = 0.05
const MIN_RUN = 0.15

type Span = { fixed: number; a: number; b: number }

function aligned(wall: Wall): 'h' | 'v' | null {
  const dx = Math.abs(wall.end.x - wall.start.x)
  const dy = Math.abs(wall.end.y - wall.start.y)
  if (dx < EPS && dy < EPS) return null
  if (dy <= EPS) return 'h'
  if (dx <= EPS) return 'v'
  return null
}

function spansOf(walls: Wall[], axis: 'h' | 'v'): Span[] {
  return walls.filter(wall => aligned(wall) === axis).map(wall => {
    if (axis === 'h') {
      return {
        fixed: (wall.start.y + wall.end.y) / 2,
        a: Math.min(wall.start.x, wall.end.x),
        b: Math.max(wall.start.x, wall.end.x),
      }
    }
    return {
      fixed: (wall.start.x + wall.end.x) / 2,
      a: Math.min(wall.start.y, wall.end.y),
      b: Math.max(wall.start.y, wall.end.y),
    }
  })
}

function mergeRuns(spans: Span[]): Span[] {
  const sorted = [...spans].sort((p, q) => p.fixed - q.fixed || p.a - q.a)
  const groups: Span[][] = []
  for (const span of sorted) {
    const group = groups.find(entry => Math.abs(entry[0].fixed - span.fixed) <= EPS)
    if (group) group.push(span)
    else groups.push([span])
  }
  const runs: Span[] = []
  for (const group of groups) {
    const fixed = group.reduce((sum, span) => sum + span.fixed, 0) / group.length
    const intervals = group
      .map(span => [Math.min(span.a, span.b), Math.max(span.a, span.b)] as [number, number])
      .sort((p, q) => p[0] - q[0])
    const merged: Array<[number, number]> = []
    for (const [start, end] of intervals) {
      const last = merged[merged.length - 1]
      if (last && start <= last[1] + EPS) last[1] = Math.max(last[1], end)
      else merged.push([start, end])
    }
    for (const [start, end] of merged) {
      if (end - start >= MIN_RUN) runs.push({ fixed, a: start, b: end })
    }
  }
  return runs
}

/**
 * Overall building extents plus merged axis-aligned exterior runs.
 * Interior walls and angled exterior walls are not dimensioned.
 */
export function sheetDimensions(scene: SceneDocument): SheetDimension[] {
  const box = sceneFootprint(scene)
  if (box.width < MIN_RUN || box.depth < MIN_RUN) return []
  const maxX = box.minX + box.width
  const maxY = box.minY + box.depth
  const cx = box.minX + box.width / 2
  const cy = box.minY + box.depth / 2
  const exterior = scene.walls.filter(wall => wall.type === 'exterior')
  const dims: SheetDimension[] = [
    {
      role: 'overall',
      a: { x: box.minX, y: maxY },
      b: { x: maxX, y: maxY },
      outward: { x: 0, y: 1 },
      lengthM: box.width,
    },
    {
      role: 'overall',
      a: { x: maxX, y: box.minY },
      b: { x: maxX, y: maxY },
      outward: { x: 1, y: 0 },
      lengthM: box.depth,
    },
  ]
  for (const run of mergeRuns(spansOf(exterior, 'h'))) {
    dims.push({
      role: 'segment',
      a: { x: run.a, y: run.fixed },
      b: { x: run.b, y: run.fixed },
      outward: { x: 0, y: run.fixed >= cy ? 1 : -1 },
      lengthM: run.b - run.a,
    })
  }
  for (const run of mergeRuns(spansOf(exterior, 'v'))) {
    dims.push({
      role: 'segment',
      a: { x: run.fixed, y: run.a },
      b: { x: run.fixed, y: run.b },
      outward: { x: run.fixed >= cx ? 1 : -1, y: 0 },
      lengthM: run.b - run.a,
    })
  }
  return dims
}
