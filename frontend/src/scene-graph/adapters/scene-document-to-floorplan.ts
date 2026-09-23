import type { Door, FloorPlan, PlanFurniture, PlanOpening, PlanWall, Room } from '../../types/floorplan'
import type { Opening, Room as SceneRoom, SceneDocument, Wall } from '../types'
import { mToFt } from '../units'

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
      x: mToFt(p.x),
      y: mToFt(p.y),
      width: mToFt(p.width),
      height: mToFt(p.height),
    }))
  }
  return [{
    x: mToFt(room.position.x),
    y: mToFt(room.position.y),
    width: mToFt(room.dimensions.width),
    height: mToFt(room.dimensions.height),
  }]
}

function isVerticalWall(wall: Wall): boolean {
  return Math.abs(wall.end.y - wall.start.y) > Math.abs(wall.end.x - wall.start.x)
}

export function sceneDocumentToFloorPlan(scene: SceneDocument): FloorPlan {
  const extra = scene.metadata.extra || {}
  const rooms: Room[] = scene.rooms.map(room => {
    const type = planType(room)
    const width = mToFt(room.dimensions.width)
    const height = mToFt(room.dimensions.height)
    return {
      id: room.id,
      name: room.name,
      type,
      x: mToFt(room.position.x),
      y: mToFt(room.position.y),
      width,
      height,
      color: (typeof room.metadata?.color === 'string' && room.metadata.color) || COLORS[type] || '#dce0e8',
      footprint: room.polygon.length
        ? {
            type,
            parts: partsFromRoom(room),
            centroid: {
              x: mToFt(room.position.x + room.dimensions.width / 2),
              y: mToFt(room.position.y + room.dimensions.height / 2),
            },
            boundary: room.polygon.map((p, i, arr) => {
              const q = arr[(i + 1) % arr.length]
              return { x1: mToFt(p.x), y1: mToFt(p.y), x2: mToFt(q.x), y2: mToFt(q.y) }
            }),
          }
        : undefined,
    }
  })

  const walls: PlanWall[] = scene.walls.map(wall => ({
    id: wall.id,
    x1: mToFt(wall.start.x),
    y1: mToFt(wall.start.y),
    x2: mToFt(wall.end.x),
    y2: mToFt(wall.end.y),
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
      x: mToFt(opening.position.x),
      y: mToFt(opening.position.y),
      width: mToFt(opening.width),
      height: mToFt(opening.height),
      isVertical: wall ? isVerticalWall(wall) : false,
      roomIds: (opening.metadata?.roomIds as string[] | undefined) || wall?.roomIds,
      sillHeight: mToFt(opening.sillHeight),
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
    x: mToFt(item.position.x),
    y: mToFt(item.position.y),
    width: mToFt(item.dimensions.width),
    depth: mToFt(item.dimensions.height),
    rotation: item.rotation || 0,
    assetId: typeof item.metadata?.assetId === 'string' ? item.metadata.assetId : undefined,
  }))

  const xs = rooms.flatMap(r => [r.x, r.x + r.width])
  const ys = rooms.flatMap(r => [r.y, r.y + r.height])
  const envelopeW = typeof extra.envelopeWidthFt === 'number'
    ? extra.envelopeWidthFt
    : xs.length ? Math.max(...xs) : mToFt(scene.site.width)
  const envelopeD = typeof extra.envelopeDepthFt === 'number'
    ? extra.envelopeDepthFt
    : ys.length ? Math.max(...ys) : mToFt(scene.site.depth)

  const ceilingM = scene.walls[0]?.height || scene.floorData[0]?.height || 2.74

  return {
    id: (extra.planId as string) || scene.projectId,
    name: scene.projectId,
    totalWidth: envelopeW,
    totalHeight: envelopeD,
    ceilingHeight: mToFt(ceilingM),
    rooms,
    doors,
    walls,
    openings,
    furniture,
  }
}
