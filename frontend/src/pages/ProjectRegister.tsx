import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import FloorPlanPreview from '../components/FloorPlanPreview'
import { FloorPlan } from '../types/floorplan'
import { displayNameFromEmail, formatDate, formatRelative } from '../workflow/displayName'
import { floorPlanLabel } from '../workflow/projectQuery'
import { clientCommentCountLabel } from '../components/planAnnotations'
import { getProject, Notification, Project } from '../workflow/api'

export default function ProjectRegister({
  projects,
  notes = [],
  empty = 'No projects yet. They appear here when your architect assigns a project to you.',
  emptyTitle = 'No projects yet',
  architect = false,
  loading = false,
}: {
  projects: Project[]
  notes?: Notification[]
  empty?: string
  emptyTitle?: string
  architect?: boolean
  loading?: boolean
}) {
  const [previews, setPreviews] = useState<Record<string, FloorPlan | null>>({})

  useEffect(() => {
    let cancelled = false
    const ready = projects.filter(p => p.has_floor_plan)
    if (ready.length === 0) {
      setPreviews({})
      return () => { cancelled = true }
    }
    Promise.all(
      ready.map(p =>
        getProject(p.id)
          .then(d => [p.id, d.current_revision?.floor_plan ?? null] as const)
          .catch(() => [p.id, null] as const),
      ),
    ).then(rows => {
      if (!cancelled) setPreviews(Object.fromEntries(rows))
    })
    return () => { cancelled = true }
  }, [projects])

  if (loading) {
    return (
      <section className="studio-section">
        <h2 className="studio-section-title">Projects</h2>
        <ul className="studio-grid" aria-busy="true" aria-label="Loading projects">
          {[1, 2, 3].map(i => (
            <li key={i}>
              <article className="studio-tile studio-tile-skeleton">
                <div className="studio-tile-plate studio-skeleton-block" />
                <div className="studio-tile-copy">
                  <span className="studio-skeleton-line" />
                  <span className="studio-skeleton-line studio-skeleton-line-short" />
                </div>
              </article>
            </li>
          ))}
        </ul>
      </section>
    )
  }

  if (projects.length === 0) {
    return (
      <section className="studio-section">
        <h2 className="studio-section-title">Projects</h2>
        <div className="studio-empty">
          <div className="studio-login-plate" aria-hidden>
            <svg viewBox="0 0 320 220" fill="none">
              <rect x="1" y="1" width="318" height="218" stroke="currentColor" strokeOpacity="0.18" />
              <rect x="28" y="36" width="168" height="148" stroke="currentColor" strokeWidth="1.2" />
              <rect x="196" y="36" width="96" height="72" stroke="currentColor" strokeWidth="1.2" />
              <rect x="196" y="108" width="96" height="76" stroke="currentColor" strokeWidth="1.2" />
            </svg>
          </div>
          <p className="studio-empty-title">{emptyTitle}</p>
          <p className="studio-empty-copy">{empty}</p>
        </div>
      </section>
    )
  }

  return (
    <section className="studio-section">
      <h2 className="studio-section-title">Projects</h2>
      <ul className="studio-grid">
        {projects.map(p => {
          const plan = previews[p.id]
          const activity = notes.find(n => n.project_id === p.id)
          const updated = formatRelative(p.updated_at)
          const created = formatDate(p.created_at)
          const clientLabel = p.client_email ? displayNameFromEmail(p.client_email) : 'Unassigned'
          const commentLine = architect ? clientCommentCountLabel(p.client_comment_count || 0, !!p.has_floor_plan) : null
          return (
            <li key={p.id}>
              <article className="studio-tile">
                <div className="studio-tile-plate">
                  {plan ? (
                    <FloorPlanPreview plan={plan} width={280} height={160} />
                  ) : (
                    <span className="studio-plate-empty">{p.has_floor_plan ? 'Drawing' : 'No drawing yet'}</span>
                  )}
                </div>
                <div className="studio-tile-copy">
                  <h3 className="studio-tile-name">{p.name}</h3>
                  {architect && <p className="studio-tile-meta">Client: {clientLabel}</p>}
                  {architect && <p className="studio-tile-meta">Floor plan: {floorPlanLabel(p)}</p>}
                  {commentLine && <p className="studio-tile-meta">{commentLine}</p>}
                  <p className="studio-row-status">{p.status.replace(/_/g, ' ')}</p>
                  {created && architect && <p className="studio-tile-meta">Created {created}</p>}
                  {updated && <p className="studio-tile-meta">{updated}</p>}
                  {activity && <p className="studio-row-activity">{activity.message}</p>}
                  <Link className="studio-tile-open" to={`/projects/${p.id}`}>Open project</Link>
                </div>
              </article>
            </li>
          )
        })}
      </ul>
    </section>
  )
}
