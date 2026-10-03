import { describe, expect, it } from 'vitest'
import { ArchitectClientRow, Project } from './api'
import { filterAndSortClients, filterAndSortProjects, floorPlanLabel, groupClientsByEmail } from './projectQuery'

const projects: Project[] = [
  {
    id: '1',
    name: 'Residential House',
    client_id: 'c1',
    architect_id: 'a1',
    status: 'IN_PROGRESS',
    client_email: 'juan@kiyub.local',
    has_floor_plan: true,
    generation_status: 'completed',
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-03T00:00:00Z',
  },
  {
    id: '2',
    name: 'Family Residence',
    client_id: null,
    architect_id: 'a1',
    status: 'DRAFT',
    client_email: 'maria@kiyub.local',
    has_floor_plan: false,
    generation_status: 'idle',
    created_at: '2026-01-04T00:00:00Z',
    updated_at: '2026-01-04T00:00:00Z',
  },
]

const clients: ArchitectClientRow[] = [
  {
    email: 'juan@kiyub.local',
    user_id: 'c1',
    project_id: '1',
    project_name: 'Residential House',
    invitation_status: 'ACCEPTED',
    project_status: 'IN_PROGRESS',
    last_activity: '2026-01-03T00:00:00Z',
    created_at: '2026-01-01T00:00:00Z',
    invitation_id: 'i1',
  },
  {
    email: 'maria@kiyub.local',
    user_id: null,
    project_id: '2',
    project_name: 'Family Residence',
    invitation_status: 'PENDING',
    project_status: 'DRAFT',
    last_activity: '2026-01-04T00:00:00Z',
    created_at: '2026-01-04T00:00:00Z',
    invitation_id: 'i2',
  },
]

describe('project query', () => {
  it('searches by project and client name', () => {
    expect(filterAndSortProjects(projects, 'juan', 'updated').map(p => p.id)).toEqual(['1'])
    expect(filterAndSortProjects(projects, 'family', 'name-asc').map(p => p.id)).toEqual(['2'])
  })

  it('sorts by name', () => {
    expect(filterAndSortProjects(projects, '', 'name-asc').map(p => p.name)).toEqual([
      'Family Residence',
      'Residential House',
    ])
  })

  it('labels floor-plan state from persisted fields', () => {
    expect(floorPlanLabel(projects[0])).toBe('Ready')
    expect(floorPlanLabel(projects[1])).toBe('Waiting')
    expect(floorPlanLabel({ ...projects[1], generation_status: 'running' })).toBe('Generating')
  })
})

describe('client query', () => {
  it('searches by email and project', () => {
    expect(filterAndSortClients(clients, 'maria', 'name-asc').map(r => r.email)).toEqual(['maria@kiyub.local'])
    expect(filterAndSortClients(clients, 'residential', 'invitation').map(r => r.email)).toEqual(['juan@kiyub.local'])
  })

  it('groups one client with many projects by email', () => {
    const extra: ArchitectClientRow = {
      email: 'JUAN@kiyub.local',
      full_name: 'Juan',
      user_id: 'c1',
      project_id: '3',
      project_name: 'Second House',
      invitation_status: 'ACCEPTED',
      project_status: 'DRAFT',
      last_activity: '2026-01-05T00:00:00Z',
      created_at: '2026-01-05T00:00:00Z',
      invitation_id: 'i3',
    }
    const groups = groupClientsByEmail([...clients, extra])
    const juan = groups.find(g => g.email.toLowerCase() === 'juan@kiyub.local')
    expect(juan?.projects).toHaveLength(2)
    expect(juan?.full_name).toBe('Juan')
    expect(juan?.last_activity).toBe('2026-01-05T00:00:00Z')
    expect(groups).toHaveLength(2)
  })
})
