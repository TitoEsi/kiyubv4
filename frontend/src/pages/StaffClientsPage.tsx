import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import WorkflowShell from './WorkflowShell'
import { ArchitectClientRow, listArchitectClients } from '../workflow/api'
import { displayNameFromEmail, formatDate, formatRelative } from '../workflow/displayName'

export default function StaffClientsPage() {
  const [rows, setRows] = useState<ArchitectClientRow[]>([])
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    listArchitectClients().then(setRows).catch(e => setError(String(e)))
  }, [])

  return (
    <WorkflowShell>
      <div className="studio-home">
        <header className="studio-page-head">
          <div>
            <p className="studio-meta">Directory</p>
            <h1 className="studio-page-title">Clients</h1>
          </div>
        </header>
        {error && <div className="error-msg" role="alert">{error}</div>}
        {rows.length === 0 ? (
          <p className="wf-hint">No clients to display.</p>
        ) : (
          <div className="studio-table-wrap">
            <table className="studio-table">
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Email</th>
                  <th>Assigned architect</th>
                  <th>Projects</th>
                  <th>Status</th>
                  <th>Joined</th>
                  <th>Last activity</th>
                </tr>
              </thead>
              <tbody>
                {rows.map(row => (
                  <tr key={`${row.project_id || 'pending'}-${row.email}-${row.invitation_id || 'row'}`}>
                    <td>{row.full_name || displayNameFromEmail(row.email)}</td>
                    <td>{row.email}</td>
                    <td>{row.architect_email || '—'}</td>
                    <td>
                      {row.project_id
                        ? <Link to={`/projects/${row.project_id}`}>{row.project_name || 'Project'}</Link>
                        : (row.project_name || '—')}
                    </td>
                    <td>{row.invitation_status?.replace(/_/g, ' ') || row.project_status?.replace(/_/g, ' ') || '—'}</td>
                    <td>{formatDate(row.created_at) || '—'}</td>
                    <td>{formatRelative(row.last_activity)?.replace(/^Updated /, '') || '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </WorkflowShell>
  )
}
