import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import GreetingBanner from '../components/GreetingBanner'
import GenerationGuide from '../components/GenerationGuide'
import WorkflowShell from './WorkflowShell'
import ProjectRegister from './ProjectRegister'
import {
  acceptInvitationById,
  declineInvitationById,
  Invitation,
  listInvitations,
  listNotifications,
  listProjects,
  Notification,
  Project,
} from '../workflow/api'
import { displayNameFromEmail } from '../workflow/displayName'

export default function ClientHome() {
  const nav = useNavigate()
  const [projects, setProjects] = useState<Project[]>([])
  const [invites, setInvites] = useState<Invitation[]>([])
  const [notes, setNotes] = useState<Notification[]>([])
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [busyId, setBusyId] = useState<string | null>(null)

  async function refresh() {
    const [p, n, inv] = await Promise.all([
      listProjects(),
      listNotifications().catch(() => [] as Notification[]),
      listInvitations().catch(() => [] as Invitation[]),
    ])
    setProjects(p)
    setNotes(n)
    setInvites(inv.filter(i => i.status === 'PENDING'))
  }

  useEffect(() => {
    let cancelled = false
    refresh()
      .catch(e => {
        if (!cancelled) setError(String(e))
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => { cancelled = true }
  }, [])

  async function onAccept(id: string) {
    setBusyId(id)
    setError(null)
    try {
      const result = await acceptInvitationById(id)
      await refresh()
      if (result.project?.id) nav(`/projects/${result.project.id}`)
    } catch (err: unknown) {
      const ax = err as { response?: { data?: { detail?: string } } }
      setError(ax.response?.data?.detail || 'Could not accept invitation')
    } finally {
      setBusyId(null)
    }
  }

  async function onDecline(id: string) {
    setBusyId(id)
    setError(null)
    try {
      await declineInvitationById(id)
      await refresh()
    } catch (err: unknown) {
      const ax = err as { response?: { data?: { detail?: string } } }
      setError(ax.response?.data?.detail || 'Could not decline invitation')
    } finally {
      setBusyId(null)
    }
  }

  return (
    <WorkflowShell>
      {error && <div className="error-msg" role="alert">{error}</div>}
      <div className="studio-home">
        <GreetingBanner />
        <div className="studio-toolbar">
          <Link className="wf-link" to="/client/history">History</Link>
        </div>
        <GenerationGuide />
        {invites.length > 0 && (
          <section className="studio-section">
            <h2 className="studio-section-title">Invitations</h2>
            <ul className="studio-notes">
              {invites.map(inv => (
                <li key={inv.id} className="studio-note">
                  <span>
                    {displayNameFromEmail(inv.architect_email || 'architect')} has invited you to work on {inv.project_name || 'a project'}.
                  </span>
                  <div className="studio-toolbar">
                    <button
                      type="button"
                      className="catalog-generate-btn"
                      disabled={busyId === inv.id}
                      onClick={() => void onAccept(inv.id)}
                    >
                      {busyId === inv.id ? 'Working…' : 'Accept'}
                    </button>
                    <button
                      type="button"
                      className="back-btn"
                      disabled={busyId === inv.id}
                      onClick={() => void onDecline(inv.id)}
                    >
                      Decline
                    </button>
                  </div>
                </li>
              ))}
            </ul>
          </section>
        )}
        <ProjectRegister
          projects={projects}
          notes={notes}
          loading={loading}
          empty="No projects yet. They appear here when you accept an architect invitation."
        />
      </div>
    </WorkflowShell>
  )
}
