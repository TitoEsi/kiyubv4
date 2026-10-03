import type { Door, FloorPlan, PlanFurniture, PlanOpening, PlanWall, Room } from '../../types/floorplan'
import type { Opening, Room as SceneRoom, SceneDocument, Wall } from '../types'
import { METRIC } from '../../units/legacy'
import { legacyFeetToMeters } from '../../units/measurement'

const TYPE_TO_PLAN: Record<string, string> = {
  living_room: 'living_room',
  dining_room: 'dining_room',
  kitchen: 'kitchen',
  bedroom: 'bedroom',
  master_bedroom: 'master_bedroom',
  bathroom: 'bathroom',
  toilet: 'half_bath',
  garage: 'garage',
  laundry: 'laundry_room',
  storage: 'closet',
  hallway: 'hallway',
  corridor: 'hallway',
  office: 'home_office',
  utility: 'utility_room',
  entry: 'foyer',
  porch: 'front_porch',
  balcony: 'patio',
  stairs: 'hallway',
  other: 'living_room',
}

const COLORS: Record<string, string> = {
  living_room: '#a8d0bc',
  kitchen: '#e2d9a8',
  bedroom: '#c8d4e8',
  master_bedroom: '#e8d4dc',
  bathroom: '#a8cfe8',
  hallway: '#d8dce4',
  garage: '#c4c8c4',
}

function planType(room: SceneRoom): string {
  const source = room.metadata?.sourceType
  if (typeof source === 'string' && source) return source
  return TYPE_TO_PLAN[room.type] || room.type
}

function wallKind(wall: Wall): PlanWall['kind'] {
  return wall.type === 'exterior' ? 'exterior' : 'interior'
}

function partsFromRoom(room: SceneRoom): Array<{ x: number; y: number; width: number; height: number }> {
  const raw = room.metadata?.parts
  if (Array.isArray(raw) && raw.length) {
    return raw.map((p: { x: number; y: number; width: number; height: number }) => ({
      x: p.x,
      y: p.y,
      width: p.width,
      height: p.height,
    }))
  }
  return [{
    x: room.position.x,
    y: room.position.y,
    width: room.dimensions.width,
    height: room.dimensions.height,
  }]
}

function isVerticalWall(wall: Wall): boolean {
  return Math.abs(wall.end.y - wall.start.y) > Math.abs(wall.end.x - wall.start.x)
}

/** Envelope from scene metadata: `envelopeWidthM`, or legacy `envelopeWidthFt` (feet). */
function envelopeFromExtra(extra: Record<string, unknown>, axis: 'Width' | 'Depth'): number | null {
  const m = extra[`envelope${axis}M`]
  if (typeof m === 'number') return m
  const ft = extra[`envelope${axis}Ft`]
  if (typeof ft === 'number') return legacyFeetToMeters(ft)
  return null
}

/** SceneDocument v2 (meters) -> FloorPlan (meters, `units: "metric"`). */
export function sceneDocumentToFloorPlan(scene: SceneDocument): FloorPlan {
  const extra = (scene.metadata.extra || {}) as Record<string, unknown>
  const rooms: Room[] = scene.rooms.map(room => {
    const type = planType(room)
    return {
      id: room.id,
      name: room.name,
      type,
      x: room.position.x,
      y: room.position.y,
      width: room.dimensions.width,
      height: room.dimensions.height,
      color: (typeof room.metadata?.color === 'string' && room.metadata.color) || COLORS[type] || '#dce0e8',
      footprint: room.polygon.length
        ? {
            type,
            parts: partsFromRoom(room),
            centroid: {
              x: room.position.x + room.dimensions.width / 2,
              y: room.position.y + room.dimensions.height / 2,
            },
            boundary: room.polygon.map((p, i, arr) => {
              const q = arr[(i + 1) % arr.length]
              return { x1: p.x, y1: p.y, x2: q.x, y2: q.y }
            }),
          }
        : undefined,
    }
  })

  const walls: PlanWall[] = scene.walls.map(wall => ({
    id: wall.id,
    x1: wall.start.x,
    y1: wall.start.y,
    x2: wall.end.x,
    y2: wall.end.y,
    kind: wallKind(wall),
    roomIds: [...wall.roomIds],
  }))

  const openings: PlanOpening[] = scene.openings.map((opening: Opening) => {
    const wall = scene.walls.find(w => w.id === opening.wallId)
    const kind = opening.type === 'window' ? 'window' : opening.type === 'sliding_door' ? 'sliding_door' : opening.type === 'garage_door' ? 'garage_door' : 'door'
    return {
      id: opening.id,
      wallId: opening.wallId,
      kind,
      x: opening.position.x,
      y: opening.position.y,
      width: opening.width,
      height: opening.height,
      isVertical: wall ? isVerticalWall(wall) : false,
      roomIds: (opening.metadata?.roomIds as string[] | undefined) || wall?.roomIds,
      sillHeight: opening.sillHeight,
    }
  })

  const doors: Door[] = openings
    .filter(o => o.kind === 'door')
    .map(o => ({
      id: o.id,
      x: o.x,
      y: o.y,
      isVertical: o.isVertical,
      roomA: o.roomIds?.[0] || '',
      roomB: o.roomIds?.[1] || o.roomIds?.[0] || '',
      wallId: o.wallId,
    }))

  const furniture: PlanFurniture[] = (scene.furniture || []).map(item => ({
    id: item.id,
    roomId: item.roomId,
    kind: item.kind,
    x: item.position.x,
    y: item.position.y,
    width: item.dimensions.width,
    depth: item.dimensions.height,
    rotation: item.rotation || 0,
    assetId: typeof item.metadata?.assetId === 'string' ? item.metadata.assetId : undefined,
  }))

  const xs = rooms.flatMap(r => [r.x, r.x + r.width])
  const ys = rooms.flatMap(r => [r.y, r.y + r.height])
  const envelopeW = envelopeFromExtra(extra, 'Width') ?? (xs.length ? Math.max(...xs) : scene.site.width)
  const envelopeD = envelopeFromExtra(extra, 'Depth') ?? (ys.length ? Math.max(...ys) : scene.site.depth)

  const ceilingM = scene.walls[0]?.height || scene.floorData[0]?.height || 2.74

  return {
    id: (extra.planId as string) || scene.projectId,
    name: scene.projectId,
    units: METRIC,
    totalWidth: envelopeW,
    totalHeight: envelopeD,
    ceilingHeight: ceilingM,
    rooms,
    doors,
    walls,
    openings,
    furniture,
  }
}
