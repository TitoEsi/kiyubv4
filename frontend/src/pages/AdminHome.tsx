import { FormEvent, useEffect, useState } from 'react'
import StatCard from '../components/StatCard'
import WorkflowShell from './WorkflowShell'
import {
  ArchitectApplication,
  approveArchitectApplication,
  createArchitectApplication,
  listAccounts,
  listArchitectApplications,
  listArchitectClients,
  listAudit,
  listProjects,
  Project,
  rejectArchitectApplication,
  WorkflowUser,
} from '../workflow/api'

function detail(err: unknown, fallback: string) {
  const ax = err as { response?: { data?: { detail?: string } } }
  return ax.response?.data?.detail || fallback
}

export default function AdminHome() {
  const [projects, setProjects] = useState<Project[]>([])
  const [clients, setClients] = useState(0)
  const [users, setUsers] = useState<WorkflowUser[]>([])
  const [applications, setApplications] = useState<ArchitectApplication[]>([])
  const [auditCount, setAuditCount] = useState(0)
  const [email, setEmail] = useState('')
  const [fullName, setFullName] = useState('')
  const [information, setInformation] = useState('')
  const [sent, setSent] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [busyId, setBusyId] = useState<string | null>(null)
  const [rejectId, setRejectId] = useState<string | null>(null)
  const [reason, setReason] = useState('')

  async function refresh() {
    const [nextProjects, accounts, clientRows, apps, audit] = await Promise.all([
      listProjects(),
      listAccounts(),
      listArchitectClients().catch(() => []),
      listArchitectApplications().catch(() => []),
      listAudit().catch(() => []),
    ])
    setProjects(nextProjects)
    setUsers(accounts)
    setClients(new Set(clientRows.map(c => c.email)).size)
    setApplications(apps)
    setAuditCount(audit.length)
  }

  useEffect(() => {
    refresh().catch(e => setError(String(e)))
  }, [])

  async function onInvite(e: FormEvent) {
    e.preventDefault()
    setLoading(true)
    setError(null)
    setSent(false)
    try {
      await createArchitectApplication(email, fullName, information.trim() || undefined)
      setSent(true)
      setEmail('')
      setFullName('')
      setInformation('')
    } catch (err: unknown) {
      setError(detail(err, 'Unable to send invitation. Please try again.'))
    } finally {
      await refresh().catch(() => undefined)
      setLoading(false)
    }
  }

  async function onApprove(id: string) {
    setBusyId(id)
    setError(null)
    try {
      await approveArchitectApplication(id)
      await refresh()
    } catch (err: unknown) {
      setError(detail(err, 'Unable to send invitation. Please try again.'))
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
      setError(detail(err, 'Could not reject request'))
    } finally {
      setBusyId(null)
    }
  }

  const architects = users.filter(u => u.role === 'ARCHITECT')

  return (
    <WorkflowShell>
      <div className="studio-home">
        <p className="wf-hint">Accounts, architect onboarding, projects, and audit. Project canvases are view-only for Admin.</p>
        {error && <div className="error-msg" role="alert">{error}</div>}
        <div className="studio-overview">
          <StatCard label="Projects" value={projects.length} to="/admin/projects" />
          <StatCard label="Clients" value={clients} to="/admin/clients" />
          <StatCard label="Architects" value={architects.length} to="/admin/architects" />
          <StatCard label="Analytics" value={users.length} to="/admin/analytics" />
          <StatCard label="Audit trail" value={auditCount} to="/admin/history" />
        </div>
        {sent && <p role="status">Architect invitation sent.</p>}
        <section className="studio-section">
          <h2 className="studio-section-title">Invite architect</h2>
          <form className="studio-stack" onSubmit={onInvite}>
            <label htmlFor="arch-invite-email">Email</label>
            <input id="arch-invite-email" type="email" value={email} onChange={e => setEmail(e.target.value)} required />
            <label htmlFor="arch-invite-name">Name</label>
            <input id="arch-invite-name" value={fullName} onChange={e => setFullName(e.target.value)} required />
            <label htmlFor="arch-invite-info">Architect information</label>
            <textarea id="arch-invite-info" value={information} onChange={e => setInformation(e.target.value)} rows={3} />
            <button className="catalog-generate-btn" type="submit" disabled={loading}>
              {loading ? 'Sending…' : 'Send invitation'}
            </button>
          </form>
        </section>
        <section className="studio-section">
          <h2 className="studio-section-title">Architect requests</h2>
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
