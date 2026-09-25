import { useEffect, useMemo, useState } from 'react'
import { Link, useLocation, useNavigate, useParams } from 'react-router-dom'
import ConfirmDialog from '../components/ConfirmDialog'
import WorkflowShell from './WorkflowShell'
import { useAuth } from '../workflow/auth'
import {
  AuditEvent,
  deleteAccount,
  listAccounts,
  listArchitectClients,
  listAudit,
  listProjects,
  patchAccount,
  Project,
  WorkflowUser,
} from '../workflow/api'
import { displayNameFromEmail, formatDate } from '../workflow/displayName'

function statusOf(u: WorkflowUser) {
  if (u.deleted_at) return 'Deleted'
  if (u.suspended) return 'Suspended'
  if (!u.approved) return 'Pending'
  return 'Active'
}

export default function ArchitectProfilePage() {
  const { userId } = useParams()
  const { user: actor } = useAuth()
  const nav = useNavigate()
  const loc = useLocation()
  const listPath = loc.pathname.startsWith('/it') ? '/it/architects' : '/admin/architects'
  const isAdmin = actor?.role === 'MAIN_ADMIN'
  const isIT = actor?.role === 'IT_PERSONNEL'
  const [profile, setProfile] = useState<WorkflowUser | null>(null)
  const [projects, setProjects] = useState<Project[]>([])
  const [audit, setAudit] = useState<AuditEvent[]>([])
  const [clientCount, setClientCount] = useState(0)
  const [error, setError] = useState<string | null>(null)
  const [confirm, setConfirm] = useState<'suspend' | 'delete' | null>(null)

  useEffect(() => {
    if (!userId) return
    Promise.all([
      listAccounts(),
      listProjects().catch(() => []),
      listAudit().catch(() => []),
      listArchitectClients().catch(() => []),
    ]).then(([accounts, nextProjects, nextAudit, clients]) => {
      setProfile(accounts.find(u => u.id === userId) || null)
      setProjects(nextProjects.filter(p => p.architect_id === userId))
      setAudit(nextAudit.filter(e => e.actor_id === userId || e.target === userId))
      setClientCount(new Set(clients.filter(c => c.architect_id === userId).map(c => c.email)).size)
    }).catch(e => setError(String(e)))
  }, [userId])

  const recent = useMemo(() => audit.slice(0, 12), [audit])

  async function onSuspend() {
    if (!profile) return
    try {
      const next = await patchAccount(profile.id, { suspended: true })
      setProfile(next)
      setConfirm(null)
    } catch (err: unknown) {
      const ax = err as { response?: { data?: { detail?: string } } }
      setError(ax.response?.data?.detail || 'Could not suspend architect')
      setConfirm(null)
    }
  }

  async function onDelete() {
    if (!profile) return
    try {
      await deleteAccount(profile.id)
      setConfirm(null)
      nav(listPath)
    } catch (err: unknown) {
      const ax = err as { response?: { data?: { detail?: string } } }
      setError(ax.response?.data?.detail || 'Could not delete profile')
      setConfirm(null)
    }
  }

  return (
    <WorkflowShell>
      <div className="studio-home">
        <header className="studio-page-head">
          <div>
            <p className="studio-meta">Architect</p>
            <h1 className="studio-page-title">{profile ? (profile.full_name || displayNameFromEmail(profile.email)) : 'Profile'}</h1>
          </div>
          <Link className="wf-link" to={listPath}>Back</Link>
        </header>
        {error && <div className="error-msg" role="alert">{error}</div>}
        {!profile ? (
          <p className="wf-hint">Architect not found.</p>
        ) : (
          <>
            <dl className="studio-contact-dl">
              <div><dt>Email</dt><dd>{profile.email}</dd></div>
              <div><dt>Status</dt><dd>{statusOf(profile)}</dd></div>
              <div><dt>Joined</dt><dd>{formatDate(profile.created_at) || '—'}</dd></div>
              <div><dt>Projects</dt><dd>{projects.length}</dd></div>
              <div><dt>Clients</dt><dd>{clientCount}</dd></div>
            </dl>
            <div className="studio-toolbar">
              {isAdmin && !profile.suspended && (
                <button type="button" className="catalog-generate-btn" onClick={() => setConfirm('suspend')}>
                  Suspend architect
                </button>
              )}
              {isIT && profile.suspended && (
                <button type="button" className="catalog-generate-btn" onClick={() => setConfirm('delete')}>
                  Delete profile
                </button>
              )}
            </div>
            <section className="studio-section">
              <h2 className="studio-section-title">Projects</h2>
              {projects.length === 0 ? <p className="wf-hint">No projects.</p> : (
                <ul className="studio-notes">
                  {projects.map(p => (
                    <li key={p.id} className="studio-note">
                      <Link to={`/projects/${p.id}`}>{p.name}</Link>
                      <span className="studio-row-activity">{p.status}</span>
                    </li>
                  ))}
                </ul>
              )}
            </section>
            <section className="studio-section">
              <h2 className="studio-section-title">Recent activity</h2>
              {recent.length === 0 ? <p className="wf-hint">No activity recorded.</p> : (
                <ul className="studio-notes">
                  {recent.map(e => (
                    <li key={e.id} className="studio-note">
                      <span>{e.event_type.replace(/_/g, ' ')}</span>
                      <span className="studio-row-activity">{formatDate(e.created_at)}</span>
                    </li>
                  ))}
                </ul>
              )}
            </section>
          </>
        )}
      </div>
      {confirm === 'suspend' && (
        <ConfirmDialog
          title="Suspend architect"
          body="This architect will lose access. Projects and history stay in place."
          confirmLabel="Suspend"
          danger
          onConfirm={() => void onSuspend()}
          onCancel={() => setConfirm(null)}
        />
      )}
      {confirm === 'delete' && (
        <ConfirmDialog
          title="Delete suspended profile"
          body="This removes the architect profile from directories. Project and audit history are kept."
          confirmLabel="Delete profile"
          danger
          onConfirm={() => void onDelete()}
          onCancel={() => setConfirm(null)}
        />
      )}
    </WorkflowShell>
  )
}
