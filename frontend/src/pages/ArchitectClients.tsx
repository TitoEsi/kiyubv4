import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import InviteClientModal from '../components/InviteClientModal'
import WorkflowShell from './WorkflowShell'
import { ArchitectClientRow, listArchitectClients, listProjects, Project } from '../workflow/api'
import { displayNameFromEmail, formatRelative } from '../workflow/displayName'
import { ClientSort, filterAndSortClients } from '../workflow/projectQuery'

export default function ArchitectClients() {
  const [rows, setRows] = useState<ArchitectClientRow[]>([])
  const [projects, setProjects] = useState<Project[]>([])
  const [query, setQuery] = useState('')
  const [sort, setSort] = useState<ClientSort>('name-asc')
  const [error, setError] = useState<string | null>(null)
  const [inviteOpen, setInviteOpen] = useState(false)

  async function refresh() {
    setRows(await listArchitectClients())
    setProjects(await listProjects())
  }

  useEffect(() => {
    refresh().catch(e => setError(String(e)))
  }, [])

  const visible = useMemo(() => filterAndSortClients(rows, query, sort), [rows, query, sort])

  return (
    <WorkflowShell title="Clients">
      {error && <div className="error-msg" role="alert">{error}</div>}
      <div className="studio-home">
        <header className="studio-page-head">
          <div>
            <p className="studio-meta">Studio</p>
            <h1 className="studio-page-title">Clients</h1>
          </div>
          <button type="button" className="catalog-generate-btn" onClick={() => setInviteOpen(true)}>
            Invite client
          </button>
        </header>
        <div className="studio-toolbar studio-toolbar-wrap">
          <label className="sr-only" htmlFor="client-search">Search clients</label>
          <input
            id="client-search"
            value={query}
            onChange={e => setQuery(e.target.value)}
            placeholder="Search clients..."
          />
          <label className="studio-sort">
            Sort
            <select value={sort} onChange={e => setSort(e.target.value as ClientSort)}>
              <option value="name-asc">Name A–Z</option>
              <option value="name-desc">Name Z–A</option>
              <option value="active">Recently active</option>
              <option value="added">Recently added</option>
              <option value="invitation">Invitation status</option>
            </select>
          </label>
        </div>
        {visible.length === 0 ? (
          <div className="studio-empty">
            <p className="studio-empty-title">{query ? 'No clients found' : 'No clients yet'}</p>
            <p className="studio-empty-copy">
              {query
                ? 'Try another search term or clear your filters.'
                : 'Invite your first client to begin a project.'}
            </p>
            {!query && (
              <button type="button" className="catalog-generate-btn" onClick={() => setInviteOpen(true)}>
                Invite client
              </button>
            )}
          </div>
        ) : (
          <div className="studio-table-wrap">
            <table className="studio-table">
              <thead>
                <tr>
                  <th>Client</th>
                  <th>Email</th>
                  <th>Project</th>
                  <th>Invitation</th>
                  <th>Project status</th>
                  <th>Last activity</th>
                </tr>
              </thead>
              <tbody>
                {visible.map(row => (
                  <tr key={`${row.project_id}-${row.email}-${row.invitation_id || 'assigned'}`}>
                    <td>{displayNameFromEmail(row.email)}</td>
                    <td>{row.email}</td>
                    <td>
                      <Link to={`/projects/${row.project_id}`}>{row.project_name}</Link>
                    </td>
                    <td>{row.invitation_status ? row.invitation_status.replace(/_/g, ' ') : 'Assigned'}</td>
                    <td>{row.project_status.replace(/_/g, ' ')}</td>
                    <td>{formatRelative(row.last_activity)?.replace(/^Updated /, '') || '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
      {inviteOpen && (
        <InviteClientModal
          projects={projects}
          onClose={() => setInviteOpen(false)}
          onSent={() => { void refresh() }}
        />
      )}
    </WorkflowShell>
  )
}
