import type { FloorPlan } from '../../types/floorplan'
import type { SceneDocument } from '../types'
import { floorPlanToSceneDocument, isCornerAnchoredPlan, planOpeningCentre, type LotMeters } from '../adapters/floorplan-to-scene-document'
import { normalizeDoorSwings } from './door-geometry'
import { dist, projectT } from './geometry'
import { normalizeFloorPlan } from '../../units/legacy'
import { assignJunctions, bootstrapWallsFromRooms } from './bootstrap-walls'
import { syncOpeningsToWalls } from './opening-ops'
import { fidelityReport } from '../adapters/scene-entities'

const FALLBACK_LOT_WIDTH_M = 12.192
const FALLBACK_LOT_DEPTH_M = 10.668
const MIN_LOT_M = 8

export function defaultLotFromPlan(input: FloorPlan, lot?: Partial<LotMeters>): LotMeters {
  const plan = normalizeFloorPlan(input)
  const w = lot?.lotWidth && lot.lotWidth > 0 ? lot.lotWidth : Math.max(plan.totalWidth || FALLBACK_LOT_WIDTH_M, MIN_LOT_M)
  const d = lot?.lotDepth && lot.lotDepth > 0 ? lot.lotDepth : Math.max(plan.totalHeight || FALLBACK_LOT_DEPTH_M, MIN_LOT_M)
  return { lotWidth: w, lotDepth: d, stories: lot?.stories || 1 }
}

const UNTOUCHED_EPS_M = 0.01

/**
 * Scenes saved before openings were centred kept OR-tools start corners as centres. An opening that
 * still sits on its source corner was never moved, so it is re-centred on its true span.
 */
function recentreUntouchedEngineOpenings(scene: SceneDocument, input: FloorPlan): SceneDocument {
  const plan = normalizeFloorPlan(input)
  if (!plan || !isCornerAnchoredPlan(plan) || !plan.openings?.length) return scene
  const source = new Map(plan.openings.map(o => [o.id, o]))
  const walls = new Map(scene.walls.map(w => [w.id, w]))
  let changed = false
  const openings = scene.openings.map(o => {
    const src = source.get(o.id)
    const wall = walls.get(o.wallId)
    if (!src || !wall || o.metadata?.swingSide != null) return o
    if (dist(o.position, { x: src.x, y: src.y }) > UNTOUCHED_EPS_M) return o
    const centre = planOpeningCentre(src, true)
    if (dist(centre, o.position) <= UNTOUCHED_EPS_M) return o
    changed = true
    return { ...o, position: centre, metadata: { ...(o.metadata || {}), t: projectT(wall, centre) } }
  })
  return changed ? { ...scene, openings } : scene
}

export function isSceneDocument(value: unknown): value is SceneDocument {
  if (!value || typeof value !== 'object') return false
  const v = value as SceneDocument
  return v.version === '2.0' && v.units === 'metric' && Array.isArray(v.walls) && Array.isArray(v.rooms)
}

export function loadLiveScene(
  plan: FloorPlan,
  lot?: Partial<LotMeters>,
  options: { projectId?: string; existing?: unknown } = {},
): SceneDocument {
  if (isSceneDocument(options.existing) && options.existing.walls) {
    let scene = options.existing
    if (!scene.furniture) scene = { ...scene, furniture: [] }
    if (!scene.walls.length) scene = bootstrapWallsFromRooms(scene)
    scene = recentreUntouchedEngineOpenings(scene, plan)
    return normalizeDoorSwings(syncOpeningsToWalls(assignJunctions(scene)))
  }
  const safeLot = defaultLotFromPlan(plan, lot)
  let scene = floorPlanToSceneDocument(plan, safeLot, { projectId: options.projectId })
  if (!scene.walls.length) scene = bootstrapWallsFromRooms(scene)
  scene = syncOpeningsToWalls(assignJunctions(scene))
  if (typeof localStorage !== 'undefined' && localStorage.getItem('kiyub.fidelity') === '1') {
    console.debug('[fidelity]', fidelityReport(plan, scene))
  }
  return scene
}
