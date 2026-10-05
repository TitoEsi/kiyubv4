import type { FloorPlan, Room as PlanRoom } from '../types/floorplan'
import type { SceneDocument } from '../scene-graph/types'
import { planType, sceneRoomColor } from '../scene-graph/adapters/scene-document-to-floorplan'

export const DEFAULT_CEILING_M = 2.7432

/** Plan room types left out of the living-area total. */
const NON_LIVING_TYPES = ['garage', 'patio', 'deck', 'rear_patio', 'outdoor_living', 'front_porch']

/** Display row for the Rooms panel; derived on render, never stored. Lengths in meters, area in m². */
export interface RoomRow {
  id: string
  name: string
  color: string
  width: number
  depth: number
  area: number
}

/** Summary section values; derived on render, never stored. Meters / m². */
export interface SidebarSummary {
  roomCount: number
  livingAreaM2: number
  footprintW: number
  footprintD: number
  ceilingM: number
}

export function planRoomRows(rooms: PlanRoom[]): RoomRow[] {
  return rooms.map(r => ({
    id: r.id,
    name: r.name,
    color: r.color,
    width: r.width,
    depth: r.height,
    area: r.width * r.height,
  }))
}

export function sceneRoomRows(scene: SceneDocument): RoomRow[] {
  return scene.rooms.map(r => ({
    id: r.id,
    name: r.name,
    color: sceneRoomColor(r),
    width: r.dimensions.width,
    depth: r.dimensions.height,
    area: r.area || r.dimensions.width * r.dimensions.height,
  }))
}

export function planSummary(plan: FloorPlan): SidebarSummary {
  return {
    roomCount: plan.rooms.length,
    livingAreaM2: plan.rooms
      .filter(r => !NON_LIVING_TYPES.includes(r.type))
      .reduce((s, r) => s + r.width * r.height, 0),
    footprintW: plan.totalWidth,
    footprintD: plan.totalHeight,
    ceilingM: plan.ceilingHeight || DEFAULT_CEILING_M,
  }
}

/** Axis-aligned extent used for the sidebar footprint and the sheet's overall dimensions. */
export function sceneFootprint(scene: SceneDocument): { minX: number; minY: number; width: number; depth: number } {
  const pts = scene.walls.length
    ? scene.walls.flatMap(w => [w.start, w.end])
    : scene.rooms.flatMap(r => [r.position, { x: r.position.x + r.dimensions.width, y: r.position.y + r.dimensions.height }])
  if (!pts.length) return { minX: 0, minY: 0, width: 0, depth: 0 }
  const xs = pts.map(p => p.x)
  const ys = pts.map(p => p.y)
  const minX = Math.min(...xs)
  const minY = Math.min(...ys)
  return { minX, minY, width: Math.max(...xs) - minX, depth: Math.max(...ys) - minY }
}

export function sceneSummary(scene: SceneDocument): SidebarSummary {
  const rows = sceneRoomRows(scene)
  const footprint = sceneFootprint(scene)
  return {
    roomCount: scene.rooms.length,
    livingAreaM2: scene.rooms.reduce(
      (s, r, i) => (NON_LIVING_TYPES.includes(planType(r)) ? s : s + rows[i].area),
      0,
    ),
    footprintW: footprint.width,
    footprintD: footprint.depth,
    ceilingM: scene.walls[0]?.height || scene.floorData[0]?.height || DEFAULT_CEILING_M,
  }
}
