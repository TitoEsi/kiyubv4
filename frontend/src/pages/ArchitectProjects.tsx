import { FormEvent, useEffect, useMemo, useState } from 'react'
import WorkflowShell from './WorkflowShell'
import ProjectRegister from './ProjectRegister'
import { createProject, listNotifications, listProjects, Notification, Project } from '../workflow/api'
import { filterAndSortProjects, ProjectSort } from '../workflow/projectQuery'

export default function ArchitectProjects() {
  const [projects, setProjects] = useState<Project[]>([])
  const [notes, setNotes] = useState<Notification[]>([])
  const [query, setQuery] = useState('')
  const [sort, setSort] = useState<ProjectSort>('updated')
  const [name, setName] = useState('')
  const [error, setError] = useState<string | null>(null)

  async function refresh() {
    setProjects(await listProjects())
    setNotes(await listNotifications())
  }

  useEffect(() => {
    refresh().catch(e => setError(String(e)))
  }, [])

  const visible = useMemo(() => filterAndSortProjects(projects, query, sort), [projects, query, sort])

  async function onCreate(e: FormEvent) {
    e.preventDefault()
    const trimmed = name.trim()
    if (!trimmed) return
    try {
      await createProject(trimmed)
      setName('')
      await refresh()
    } catch (err: unknown) {
      const ax = err as { response?: { data?: { detail?: string } } }
      setError(ax.response?.data?.detail || 'Could not create project')
    }
  }

  const empty = query
    ? 'Try another search term or clear your filters.'
    : 'Once you create or are assigned a project, it will appear here.'

  return (
    <WorkflowShell title="Projects">
      {error && <div className="error-msg" role="alert">{error}</div>}
      <div className="studio-home">
        <header className="studio-page-head">
          <div>
            <p className="studio-meta">Register</p>
            <h1 className="studio-page-title">Projects</h1>
          </div>
          <form className="studio-inline-create" onSubmit={onCreate}>
            <label htmlFor="new-project-name" className="sr-only">New project</label>
            <input id="new-project-name" value={name} onChange={e => setName(e.target.value)} placeholder="New project name" />
            <button className="catalog-generate-btn" type="submit">Create</button>
          </form>
        </header>
        <div className="studio-toolbar studio-toolbar-wrap">
          <label className="sr-only" htmlFor="project-search">Search projects</label>
          <input
            id="project-search"
            value={query}
            onChange={e => setQuery(e.target.value)}
            placeholder="Search projects..."
          />
          <label className="studio-sort">
            Sort
            <select value={sort} onChange={e => setSort(e.target.value as ProjectSort)}>
              <option value="updated">Recently updated</option>
              <option value="newest">Newest</option>
              <option value="oldest">Oldest</option>
              <option value="name-asc">Project name A–Z</option>
              <option value="name-desc">Project name Z–A</option>
              <option value="status">Status</option>
            </select>
          </label>
        </div>
        <ProjectRegister
          projects={visible}
          notes={notes}
          architect
          emptyTitle={query ? 'No projects found' : 'No projects yet'}
          empty={empty}
        />
      </div>
    </WorkflowShell>
  )
}
