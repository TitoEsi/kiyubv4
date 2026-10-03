export type Role = 'CLIENT' | 'ARCHITECT' | 'MAIN_ADMIN' | 'IT_PERSONNEL'

export interface Actor {
  id: string
  role: Role
  approved?: boolean
}

export interface ProjectRef {
  id?: string
  client_id?: string | null
  architect_id?: string | null
  status?: string
  has_floor_plan?: boolean
}

export function canViewProject(actor: Actor, project: ProjectRef): boolean {
  if (actor.role === 'MAIN_ADMIN' || actor.role === 'IT_PERSONNEL') return true
  if (actor.role === 'CLIENT') return project.client_id === actor.id
  if (actor.role === 'ARCHITECT') return project.architect_id === actor.id
  return false
}

export function canEditDesign(actor: Actor, project: ProjectRef): boolean {
  if (actor.role !== 'ARCHITECT' || actor.approved === false) return false
  if (project.status === 'PUBLISHED') return false
  return project.architect_id === actor.id
}

export function canGenerate(actor: Actor, project: ProjectRef): boolean {
  if (project.status === 'PUBLISHED') return false
  if (actor.role === 'CLIENT') return project.client_id === actor.id
  if (actor.role === 'ARCHITECT' && actor.approved !== false) {
    if (project.architect_id !== actor.id) return false
    if (project.has_floor_plan === false) return false
    return true
  }
  return false
}

export function canOpenArchitectCanvas(actor: Actor, project: ProjectRef): boolean {
  if (actor.role !== 'ARCHITECT' || actor.approved === false) return false
  if (project.architect_id !== actor.id) return false
  return project.has_floor_plan === true
}

export function canComment(actor: Actor, project: ProjectRef): boolean {
  if (actor.role === 'CLIENT') return project.client_id === actor.id
  if (actor.role === 'ARCHITECT') return project.architect_id === actor.id
  return false
}

export function canSelectCandidate(actor: Actor, project: ProjectRef): boolean {
  return actor.role === 'CLIENT' && project.client_id === actor.id && project.status !== 'PUBLISHED'
}

export function canApprove(actor: Actor, project: ProjectRef): boolean {
  if (project.status === 'PUBLISHED') return false
  if (actor.role === 'CLIENT') return project.client_id === actor.id && project.status === 'FOR_CHECKING'
  if (actor.role === 'ARCHITECT' && actor.approved !== false) {
    return project.architect_id === actor.id && project.status === 'FOR_CHECKING'
  }
  return false
}

export function canPublish(actor: Actor, project: ProjectRef): boolean {
  return (
    actor.role === 'ARCHITECT' &&
    actor.approved !== false &&
    project.architect_id === actor.id &&
    project.status === 'APPROVED'
  )
}

export function canSubmitReview(actor: Actor, project: ProjectRef): boolean {
  if (actor.role === 'ARCHITECT' && actor.approved !== false && project.architect_id === actor.id) {
    return project.status === 'IN_PROGRESS' || project.status === 'FOR_CHECKING'
  }
  if (project.status !== 'IN_PROGRESS') return false
  if (actor.role === 'CLIENT' && project.client_id === actor.id && project.has_floor_plan) {
    return true
  }
  return false
}

export function canManageAccounts(actor: Actor): boolean {
  return actor.role === 'MAIN_ADMIN' || actor.role === 'IT_PERSONNEL'
}

export function canViewAudit(actor: Actor): boolean {
  return actor.role === 'MAIN_ADMIN' || actor.role === 'IT_PERSONNEL' || actor.role === 'ARCHITECT' || actor.role === 'CLIENT'
}
