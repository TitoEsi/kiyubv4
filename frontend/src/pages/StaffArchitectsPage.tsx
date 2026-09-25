import { useEffect, useMemo, useState } from 'react'
import { Link, useLocation } from 'react-router-dom'
import WorkflowShell from './WorkflowShell'
import { AuditEvent, listAccounts, listAudit, listProjects, Project, WorkflowUser } from '../workflow/api'
import { displayNameFromEmail, formatDate, formatRelative } from '../workflow/displayName'

function statusOf(u: WorkflowUser) {
  if (u.deleted_at) return 'Deleted'
  if (u.suspended) return 'Suspended'
  if (!u.approved) return 'Pending'
  return 'Active'
}

export default function StaffArchitectsPage() {
  const loc = useLocation()
  const base = loc.pathname.startsWith('/it') ? '/it/architects' : '/admin/architects'
  const [users, setUsers] = useState<WorkflowUser[]>([])
  const [projects, setProjects] = useState<Project[]>([])
  const [audit, setAudit] = useState<AuditEvent[]>([])
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    Promise.all([listAccounts(), listProjects().catch(() => []), listAudit().catch(() => [])])
      .then(([accounts, nextProjects, nextAudit]) => {
        setUsers(accounts.filter(u => u.role === 'ARCHITECT'))
        setProjects(nextProjects)
        setAudit(nextAudit)
      })
      .catch(e => setError(String(e)))
  }, [])

  const rows = useMemo(() => users.map(u => {
    const own = projects.filter(p => p.architect_id === u.id)
    const clients = new Set(own.map(p => p.client_id).filter(Boolean)).size
    const last = audit.filter(e => e.actor_id === u.id)[0]?.created_at
    return { user: u, projects: own.length, clients, last }
  }), [users, projects, audit])

  return (
    <WorkflowShell>
      <div className="studio-home">
        <header className="studio-page-head">
          <div>
            <p className="studio-meta">Directory</p>
            <h1 className="studio-page-title">Architects</h1>
          </div>
        </header>
        {error && <div className="error-msg" role="alert">{error}</div>}
        {rows.length === 0 ? (
          <p className="wf-hint">No architects to display.</p>
        ) : (
          <div className="studio-table-wrap">
            <table className="studio-table">
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Email</th>
                  <th>Projects</th>
                  <th>Clients</th>
                  <th>Status</th>
                  <th>Joined</th>
                  <th>Last activity</th>
                </tr>
              </thead>
              <tbody>
                {rows.map(({ user, projects: count, clients, last }) => (
                  <tr key={user.id}>
                    <td><Link to={`${base}/${user.id}`}>{user.full_name || displayNameFromEmail(user.email)}</Link></td>
                    <td>{user.email}</td>
                    <td>{count}</td>
                    <td>{clients}</td>
                    <td><span className="studio-badge">{statusOf(user)}</span></td>
                    <td>{formatDate(user.created_at) || '—'}</td>
                    <td>{formatRelative(last)?.replace(/^Updated /, '') || '—'}</td>
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
