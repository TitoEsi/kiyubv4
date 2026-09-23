import { FloorPlan, roomCentroid } from '../types/floorplan'

export interface PlanAnnotation {
  id: string
  body: string
  author_id: string
  author_email?: string | null
  author_role?: string | null
  created_at: string | null
  object_id?: string | null
  x?: number | null
  y?: number | null
}

export function annotationPoint(a: PlanAnnotation, plan: FloorPlan): { x: number; y: number } | null {
  if (a.x != null && a.y != null) return { x: a.x, y: a.y }
  if (a.object_id) {
    const room = plan.rooms.find(r => r.id === a.object_id)
    if (room) {
      const c = roomCentroid(room)
      return { x: c.x, y: c.y }
    }
  }
  return null
}

export function commentRoleLabel(role?: string | null): string {
  if (role === 'CLIENT') return 'Client comment'
  if (role === 'ARCHITECT') return 'Architect comment'
  return 'Comment'
}

export function pinTargetLabel(plan: FloorPlan, objectId?: string | null): string | null {
  if (!objectId) return null
  const room = plan.rooms.find(r => r.id === objectId)
  return room?.name || room?.type || objectId
}

export function clientCommentCountLabel(count = 0, ready = false): string | null {
  if (count > 0) return `${count} client comment${count === 1 ? '' : 's'}`
  if (ready) return 'No client comments'
  return null
}
