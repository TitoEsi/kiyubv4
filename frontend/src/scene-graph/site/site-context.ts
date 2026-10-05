/**
 * Render-only site context for the 2D plan: the lot rectangle in plan meters and
 * deterministic landscaping around the building. Nothing here is stored.
 *
 * Plan (0,0) is the solver's buildable-envelope corner, so the lot starts one
 * setback up and left of it unless the footprint does not fit, in which case the
 * lot is centred on the footprint along that axis.
 */
import type { Point2D, SceneDocument } from '../types'
import { wallPointAtT } from '../edit/geometry'
import { openingT } from '../edit/opening-ops'

/** Must match the solver's placeholder envelope setbacks (5 ft on every side). */
export const SITE_SETBACK_M = 1.524

export interface SiteLot {
  width: number
  depth: number
  shape?: string
}

export interface Rect {
  x: number
  y: number
  width: number
  height: number
}

export type VegetationKind = 'tree-lg' | 'tree-md' | 'tree-sm' | 'cluster' | 'shrub'

export interface Vegetation {
  kind: VegetationKind
  x: number
  y: number
  r: number
  variant: number
}

export interface SiteContext {
  lot: Rect | null
  /** True when no brief lot was available and the lot is only a margin around the footprint. */
  inferred: boolean
  vegetation: Vegetation[]
}

const BUILDING_CLEARANCE_M = 0.9
const DOOR_CLEARANCE_M = 1.8
const WINDOW_CLEARANCE_M = 1.0
const CANOPY_GAP_M = 0.4
const MAX_CELLS = 4000
const MAX_VEGETATION = 60
const EPS = 1e-6

const TREE_TIERS: Array<{ kind: VegetationKind; r: number; max: number; prefer: 'edge' | 'building' }> = [
  { kind: 'tree-lg', r: 2.4, max: 6, prefer: 'edge' },
  { kind: 'tree-md', r: 1.6, max: 7, prefer: 'edge' },
  { kind: 'tree-sm', r: 1.0, max: 6, prefer: 'building' },
]
const CLUSTER = { r: 0.55, max: 5 }
const SHRUB = { r: 0.4, spacing: 1.5, offset: 0.9, max: 16 }

type Poly = Point2D[]
type Seg = { a: Point2D; b: Point2D }

function roomPoly(room: SceneDocument['rooms'][number]): Poly {
  if (room.polygon?.length) return room.polygon
  const { x, y } = room.position
  const { width, height } = room.dimensions
  return [{ x, y }, { x: x + width, y }, { x: x + width, y: y + height }, { x, y: y + height }]
}

function insidePoly(p: Point2D, pts: Poly): boolean {
  let inside = false
  for (let i = 0, j = pts.length - 1; i < pts.length; j = i++) {
    const xi = pts[i].x, yi = pts[i].y, xj = pts[j].x, yj = pts[j].y
    if ((yi > p.y) !== (yj > p.y) && p.x < ((xj - xi) * (p.y - yi)) / (yj - yi + 1e-12) + xi) inside = !inside
  }
  return inside
}

function segDist(p: Point2D, s: Seg): number {
  const dx = s.b.x - s.a.x, dy = s.b.y - s.a.y
  const len2 = dx * dx + dy * dy
  const t = len2 > 0 ? Math.max(0, Math.min(1, ((p.x - s.a.x) * dx + (p.y - s.a.y) * dy) / len2)) : 0
  return Math.hypot(p.x - (s.a.x + t * dx), p.y - (s.a.y + t * dy))
}

function variantOf(x: number, y: number): number {
  const h = Math.imul(Math.round(x * 100), 73856093) ^ Math.imul(Math.round(y * 100), 19349663)
  return (h >>> 0) % 1000
}

function placeAxis(min: number, max: number, length: number): number {
  const fits = min >= -EPS && max <= length - 2 * SITE_SETBACK_M + EPS
  return fits ? -SITE_SETBACK_M : (min + max) / 2 - length / 2
}

export function lotRect(scene: SceneDocument, lot?: SiteLot | null): { lot: Rect | null; inferred: boolean } {
  const b = footprintBounds(scene)
  const valid = lot && Number.isFinite(lot.width) && Number.isFinite(lot.depth) && lot.width > 0 && lot.depth > 0
  if (valid) {
    let w = lot.width, d = lot.depth
    if (lot.shape === 'square') w = d = Math.min(w, d)
    if (!b) return { lot: { x: -SITE_SETBACK_M, y: -SITE_SETBACK_M, width: w, height: d }, inferred: false }
    return {
      lot: { x: placeAxis(b.minX, b.maxX, w), y: placeAxis(b.minY, b.maxY, d), width: w, height: d },
      inferred: false,
    }
  }
  if (!b) return { lot: null, inferred: true }
  return {
    lot: {
      x: b.minX - SITE_SETBACK_M,
      y: b.minY - SITE_SETBACK_M,
      width: b.maxX - b.minX + 2 * SITE_SETBACK_M,
      height: b.maxY - b.minY + 2 * SITE_SETBACK_M,
    },
    inferred: true,
  }
}

function footprintBounds(scene: SceneDocument) {
  let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity
  const take = (p: Point2D) => {
    minX = Math.min(minX, p.x); minY = Math.min(minY, p.y)
    maxX = Math.max(maxX, p.x); maxY = Math.max(maxY, p.y)
  }
  for (const room of scene.rooms) roomPoly(room).forEach(take)
  for (const wall of scene.walls) { take(wall.start); take(wall.end) }
  return Number.isFinite(minX) ? { minX, minY, maxX, maxY } : null
}

export function buildSiteContext(scene: SceneDocument, lot?: SiteLot | null): SiteContext {
  const placed = lotRect(scene, lot)
  const base: SiteContext = { ...placed, vegetation: [] }
  if (!placed.lot) return base
  try {
    return { ...base, vegetation: landscape(scene, placed.lot) }
  } catch {
    return base
  }
}

function landscape(scene: SceneDocument, lot: Rect): Vegetation[] {
  const polys = scene.rooms.map(roomPoly).filter(p => p.length >= 3)
  const edges: Seg[] = []
  for (const pts of polys) {
    for (let i = 0; i < pts.length; i++) edges.push({ a: pts[i], b: pts[(i + 1) % pts.length] })
  }
  for (const w of scene.walls) edges.push({ a: w.start, b: w.end })
  if (!edges.length) return []

  const doors: Point2D[] = []
  const windows: Point2D[] = []
  const wallById = new Map(scene.walls.map(w => [w.id, w]))
  for (const o of scene.openings) {
    const host = wallById.get(o.wallId)
    ;(o.type === 'window' ? windows : doors).push(host ? wallPointAtT(host, openingT(o, host)) : o.position)
  }

  const inBuilding = (p: Point2D) => polys.some(pts => insidePoly(p, pts))
  const footDist = (p: Point2D) => (inBuilding(p) ? 0 : Math.min(...edges.map(s => segDist(p, s))))
  const nearest = (p: Point2D, pts: Point2D[]) => pts.reduce((m, q) => Math.min(m, Math.hypot(p.x - q.x, p.y - q.y)), Infinity)
  const edgeDist = (p: Point2D) => Math.min(p.x - lot.x, lot.x + lot.width - p.x, p.y - lot.y, lot.y + lot.height - p.y)

  const cell = Math.max(0.5, Math.sqrt((lot.width * lot.height) / MAX_CELLS))
  type Cell = { x: number; y: number; foot: number; door: number; win: number; edge: number }
  const cells: Cell[] = []
  for (let y = lot.y + cell / 2; y < lot.y + lot.height; y += cell) {
    for (let x = lot.x + cell / 2; x < lot.x + lot.width; x += cell) {
      const p = { x, y }
      const foot = footDist(p)
      if (foot < BUILDING_CLEARANCE_M) continue
      const door = nearest(p, doors)
      const win = nearest(p, windows)
      if (door < DOOR_CLEARANCE_M || win < WINDOW_CLEARANCE_M) continue
      cells.push({ x, y, foot, door, win, edge: edgeDist(p) })
    }
  }

  const out: Vegetation[] = []
  const clear = (x: number, y: number, r: number) =>
    out.every(v => Math.hypot(v.x - x, v.y - y) >= v.r + r + CANOPY_GAP_M)
  const add = (kind: VegetationKind, x: number, y: number, r: number) =>
    out.push({ kind, x, y, r, variant: variantOf(x, y) })

  for (const tier of TREE_TIERS) {
    const order = [...cells].sort((a, b) =>
      (tier.prefer === 'edge' ? a.edge - b.edge : a.foot - b.foot) || a.y - b.y || a.x - b.x)
    let count = 0
    for (const c of order) {
      if (count >= tier.max || out.length >= MAX_VEGETATION) break
      if (c.foot < tier.r + BUILDING_CLEARANCE_M || c.edge < tier.r * 0.5) continue
      if (c.door < tier.r + DOOR_CLEARANCE_M * 0.7 || c.win < tier.r + WINDOW_CLEARANCE_M * 0.6) continue
      if (!clear(c.x, c.y, tier.r)) continue
      add(tier.kind, c.x, c.y, tier.r)
      count++
    }
  }

  const openings = [...doors, ...windows]
  let shrubs = 0
  for (const wall of scene.walls) {
    if (wall.type !== 'exterior' || shrubs >= SHRUB.max) continue
    const len = Math.hypot(wall.end.x - wall.start.x, wall.end.y - wall.start.y)
    if (len < SHRUB.spacing) continue
    const ux = (wall.end.x - wall.start.x) / len, uy = (wall.end.y - wall.start.y) / len
    const mid = { x: (wall.start.x + wall.end.x) / 2, y: (wall.start.y + wall.end.y) / 2 }
    const off = SHRUB.offset + (wall.thickness || 0) / 2
    const side = inBuilding({ x: mid.x - uy * off, y: mid.y + ux * off }) ? -1 : 1
    const nx = -uy * side, ny = ux * side
    for (let t = SHRUB.spacing / 2; t < len && shrubs < SHRUB.max && out.length < MAX_VEGETATION; t += SHRUB.spacing) {
      const wp = { x: wall.start.x + ux * t, y: wall.start.y + uy * t }
      if (nearest(wp, openings) < 1.2) continue
      const p = { x: wp.x + nx * off, y: wp.y + ny * off }
      if (edgeDist(p) < SHRUB.r || footDist(p) < SHRUB.offset - 0.05) continue
      if (!clear(p.x, p.y, SHRUB.r)) continue
      add('shrub', p.x, p.y, SHRUB.r)
      shrubs++
    }
  }

  const corners = [...cells].sort((a, b) => a.edge - b.edge || a.foot - b.foot || a.y - b.y || a.x - b.x)
  let clusters = 0
  for (const c of corners) {
    if (clusters >= CLUSTER.max || out.length >= MAX_VEGETATION) break
    if (c.edge < CLUSTER.r || !clear(c.x, c.y, CLUSTER.r)) continue
    add('cluster', c.x, c.y, CLUSTER.r)
    clusters++
  }
  return out
}
