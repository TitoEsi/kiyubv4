import { useEffect, useState } from 'react'
import WorkflowShell from './WorkflowShell'
import ProjectRegister from './ProjectRegister'
import { listAudit, listInquiries, listProjects, Inquiry, Project } from '../workflow/api'

function pad(n: number) {
  return String(n).padStart(2, '0')
}

export default function AdminHome() {
  const [projects, setProjects] = useState<Project[]>([])
  const [audit, setAudit] = useState<Array<{ id: string; event_type: string; created_at: string | null }>>([])
  const [inquiries, setInquiries] = useState<Inquiry[]>([])

  useEffect(() => {
    listProjects().then(setProjects)
    listAudit().then(setAudit)
    listInquiries().then(setInquiries).catch(() => undefined)
  }, [])

  return (
    <WorkflowShell title="Main admin" crumbs={[{ label: 'Projects' }]}>
      <div className="studio-home">
        <p className="wf-hint">Oversight only — the architectural canvas is not available here.</p>
        <ProjectRegister projects={projects} empty="No projects." />
        <section className="studio-section">
          <h2 className="studio-section-title">Access requests</h2>
          {inquiries.length === 0 ? (
            <p className="wf-hint">No inquiries yet.</p>
          ) : (
            <ol className="studio-notes">
              {inquiries.slice(0, 40).map((item, i) => (
                <li key={item.id} className="studio-note">
                  <span className="studio-index">{pad(i + 1)}</span>
                  <span>{item.name} · {item.email}</span>
                  <span className="studio-row-activity">{item.message}</span>
                </li>
              ))}
            </ol>
          )}
        </section>
        <section className="studio-section">
          <h2 className="studio-section-title">Recent audit</h2>
          <ol className="studio-notes">
            {audit.slice(0, 40).map((e, i) => (
              <li key={e.id} className="studio-note">
                <span className="studio-index">{pad(i + 1)}</span>
                <span>{e.event_type}</span>
                <span className="studio-row-activity">{e.created_at}</span>
              </li>
            ))}
          </ol>
        </section>
      </div>
    </WorkflowShell>
  )
}
