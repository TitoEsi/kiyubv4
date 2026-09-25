import { useEffect, useState } from 'react'
import StatCard from '../components/StatCard'
import WorkflowShell from './WorkflowShell'
import {
  ArchitectApplication,
  approveArchitectApplication,
  listAccounts,
  listArchitectApplications,
  listArchitectClients,
  listAudit,
  rejectArchitectApplication,
  WorkflowUser,
} from '../workflow/api'

export default function ITHome() {
  const [users, setUsers] = useState<WorkflowUser[]>([])
  const [clients, setClients] = useState(0)
  const [applications, setApplications] = useState<ArchitectApplication[]>([])
  const [auditCount, setAuditCount] = useState(0)
  const [error, setError] = useState<string | null>(null)
  const [busyId, setBusyId] = useState<string | null>(null)
  const [rejectId, setRejectId] = useState<string | null>(null)
  const [reason, setReason] = useState('')

  async function refresh() {
    const [accounts, apps, clientRows, audit] = await Promise.all([
      listAccounts(),
      listArchitectApplications().catch(() => []),
      listArchitectClients().catch(() => []),
      listAudit().catch(() => []),
    ])
    setUsers(accounts)
    setApplications(apps)
    setClients(new Set(clientRows.map(c => c.email)).size)
    setAuditCount(audit.length)
  }

  useEffect(() => {
    refresh().catch(e => setError(String(e)))
  }, [])

  async function onApprove(id: string) {
    setBusyId(id)
    setError(null)
    try {
      await approveArchitectApplication(id)
      await refresh()
    } catch (err: unknown) {
      const ax = err as { response?: { data?: { detail?: string } } }
      setError(ax.response?.data?.detail || 'Unable to send invitation. Please try again.')
    } finally {
      setBusyId(null)
    }
  }

  async function onReject(id: string) {
    setBusyId(id)
    setError(null)
    try {
      const result = await rejectArchitectApplication(id, reason.trim() || undefined)
      setRejectId(null)
      setReason('')
      await refresh()
      if (result.email_sent === false) {
        setError('Request rejected. The rejection email could not be sent.')
      }
    } catch (err: unknown) {
      const ax = err as { response?: { data?: { detail?: string } } }
      setError(ax.response?.data?.detail || 'Could not reject request')
    } finally {
      setBusyId(null)
    }
  }

  const architects = users.filter(u => u.role === 'ARCHITECT')

  return (
    <WorkflowShell>
      <div className="studio-home">
        <p className="wf-hint">Account approval and audit. No canvas editing.</p>
        {error && <div className="error-msg" role="alert">{error}</div>}
        <div className="studio-overview">
          <StatCard label="Clients" value={clients} to="/it/clients" />
          <StatCard label="Architects" value={architects.length} to="/it/architects" />
          <StatCard label="Analytics" value={users.length} to="/it/analytics" />
          <StatCard label="Audit trail" value={auditCount} to="/it/history" />
        </div>
        <section className="studio-section">
          <h2 className="studio-section-title">Architect registration requests</h2>
          {applications.length === 0 ? (
            <p className="wf-hint">No architect requests.</p>
          ) : (
            <ol className="studio-register">
              {applications.map(row => (
                <li key={row.id} className="studio-row studio-row-static">
                  <span className="studio-row-copy">
                    <span className="studio-row-name">{row.full_name}</span>
                    <span className="studio-row-status">{row.email} · {row.status.replace(/_/g, ' ')}</span>
                    {row.information && <span className="wf-hint">{row.information}</span>}
                  </span>
                  {row.status === 'PENDING_APPROVAL' && (
                    <div className="studio-toolbar">
                      <button className="wf-action" type="button" disabled={busyId === row.id} onClick={() => void onApprove(row.id)}>
                        Approve
                      </button>
                      <button className="wf-action" type="button" disabled={busyId === row.id} onClick={() => setRejectId(row.id)}>
                        Reject
                      </button>
                    </div>
                  )}
                  {rejectId === row.id && (
                    <div className="studio-stack">
                      <label htmlFor={`reject-${row.id}`}>Reason</label>
                      <input id={`reject-${row.id}`} value={reason} onChange={e => setReason(e.target.value)} />
                      <button className="catalog-generate-btn" type="button" disabled={busyId === row.id} onClick={() => void onReject(row.id)}>
                        Confirm reject
                      </button>
                    </div>
                  )}
                </li>
              ))}
            </ol>
          )}
        </section>
      </div>
    </WorkflowShell>
  )
}
