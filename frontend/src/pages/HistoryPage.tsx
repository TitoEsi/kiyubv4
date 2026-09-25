import { useEffect, useState } from 'react'
import WorkflowShell from './WorkflowShell'
import { AuditEvent, listAudit, listProjects, Project } from '../workflow/api'

function stamp(iso: string | null) {
  if (!iso) return '—'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  return d.toLocaleString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  })
}

function actionLabel(type: string) {
  return type.replace(/_/g, ' ')
}

export default function HistoryPage() {
  const [rows, setRows] = useState<AuditEvent[]>([])
  const [projects, setProjects] = useState<Project[]>([])
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    Promise.all([listAudit(), listProjects().catch(() => [] as Project[])])
      .then(([events, nextProjects]) => {
        setRows(events)
        setProjects(nextProjects)
      })
      .catch(e => setError(String(e)))
  }, [])

  const names = Object.fromEntries(projects.map(p => [p.id, p.name]))
  const showProject = rows.some(e => e.project_id)

  return (
    <WorkflowShell>
      <div className="studio-home">
        <header className="studio-page-head">
          <div>
            <p className="studio-meta">Audit</p>
            <h1 className="studio-page-title">History</h1>
          </div>
        </header>
        {error && <div className="error-msg" role="alert">{error}</div>}
        {rows.length === 0 ? (
          <p className="wf-hint">No history for your role yet.</p>
        ) : (
          <div className="studio-table-wrap">
            <table className="studio-table">
              <thead>
                <tr>
                  <th>Action</th>
                  <th>Account</th>
                  <th>Timestamp</th>
                  {showProject && <th>Project</th>}
                </tr>
              </thead>
              <tbody>
                {rows.map(e => (
                  <tr key={e.id}>
                    <td>{actionLabel(e.event_type)}</td>
                    <td>{e.actor_email || e.target || '—'}</td>
                    <td>{stamp(e.created_at)}</td>
                    {showProject && <td>{e.project_id ? (names[e.project_id] || e.project_id) : '—'}</td>}
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
