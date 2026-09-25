import { useEffect, useState } from 'react'
import WorkflowShell from './WorkflowShell'
import ProjectRegister from './ProjectRegister'
import { listProjects, Project } from '../workflow/api'

export default function AdminProjectsPage() {
  const [projects, setProjects] = useState<Project[]>([])
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    listProjects().then(setProjects).catch(e => setError(String(e)))
  }, [])

  return (
    <WorkflowShell>
      <div className="studio-home">
        <header className="studio-page-head">
          <div>
            <p className="studio-meta">Register</p>
            <h1 className="studio-page-title">Projects</h1>
          </div>
        </header>
        {error && <div className="error-msg" role="alert">{error}</div>}
        <ProjectRegister projects={projects} empty="No projects." />
      </div>
    </WorkflowShell>
  )
}
