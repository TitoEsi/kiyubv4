export interface FootprintPart {
  x: number
  y: number
  width: number
  height: number
}

export interface BoundarySegment {
  x1: number
  y1: number
  x2: number
  y2: number
}

export interface RoomFootprint {
  type: string
  parts: FootprintPart[]
  centroid?: { x: number; y: number }
  boundary?: BoundarySegment[]
}

export interface Room {
  id: string
  name: string
  type: string
  x: number
  y: number
  width: number
  height: number
  color: string
  footprint?: RoomFootprint
}

export function roomParts(room: Room): FootprintPart[] {
  if (room.footprint?.parts?.length) {
    return room.footprint.parts
  }
  return [{ x: room.x, y: room.y, width: room.width, height: room.height }]
}

export function roomCentroid(room: Room): { x: number; y: number } {
  if (room.footprint?.centroid) {
    return room.footprint.centroid
  }
  const parts = roomParts(room)
  let area = 0
  let cx = 0
  let cy = 0
  for (const p of parts) {
    const a = p.width * p.height
    area += a
    cx += (p.x + p.width / 2) * a
    cy += (p.y + p.height / 2) * a
  }
  if (area <= 0) {
    return { x: room.x + room.width / 2, y: room.y + room.height / 2 }
  }
  return { x: cx / area, y: cy / area }
}

export function roomBoundary(room: Room): BoundarySegment[] {
  if (room.footprint?.boundary?.length) {
    return room.footprint.boundary
  }
  const { x, y, width, height } = room
  return [
    { x1: x, y1: y, x2: x + width, y2: y },
    { x1: x + width, y1: y, x2: x + width, y2: y + height },
    { x1: x, y1: y + height, x2: x + width, y2: y + height },
    { x1: x, y1: y, x2: x, y2: y + height },
  ]
}

export function roomOccupiedArea(room: Room): number {
  return roomParts(room).reduce((s, p) => s + p.width * p.height, 0)
}

export interface Door {
  x: number
  y: number
  isVertical: boolean
  roomA: string
  roomB: string
  id?: string
  wallId?: string
}

export interface PlanWall {
  id: string
  x1: number
  y1: number
  x2: number
  y2: number
  kind: "interior" | "exterior" | string
  roomIds: string[]
}

export interface PlanOpening {
  id: string
  wallId: string
  kind: "door" | "window" | string
  x: number
  y: number
  width: number
  height?: number
  isVertical: boolean
  roomIds?: string[]
  sillHeight?: number
}

export interface PlanFurniture {
  id: string
  roomId: string
  kind: string
  x: number
  y: number
  width: number
  depth: number
  rotation?: number
  assetId?: string
}

export interface FloorPlan {
  id: string
  name: string
  totalWidth: number
  totalHeight: number
  ceilingHeight: number   // feet
  rooms: Room[]
  doors: Door[]
  walls?: PlanWall[]
  openings?: PlanOpening[]
  furniture?: PlanFurniture[]
}

export type LotShape =
  | 'rectangle'
  | 'square'
  | 'l_shape'
  | 'irregular'

export interface Constraints {
  // Site
  lotShape: LotShape
  lotWidth: number
  lotDepth: number

  // Basics
  bedrooms: number
  bathrooms: number
  sqft: number
  stories: number
  style: string

  // Layout options
  openPlan: boolean        // merge living/kitchen/dining
  primarySuite: boolean    // ensuite + walk-in closet for primary bedroom
  homeOffice: boolean
  formalDining: boolean    // separate formal dining (ignored when openPlan)

  // Spaces
  garage: 'none' | '1car' | '2car' | '3car'
  laundry: 'none' | 'closet' | 'room'
  outdoor: 'none' | 'patio' | 'deck' | 'both'

  // Style
  ceilingHeight: 'standard' | 'high' | 'vaulted'   // 9ft / 10ft / 12ft
}

export interface ValidationIssue {
  field: string
  severity: 'error' | 'warning'
  message: string
  detail: string
}
