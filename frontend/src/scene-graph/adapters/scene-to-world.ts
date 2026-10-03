/**
 * Single SceneDocument (meters) → Three.js world mapping.
 *
 * 2D (x, y) → 3D (u(x), height, u(y))
 * u(m) = m * WORLD_UNITS_PER_METER (fixed presentation scale, independent of display unit).
 *
 * THREE.Shape lives in XY. After Rx(-π/2): (sx, sy, 0) → (sx, 0, -sy).
 * shapeXY uses sy = -u(y) so the floor lands at Z = +u(y), same as walls.
 */
import { WORLD_UNITS_PER_METER } from '../../components/view3d-camera'
import type { Point2D, SceneDocument, Wall } from '../types'
import { wallLength } from '../edit/geometry'

export const SCENE_WORLD_SCALE = WORLD_UNITS_PER_METER

export function metersToWorld(meters: number, scale = SCENE_WORLD_SCALE): number {
  return meters * scale
}

export function toWorld(x: number, y: number, scale = SCENE_WORLD_SCALE): { x: number; z: number } {
  return { x: metersToWorld(x, scale), z: metersToWorld(y, scale) }
}

/** THREE.Shape point that becomes toWorld(x, y) after mesh rotation Rx(-π/2). */
export function shapeXY(x: number, y: number, scale = SCENE_WORLD_SCALE): { x: number; y: number } {
  return { x: metersToWorld(x, scale), y: -metersToWorld(y, scale) }
}

/** Angle for box-along-X walls: rotation={[0, -wallYaw(wall), 0]}. */
export function wallYaw(wall: Pick<Wall, 'start' | 'end'>): number {
  return Math.atan2(wall.end.y - wall.start.y, wall.end.x - wall.start.x)
}

export function sceneWorldBounds(scene: SceneDocument) {
  let minX = Infinity, maxX = -Infinity, minZ = Infinity, maxZ = -Infinity
  const add = (p: Point2D) => {
    const w = toWorld(p.x, p.y)
    minX = Math.min(minX, w.x)
    maxX = Math.max(maxX, w.x)
    minZ = Math.min(minZ, w.z)
    maxZ = Math.max(maxZ, w.z)
  }
  for (const room of scene.rooms) {
    if (room.polygon?.length) room.polygon.forEach(add)
    else {
      add(room.position)
      add({ x: room.position.x + room.dimensions.width, y: room.position.y + room.dimensions.height })
    }
  }
  for (const wall of scene.walls) {
    add(wall.start)
    add(wall.end)
  }
  if (!Number.isFinite(minX)) {
    const a = toWorld(0, 0)
    const b = toWorld(scene.site.width, scene.site.depth)
    minX = a.x
    maxX = b.x
    minZ = a.z
    maxZ = b.z
  }
  return {
    minX, maxX, minZ, maxZ,
    cx: (minX + maxX) / 2,
    cz: (minZ + maxZ) / 2,
    spanX: Math.max(maxX - minX, 0.5),
    spanZ: Math.max(maxZ - minZ, 0.5),
    span: Math.max(maxX - minX, maxZ - minZ, 0.5),
  }
}

export function validateSceneDocumentGeometry(scene: SceneDocument) {
  const issues: string[] = []
  const finite = (n: number) => Number.isFinite(n)
  const checkPt = (label: string, p: Point2D) => {
    if (!finite(p.x) || !finite(p.y)) issues.push(`${label} non-finite`)
  }
  for (const wall of scene.walls) {
    checkPt(`wall ${wall.id} start`, wall.start)
    checkPt(`wall ${wall.id} end`, wall.end)
    if (wallLength(wall) < 1e-6) issues.push(`wall ${wall.id} zero-length`)
  }
  for (const room of scene.rooms) {
    checkPt(`room ${room.id} position`, room.position)
    if (!room.polygon || room.polygon.length < 3) issues.push(`room ${room.id} invalid polygon`)
    else room.polygon.forEach((p, i) => checkPt(`room ${room.id} v${i}`, p))
  }
  for (const opening of scene.openings) {
    checkPt(`opening ${opening.id}`, opening.position)
    if (!scene.walls.some(w => w.id === opening.wallId)) issues.push(`opening ${opening.id} missing host ${opening.wallId}`)
  }
  for (const item of scene.furniture || []) {
    checkPt(`furniture ${item.id}`, item.position)
  }
  const bounds = sceneWorldBounds(scene)
  return {
    units: 'meters',
    mapping: '2D (x,y) → 3D (u(x), height, u(y))',
    counts: {
      rooms: scene.rooms.length,
      walls: scene.walls.length,
      openings: scene.openings.length,
      furniture: (scene.furniture || []).length,
    },
    bounds,
    issues,
    valid: issues.length === 0,
  }
}
