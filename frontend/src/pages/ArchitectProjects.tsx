import { useEffect, useMemo, useState } from 'react'
import InviteClientModal from '../components/InviteClientModal'
import WorkflowShell from './WorkflowShell'
import ProjectRegister from './ProjectRegister'
import { listNotifications, listProjects, Notification, Project } from '../workflow/api'
import { filterAndSortProjects, ProjectSort } from '../workflow/projectQuery'

export default function ArchitectProjects() {
  const [projects, setProjects] = useState<Project[]>([])
  const [notes, setNotes] = useState<Notification[]>([])
  const [query, setQuery] = useState('')
  const [sort, setSort] = useState<ProjectSort>('updated')
  const [error, setError] = useState<string | null>(null)
  const [inviteOpen, setInviteOpen] = useState(false)

  async function refresh() {
    setProjects(await listProjects())
    setNotes(await listNotifications())
  }

  useEffect(() => {
    refresh().catch(e => setError(String(e)))
  }, [])

  const visible = useMemo(() => filterAndSortProjects(projects, query, sort), [projects, query, sort])

  const empty = query
    ? 'Try another search term or clear your filters.'
    : 'Invite a client. The project appears here after they accept.'

  return (
    <WorkflowShell>
      {error && <div className="error-msg" role="alert">{error}</div>}
      <div className="studio-home">
        <header className="studio-page-head">
          <div>
            <p className="studio-meta">Register</p>
            <h1 className="studio-page-title">Projects</h1>
          </div>
          <button type="button" className="catalog-generate-btn" onClick={() => setInviteOpen(true)}>
            Invite client
          </button>
        </header>
        <div className="studio-toolbar studio-toolbar-wrap">
          <label className="sr-only" htmlFor="project-search">Search projects</label>
          <input
            id="project-search"
            value={query}
            onChange={e => setQuery(e.target.value)}
            placeholder="Search projects..."
          />
          <label className="studio-sort">
            Sort
            <select value={sort} onChange={e => setSort(e.target.value as ProjectSort)}>
              <option value="updated">Recently updated</option>
              <option value="newest">Newest</option>
              <option value="oldest">Oldest</option>
              <option value="name-asc">Project name A–Z</option>
              <option value="name-desc">Project name Z–A</option>
              <option value="status">Status</option>
            </select>
          </label>
        </div>
        <ProjectRegister
          projects={visible}
          notes={notes}
          architect
          emptyTitle={query ? 'No projects found' : 'No projects yet'}
          empty={empty}
        />
      </div>
      {inviteOpen && (
        <InviteClientModal
          onClose={() => setInviteOpen(false)}
          onSent={() => { void refresh() }}
        />
      )}
    </WorkflowShell>
  )
}
