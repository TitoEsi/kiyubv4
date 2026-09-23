import { useEffect, useMemo, useState } from 'react'
import GreetingBanner from '../components/GreetingBanner'
import InviteClientModal from '../components/InviteClientModal'
import WorkflowShell from './WorkflowShell'
import ProjectRegister from './ProjectRegister'
import { listArchitectClients, listNotifications, listProjects, Notification, Project } from '../workflow/api'
import { sortProjects } from '../workflow/projectQuery'

export default function ArchitectHome() {
  const [projects, setProjects] = useState<Project[]>([])
  const [notes, setNotes] = useState<Notification[]>([])
  const [clientCount, setClientCount] = useState(0)
  const [pendingInvites, setPendingInvites] = useState(0)
  const [error, setError] = useState<string | null>(null)
  const [inviteOpen, setInviteOpen] = useState(false)

  async function refresh() {
    const [nextProjects, nextNotes, clients] = await Promise.all([
      listProjects(),
      listNotifications(),
      listArchitectClients().catch(() => []),
    ])
    setProjects(nextProjects)
    setNotes(nextNotes)
    setClientCount(new Set(clients.map(c => c.email)).size)
    setPendingInvites(clients.filter(c => c.invitation_status === 'PENDING').length)
  }

  useEffect(() => {
    refresh().catch(e => setError(String(e)))
  }, [])

  const recent = useMemo(() => sortProjects(projects, 'updated').slice(0, 6), [projects])
  const activity = notes.slice(0, 5)

  return (
    <WorkflowShell title="Architect workspace">
      {error && <div className="error-msg" role="alert">{error}</div>}
      <div className="studio-home">
        <GreetingBanner lede="Ready to review your projects?" />
        <div className="studio-overview">
          <div>
            <p className="studio-meta">Projects</p>
            <p className="studio-stat">{projects.length}</p>
          </div>
          <div>
            <p className="studio-meta">Clients</p>
            <p className="studio-stat">{clientCount}</p>
          </div>
          <div>
            <p className="studio-meta">Pending invites</p>
            <p className="studio-stat">{pendingInvites}</p>
          </div>
          <div>
            <p className="studio-meta">Unread</p>
            <p className="studio-stat">{notes.filter(n => !n.read).length}</p>
          </div>
        </div>
        <div className="studio-toolbar">
          <button type="button" className="catalog-generate-btn" onClick={() => setInviteOpen(true)}>
            Invite client
          </button>
        </div>
        {activity.length > 0 && (
          <section className="studio-section">
            <h2 className="studio-section-title">Recent activity</h2>
            <ul className="studio-notes">
              {activity.map(n => (
                <li key={n.id} className="studio-note">
                  <span>{n.message}</span>
                </li>
              ))}
            </ul>
          </section>
        )}
        <ProjectRegister
          projects={recent}
          notes={notes}
          architect
          empty="Once you create a project, it will appear here."
        />
      </div>
      {inviteOpen && (
        <InviteClientModal
          projects={projects}
          onClose={() => setInviteOpen(false)}
          onSent={() => { void refresh() }}
        />
      )}
    </WorkflowShell>
  )
}
