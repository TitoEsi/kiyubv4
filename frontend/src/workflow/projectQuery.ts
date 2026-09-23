import { ArchitectClientRow, Project } from './api'
import { displayNameFromEmail } from './displayName'

export type ProjectSort = 'updated' | 'newest' | 'oldest' | 'name-asc' | 'name-desc' | 'status'

export type ClientSort = 'name-asc' | 'name-desc' | 'active' | 'added' | 'invitation'

export function projectMatches(project: Project, query: string): boolean {
  const q = query.trim().toLowerCase()
  if (!q) return true
  const clientName = project.client_email ? displayNameFromEmail(project.client_email) : ''
  return [project.name, project.client_email || '', clientName, project.status]
    .join(' ')
    .toLowerCase()
    .includes(q)
}

export function sortProjects(projects: Project[], sort: ProjectSort): Project[] {
  const copy = [...projects]
  const stamp = (iso?: string | null) => (iso ? new Date(iso).getTime() : 0)
  copy.sort((a, b) => {
    switch (sort) {
      case 'newest':
        return stamp(b.created_at) - stamp(a.created_at)
      case 'oldest':
        return stamp(a.created_at) - stamp(b.created_at)
      case 'name-asc':
        return a.name.localeCompare(b.name)
      case 'name-desc':
        return b.name.localeCompare(a.name)
      case 'status':
        return a.status.localeCompare(b.status) || a.name.localeCompare(b.name)
      case 'updated':
      default:
        return stamp(b.updated_at) - stamp(a.updated_at)
    }
  })
  return copy
}

export function filterAndSortProjects(projects: Project[], query: string, sort: ProjectSort): Project[] {
  return sortProjects(projects.filter(p => projectMatches(p, query)), sort)
}

export function clientMatches(row: ArchitectClientRow, query: string): boolean {
  const q = query.trim().toLowerCase()
  if (!q) return true
  const name = displayNameFromEmail(row.email)
  return [name, row.email, row.project_name, row.invitation_status || '', row.project_status]
    .join(' ')
    .toLowerCase()
    .includes(q)
}

export function sortClients(rows: ArchitectClientRow[], sort: ClientSort): ArchitectClientRow[] {
  const copy = [...rows]
  const stamp = (iso?: string | null) => (iso ? new Date(iso).getTime() : 0)
  copy.sort((a, b) => {
    const nameA = displayNameFromEmail(a.email)
    const nameB = displayNameFromEmail(b.email)
    switch (sort) {
      case 'name-desc':
        return nameB.localeCompare(nameA)
      case 'active':
        return stamp(b.last_activity) - stamp(a.last_activity)
      case 'added':
        return stamp(b.created_at) - stamp(a.created_at)
      case 'invitation':
        return (a.invitation_status || 'ZZZ').localeCompare(b.invitation_status || 'ZZZ') || nameA.localeCompare(nameB)
      case 'name-asc':
      default:
        return nameA.localeCompare(nameB)
    }
  })
  return copy
}

export function filterAndSortClients(rows: ArchitectClientRow[], query: string, sort: ClientSort): ArchitectClientRow[] {
  return sortClients(rows.filter(r => clientMatches(r, query)), sort)
}

export function floorPlanLabel(project: Project): string {
  if (project.generation_status === 'running') return 'Generating'
  if (project.has_floor_plan) return 'Ready'
  return 'Waiting'
}
