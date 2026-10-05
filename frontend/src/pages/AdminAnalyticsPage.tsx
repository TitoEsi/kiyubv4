import { useEffect, useMemo, useState } from 'react'
import WorkflowShell from './WorkflowShell'
import StatCard from '../components/StatCard'
import { AuditEvent, listAccounts, listAudit, listProjects, Project, WorkflowUser } from '../workflow/api'

export default function AdminAnalyticsPage() {
  const [users, setUsers] = useState<WorkflowUser[]>([])
  const [projects, setProjects] = useState<Project[]>([])
  const [audit, setAudit] = useState<AuditEvent[]>([])
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    Promise.all([listAccounts(), listProjects().catch(() => []), listAudit().catch(() => [])])
      .then(([accounts, nextProjects, nextAudit]) => {
        setUsers(accounts)
        setProjects(nextProjects)
        setAudit(nextAudit)
      })
      .catch(e => setError(String(e)))
  }, [])

  const stats = useMemo(() => {
    const architects = users.filter(u => u.role === 'ARCHITECT')
    const clients = users.filter(u => u.role === 'CLIENT')
    return {
      projects: projects.length,
      active: projects.filter(p => p.status !== 'PUBLISHED' && p.status !== 'DRAFT').length,
      published: projects.filter(p => p.status === 'PUBLISHED').length,
      clients: clients.length,
      architects: architects.length,
      suspended: architects.filter(u => u.suspended).length,
      reviews: audit.filter(e => e.event_type.includes('REVIEW') || e.event_type.includes('APPROVED')).length,
      events: audit.length,
    }
  }, [users, projects, audit])

  return (
    <WorkflowShell>
      <div className="studio-home">
        <header className="studio-page-head">
          <div>
            <p className="studio-meta">Operations</p>
            <h1 className="studio-page-title">Analytics</h1>
          </div>
        </header>
        {error && <div className="error-msg" role="alert">{error}</div>}
        {users.length === 0 && projects.length === 0 && audit.length === 0 && (
          <p className="wf-hint">No analytics yet. Counts appear when accounts, projects, or audit events exist.</p>
        )}
        <div className="studio-overview">
          <StatCard label="Projects" value={stats.projects} to="/admin/projects" />
          <StatCard label="Active projects" value={stats.active} to="/admin/projects" />
          <StatCard label="Published" value={stats.published} to="/admin/projects" />
          <StatCard label="Clients" value={stats.clients} to="/admin/clients" />
          <StatCard label="Architects" value={stats.architects} to="/admin/architects" />
          <StatCard label="Suspended" value={stats.suspended} to="/admin/architects" />
          <StatCard label="Review events" value={stats.reviews} to="/admin/history" />
          <StatCard label="Audit events" value={stats.events} to="/admin/history" />
        </div>
      </div>
    </WorkflowShell>
  )
}
