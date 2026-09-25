import { useEffect, useState } from 'react'
import WorkflowShell from './WorkflowShell'
import { ArchitectClientRow, listArchitectClients } from '../workflow/api'
import { displayNameFromEmail, formatDate } from '../workflow/displayName'

export default function ArchitectInvitationsPage() {
  const [rows, setRows] = useState<ArchitectClientRow[]>([])
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    listArchitectClients()
      .then(list => setRows(list.filter(r => r.invitation_status === 'PENDING')))
      .catch(e => setError(String(e)))
  }, [])

  return (
    <WorkflowShell>
      <div className="studio-home">
        <header className="studio-page-head">
          <div>
            <p className="studio-meta">Invitations</p>
            <h1 className="studio-page-title">Pending invites</h1>
          </div>
        </header>
        {error && <div className="error-msg" role="alert">{error}</div>}
        {rows.length === 0 ? (
          <p className="wf-hint">No pending invitations.</p>
        ) : (
          <div className="studio-table-wrap">
            <table className="studio-table">
              <thead>
                <tr>
                  <th>Client</th>
                  <th>Email</th>
                  <th>Project</th>
                  <th>Sent</th>
                </tr>
              </thead>
              <tbody>
                {rows.map(row => (
                  <tr key={row.invitation_id || row.email}>
                    <td>{displayNameFromEmail(row.email)}</td>
                    <td>{row.email}</td>
                    <td>{row.project_name || '—'}</td>
                    <td>{formatDate(row.created_at) || '—'}</td>
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
