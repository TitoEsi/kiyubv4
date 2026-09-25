import { FormEvent, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import StatCard from '../components/StatCard'
import WorkflowShell from './WorkflowShell'
import {
  ArchitectApplication,
  createArchitectApplication,
  listAccounts,
  listArchitectApplications,
  listArchitectClients,
  listProjects,
  Project,
  WorkflowUser,
} from '../workflow/api'

export default function AdminHome() {
  const [projects, setProjects] = useState<Project[]>([])
  const [clients, setClients] = useState(0)
  const [architects, setArchitects] = useState<WorkflowUser[]>([])
  const [applications, setApplications] = useState<ArchitectApplication[]>([])
  const [email, setEmail] = useState('')
  const [fullName, setFullName] = useState('')
  const [information, setInformation] = useState('')
  const [sent, setSent] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  async function refresh() {
    const [nextProjects, accounts, clientRows, apps] = await Promise.all([
      listProjects(),
      listAccounts(),
      listArchitectClients().catch(() => []),
      listArchitectApplications().catch(() => []),
    ])
    setProjects(nextProjects)
    setArchitects(accounts.filter(u => u.role === 'ARCHITECT'))
    setClients(new Set(clientRows.map(c => c.email)).size)
    setApplications(apps)
  }

  useEffect(() => {
    refresh().catch(() => undefined)
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
      await refresh()
    } catch (err: unknown) {
      const ax = err as { response?: { data?: { detail?: string } } }
      setError(ax.response?.data?.detail || 'Unable to send invitation. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <WorkflowShell>
      <div className="studio-home">
        <p className="wf-hint">Oversight only — the architectural canvas is not available here.</p>
        {error && <div className="error-msg" role="alert">{error}</div>}
        <div className="studio-overview">
          <StatCard label="Projects" value={projects.length} to="/admin/projects" />
          <StatCard label="Clients" value={clients} to="/admin/clients" />
          <StatCard label="Architects" value={architects.length} to="/admin/architects" />
        </div>
        <div className="studio-toolbar">
          <Link className="wf-link" to="/admin/history">History</Link>
        </div>
        {sent && <p>Architect registration request sent for IT approval.</p>}
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
              {loading ? 'Sending…' : 'Send for IT approval'}
            </button>
          </form>
        </section>
        {applications.length > 0 && (
          <section className="studio-section">
            <h2 className="studio-section-title">Architect requests</h2>
            <ol className="studio-notes">
              {applications.slice(0, 8).map(row => (
                <li key={row.id} className="studio-note">
                  <span>{row.full_name} · {row.email}</span>
                  <span className="studio-row-activity">{row.status.replace(/_/g, ' ')}</span>
                </li>
              ))}
            </ol>
          </section>
        )}
      </div>
    </WorkflowShell>
  )
}
