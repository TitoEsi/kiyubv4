import { useEffect, useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { ArrowLeft } from '@phosphor-icons/react'
import WorkflowShell from './WorkflowShell'
import { getProject, listProjectActivity, type ActivityEntry, type Project } from '../workflow/api'
import { activityItems } from '../workflow/activityItems'
import { statusLabel } from '../workflow/statusLabels'

/** Immutable, project-wide history shared by the Architect and the Client. */
export default function ProjectActivityPage() {
  const { projectId } = useParams()
  const [project, setProject] = useState<Project | null>(null)
  const [entries, setEntries] = useState<ActivityEntry[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!projectId) return
    setEntries(null)
    Promise.all([getProject(projectId), listProjectActivity(projectId)])
      .then(([detail, activity]) => {
        setProject(detail.project)
        setEntries(activity)
      })
      .catch(() => setError('Could not load project activity.'))
  }, [projectId])

  const items = useMemo(() => activityItems(entries || []), [entries])

  return (
    <WorkflowShell status={statusLabel(project?.status) || undefined}>
      <div className="studio-home project-activity">
        <header className="studio-page-head">
          <div>
            <Link className="wf-link project-activity-back" to={`/projects/${projectId}`}>
              <ArrowLeft size={14} aria-hidden /> Back to Project
            </Link>
            <p className="studio-meta">{project?.name || 'Project'}</p>
            <h1 className="studio-page-title">Project Activity</h1>
          </div>
        </header>
        {error && <div className="error-msg" role="alert">{error}</div>}
        {entries === null && !error ? (
          <p className="wf-hint">Loading activity…</p>
        ) : items.length === 0 ? (
          <p className="wf-hint">No activity yet.</p>
        ) : (
          <ol className="activity-list" aria-label="Project activity">
            {items.map(item => (
              <li key={item.id} className="activity-item">
                <p className="activity-title">{item.title}</p>
                <p className="activity-meta">{item.actor} · <time>{item.when}</time></p>
                {item.context && <p className="activity-context">{item.context.label}: “{item.context.text}”</p>}
                {item.quote && <blockquote className="activity-quote">“{item.quote}”</blockquote>}
                {item.resolution && <p className="activity-resolution">Resolution: {item.resolution}</p>}
                {item.implementedIn != null && <p className="activity-meta">Implemented in Version {item.implementedIn}</p>}
                {item.changes.length > 0 && (
                  <ul className="activity-changes" aria-label="Changes">
                    {item.changes.map((c, i) => <li key={i}>{c}</li>)}
                  </ul>
                )}
                {item.version && (
                  item.version.viewable ? (
                    <Link className="wf-link activity-version" to={`/projects/${projectId}?version=${item.version.revisionId}`}>
                      View Version {item.version.number}
                    </Link>
                  ) : (
                    <p className="activity-meta">Version {item.version.number}</p>
                  )
                )}
              </li>
            ))}
          </ol>
        )}
      </div>
    </WorkflowShell>
  )
}
