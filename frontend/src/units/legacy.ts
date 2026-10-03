/**
 * Compatibility layer for data written before meters became canonical.
 *
 * Legacy FloorPlan JSON (solver/MOE output and older saves) has no `units` key and is in
 * feet. Legacy comment pins have no `coord_units` and are plan-feet coordinates.
 * Everything that enters the app passes through here so the rest of the code only sees meters.
 */
import type { FloorPlan } from '../types/floorplan'
import { legacyFeetToMeters as ft, legacySquareFeetToSquareMeters } from './measurement'

export const METRIC = 'metric' as const

type Pt = { x: number; y: number }
type Seg = { x1: number; y1: number; x2: number; y2: number }

const pt = <T extends Pt>(p: T): T => ({ ...p, x: ft(p.x), y: ft(p.y) })
const seg = <T extends Seg>(s: T): T => ({ ...s, x1: ft(s.x1), y1: ft(s.y1), x2: ft(s.x2), y2: ft(s.y2) })
const opt = (v: number | undefined) => (v == null ? v : ft(v))

export function isMetricPlan(plan: { units?: string } | null | undefined): boolean {
  return plan?.units === METRIC
}

/** Returns a meters FloorPlan. Idempotent: metric plans are returned unchanged. */
export function normalizeFloorPlan<T extends FloorPlan | null | undefined>(plan: T): T {
  if (!plan || isMetricPlan(plan)) return plan
  const p = plan as FloorPlan
  return {
    ...p,
    units: METRIC,
    totalWidth: ft(p.totalWidth || 0),
    totalHeight: ft(p.totalHeight || 0),
    ceilingHeight: ft(p.ceilingHeight || 9),
    envelope: p.envelope ? { width: ft(p.envelope.width), depth: ft(p.envelope.depth) } : p.envelope,
    rooms: (p.rooms || []).map(r => ({
      ...r,
      x: ft(r.x),
      y: ft(r.y),
      width: ft(r.width),
      height: ft(r.height),
      footprint: r.footprint
        ? {
            ...r.footprint,
            parts: (r.footprint.parts || []).map(part => ({
              ...part,
              x: ft(part.x),
              y: ft(part.y),
              width: ft(part.width),
              height: ft(part.height),
            })),
            centroid: r.footprint.centroid ? pt(r.footprint.centroid) : r.footprint.centroid,
            boundary: r.footprint.boundary?.map(seg),
          }
        : r.footprint,
    })),
    doors: (p.doors || []).map(pt),
    walls: p.walls?.map(seg),
    openings: p.openings?.map(o => ({
      ...pt(o),
      width: ft(o.width),
      height: opt(o.height),
      sillHeight: opt(o.sillHeight),
    })),
    furniture: p.furniture?.map(f => ({ ...pt(f), width: ft(f.width), depth: ft(f.depth) })),
  } as T
}

/** Legacy briefs stored `house.livingAreaSqft` (ft²); returns a brief with `livingAreaM2` (m²). */
export function normalizeQuestionnaire<T>(questionnaire: T): T {
  const q = questionnaire as { house?: Record<string, unknown> } | null | undefined
  const house = q?.house
  if (!house || typeof house.livingAreaSqft !== 'number') return questionnaire
  const { livingAreaSqft, ...rest } = house as { livingAreaSqft: number } & Record<string, unknown>
  const m2 = typeof rest.livingAreaM2 === 'number' ? rest.livingAreaM2 : legacySquareFeetToSquareMeters(livingAreaSqft)
  return { ...q, house: { ...rest, livingAreaM2: m2 } } as T
}

export interface PinCoords {
  x?: number | null
  y?: number | null
  coord_units?: string | null
}

/** Comment pins: legacy rows (no coord_units) are plan-feet; returns meters. */
export function normalizeCommentCoords<T extends PinCoords>(c: T): T {
  if (c.coord_units === METRIC) return c
  return {
    ...c,
    x: c.x == null ? c.x : ft(c.x),
    y: c.y == null ? c.y : ft(c.y),
    coord_units: METRIC,
  }
}
