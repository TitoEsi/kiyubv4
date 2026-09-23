import { roomCentroid, roomParts, type FloorPlan, type Room } from '../types/floorplan'

export const VIEW3D_SCALE = 0.09

export type View3DMode = 'exterior' | 'dollhouse' | 'walkthrough' | 'topview'

export type Vec3 = [number, number, number]

export interface BuildingBounds {
  minX: number
  maxX: number
  minZ: number
  maxZ: number
  cx: number
  cz: number
  spanX: number
  spanZ: number
  span: number
}

export interface ViewCameraConfig {
  kind: 'perspective' | 'orthographic'
  position: Vec3
  target: Vec3
  up?: Vec3
  fov?: number
  halfWidth?: number
  halfHeight?: number
}

type PlanBounds = Pick<FloorPlan, 'rooms' | 'totalWidth' | 'totalHeight'>

export function buildingBounds(plan: PlanBounds, scale = VIEW3D_SCALE): BuildingBounds {
  let minX = Infinity
  let maxX = -Infinity
  let minZ = Infinity
  let maxZ = -Infinity
  for (const room of plan.rooms) {
    for (const p of roomParts(room)) {
      minX = Math.min(minX, p.x * scale)
      maxX = Math.max(maxX, (p.x + p.width) * scale)
      minZ = Math.min(minZ, p.y * scale)
      maxZ = Math.max(maxZ, (p.y + p.height) * scale)
    }
  }
  if (!Number.isFinite(minX)) {
    minX = 0
    maxX = plan.totalWidth * scale
    minZ = 0
    maxZ = plan.totalHeight * scale
  }
  const cx = (minX + maxX) / 2
  const cz = (minZ + maxZ) / 2
  const spanX = Math.max(maxX - minX, 0.5)
  const spanZ = Math.max(maxZ - minZ, 0.5)
  return { minX, maxX, minZ, maxZ, cx, cz, spanX, spanZ, span: Math.max(spanX, spanZ) }
}

export function walkStartPosition(
  rooms: Room[],
  wallH: number,
  scale = VIEW3D_SCALE,
): Vec3 {
  const room = rooms[0]
  if (!room) return [0, wallH * 0.62, 0]
  const c = roomCentroid(room)
  return [c.x * scale, wallH * 0.62, c.y * scale]
}

export function viewCameraConfig(
  mode: View3DMode,
  bounds: BuildingBounds,
  wallH: number,
  walkStart?: Vec3,
): ViewCameraConfig {
  const { cx, cz, span, spanX, spanZ } = bounds

  if (mode === 'topview') {
    return {
      kind: 'orthographic',
      position: [cx, Math.max(wallH * 8, span * 2.2), cz],
      target: [cx, 0, cz],
      // Smaller plan-y (ArchPlan north) maps to -Z. camera.up must not be
      // parallel to the view axis (default 0,1,0 looks down -Y).
      up: [0, 0, -1],
      halfWidth: spanX / 2 * 1.2,
      halfHeight: spanZ / 2 * 1.2,
    }
  }

  if (mode === 'dollhouse') {
    return {
      kind: 'perspective',
      position: [cx + span * 0.55, wallH * 4.2 + span * 0.45, cz + span * 0.85],
      target: [cx, 0, cz],
      fov: 52,
    }
  }

  if (mode === 'walkthrough') {
    const position = walkStart ?? [cx, wallH * 0.62, cz]
    return {
      kind: 'perspective',
      position,
      target: [position[0], position[1], position[2] - 1],
      fov: 72,
    }
  }

  return {
    kind: 'perspective',
    position: [cx + span * 0.7, wallH * 1.4 + span * 0.15, cz + span * 1.15],
    target: [cx, wallH * 0.44, cz],
    fov: 44,
  }
}
