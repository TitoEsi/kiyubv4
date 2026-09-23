import { useEffect, useState } from 'react'
import GreetingBanner from '../components/GreetingBanner'
import GenerationGuide from '../components/GenerationGuide'
import WorkflowShell from './WorkflowShell'
import ProjectRegister from './ProjectRegister'
import { listNotifications, listProjects, Notification, Project } from '../workflow/api'

export default function ClientHome() {
  const [projects, setProjects] = useState<Project[]>([])
  const [notes, setNotes] = useState<Notification[]>([])
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    Promise.all([listProjects(), listNotifications().catch(() => [] as Notification[])])
      .then(([p, n]) => {
        if (cancelled) return
        setProjects(p)
        setNotes(n)
      })
      .catch(e => {
        if (!cancelled) setError(String(e))
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => { cancelled = true }
  }, [])

  return (
    <WorkflowShell title="Client projects" crumbs={[{ label: 'Projects' }]}>
      {error && <div className="error-msg" role="alert">{error}</div>}
      <div className="studio-home">
        <GreetingBanner />
        <GenerationGuide />
        <ProjectRegister projects={projects} notes={notes} loading={loading} />
      </div>
    </WorkflowShell>
  )
}
