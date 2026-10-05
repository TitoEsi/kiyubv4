import { FloorPlan, roomCentroid } from '../types/floorplan'
import type { Comment } from '../workflow/api'

/** A comment pinned in plan meters (legacy plan-feet pins are normalized in workflow/api.ts). */
export type PlanAnnotation = Comment & { replies?: Comment[] }

/** Sticky-note markers show only for unresolved top-level comments with a pin. */
export function isStickyVisible(a: PlanAnnotation): boolean {
  return !a.parent_id && !a.resolved && a.x != null && a.y != null
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
