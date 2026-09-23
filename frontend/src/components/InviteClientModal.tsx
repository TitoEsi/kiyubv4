import { FormEvent, useState } from 'react'
import { inviteClient, Invitation, Project } from '../workflow/api'

export default function InviteClientModal({
  projects,
  onClose,
  onSent,
}: {
  projects: Project[]
  onClose: () => void
  onSent: (invite: Invitation) => void
}) {
  const [projectId, setProjectId] = useState(projects[0]?.id || '')
  const [email, setEmail] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [sent, setSent] = useState<Invitation | null>(null)
  const [loading, setLoading] = useState(false)

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    if (!projectId) {
      setError('Select a project')
      return
    }
    setLoading(true)
    setError(null)
    try {
      const invite = await inviteClient(projectId, email)
      setSent(invite)
      onSent(invite)
    } catch (err: unknown) {
      const ax = err as { response?: { data?: { detail?: string }; status?: number } }
      if (ax.response?.status === 409) {
        try {
          const invite = await inviteClient(projectId, email, true)
          setSent(invite)
          onSent(invite)
          return
        } catch (retry: unknown) {
          const rx = retry as { response?: { data?: { detail?: string } } }
          setError(rx.response?.data?.detail || 'Could not resend invitation')
        }
      } else {
        setError(ax.response?.data?.detail || 'Could not send invitation')
      }
    } finally {
      setLoading(false)
    }
  }

  const href = sent?.invite_url ? `${window.location.origin}${sent.invite_url}` : ''

  return (
    <div className="studio-modal-backdrop" role="presentation" onClick={onClose}>
      <div className="studio-modal" role="dialog" aria-labelledby="invite-title" onClick={e => e.stopPropagation()}>
        <p className="studio-meta">Invitation</p>
        <h2 id="invite-title">Invite client</h2>
        {sent ? (
          <div className="studio-stack">
            <p>Invitation is {sent.status.toLowerCase()} for {sent.email}.</p>
            <p className="wf-hint">Share this link. KIYUB does not send email from this environment.</p>
            <label htmlFor="invite-link">Invite link</label>
            <input id="invite-link" readOnly value={href} />
            <div className="studio-toolbar">
              <button
                type="button"
                className="catalog-generate-btn"
                onClick={() => { if (href) void navigator.clipboard.writeText(href) }}
              >
                Copy link
              </button>
              <button type="button" className="back-btn" onClick={onClose}>Done</button>
            </div>
          </div>
        ) : (
          <form className="studio-stack" onSubmit={onSubmit}>
            {error && <div className="error-msg" role="alert">{error}</div>}
            <label htmlFor="invite-project">Project</label>
            <select id="invite-project" value={projectId} onChange={e => setProjectId(e.target.value)} required>
              <option value="">Select project</option>
              {projects.map(p => (
                <option key={p.id} value={p.id}>{p.name}</option>
              ))}
            </select>
            <label htmlFor="invite-email">Client email</label>
            <input
              id="invite-email"
              type="email"
              value={email}
              onChange={e => setEmail(e.target.value)}
              placeholder="client@studio.local"
              required
            />
            <div className="studio-toolbar">
              <button className="catalog-generate-btn" type="submit" disabled={loading || !projects.length}>
                {loading ? 'Sending…' : 'Send invitation'}
              </button>
              <button type="button" className="back-btn" onClick={onClose}>Cancel</button>
            </div>
          </form>
        )}
      </div>
    </div>
  )
}
