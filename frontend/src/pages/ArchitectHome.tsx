import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import GreetingBanner from '../components/GreetingBanner'
import InviteClientModal from '../components/InviteClientModal'
import StatCard from '../components/StatCard'
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

  return (
    <WorkflowShell>
      {error && <div className="error-msg" role="alert">{error}</div>}
      <div className="studio-home">
        <GreetingBanner lede="Ready to review your projects?" />
        <div className="studio-overview">
          <StatCard label="Projects" value={projects.length} to="/architect/projects" />
          <StatCard label="Clients" value={clientCount} to="/architect/clients" />
          <StatCard label="Pending invites" value={pendingInvites} to="/architect/invitations" />
          <StatCard label="Unread" value={notes.filter(n => !n.read).length} />
        </div>
        <div className="studio-toolbar">
          <button type="button" className="catalog-generate-btn" onClick={() => setInviteOpen(true)}>
            Invite client
          </button>
          <Link className="wf-link" to="/architect/history">History</Link>
        </div>
        <ProjectRegister
          projects={recent}
          notes={notes}
          architect
          empty="Invite a client. The project appears here after they accept."
        />
      </div>
      {inviteOpen && (
        <InviteClientModal
          onClose={() => setInviteOpen(false)}
          onSent={() => { void refresh() }}
        />
      )}
    </WorkflowShell>
  )
}
