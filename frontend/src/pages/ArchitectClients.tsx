import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import InviteClientModal from '../components/InviteClientModal'
import WorkflowShell from './WorkflowShell'
import { ArchitectClientRow, listArchitectClients } from '../workflow/api'
import { displayNameFromEmail, formatDate, formatRelative } from '../workflow/displayName'
import { ClientSort, filterAndSortClients } from '../workflow/projectQuery'

export default function ArchitectClients() {
  const [rows, setRows] = useState<ArchitectClientRow[]>([])
  const [query, setQuery] = useState('')
  const [sort, setSort] = useState<ClientSort>('name-asc')
  const [error, setError] = useState<string | null>(null)
  const [inviteOpen, setInviteOpen] = useState(false)

  async function refresh() {
    setRows(await listArchitectClients())
  }

  useEffect(() => {
    refresh().catch(e => setError(String(e)))
  }, [])

  const visible = useMemo(() => filterAndSortClients(rows, query, sort), [rows, query, sort])

  return (
    <WorkflowShell>
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
                  <th>Assigned architect</th>
                  <th>Project</th>
                  <th>Status</th>
                  <th>Joined</th>
                  <th>Last activity</th>
                </tr>
              </thead>
              <tbody>
                {visible.map(row => (
                  <tr key={`${row.project_id || 'pending'}-${row.email}-${row.invitation_id || 'assigned'}`}>
                    <td>{row.full_name || displayNameFromEmail(row.email)}</td>
                    <td>{row.email}</td>
                    <td>{row.architect_email || '—'}</td>
                    <td>
                      {row.project_id
                        ? <Link to={`/projects/${row.project_id}`}>{row.project_name || 'Open project'}</Link>
                        : (row.project_name || '—')}
                    </td>
                    <td>{row.invitation_status ? row.invitation_status.replace(/_/g, ' ') : (row.project_status || 'Assigned')}</td>
                    <td>{formatDate(row.created_at) || '—'}</td>
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
          onClose={() => setInviteOpen(false)}
          onSent={() => { void refresh() }}
        />
      )}
    </WorkflowShell>
  )
}
