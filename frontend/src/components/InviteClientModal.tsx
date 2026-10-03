import { FormEvent, useState } from 'react'
import { inviteClient, Invitation } from '../workflow/api'

export default function InviteClientModal({
  onClose,
  onSent,
  initialEmail = '',
}: {
  onClose: () => void
  onSent: (invite: Invitation) => void
  initialEmail?: string
}) {
  const [email, setEmail] = useState(initialEmail)
  const [projectName, setProjectName] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [sent, setSent] = useState<Invitation | null>(null)
  const [loading, setLoading] = useState(false)

  async function send(resend = false) {
    return inviteClient(email, projectName.trim() || undefined, resend)
  }

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    setLoading(true)
    setError(null)
    try {
      const invite = await send(false)
      setSent(invite)
      onSent(invite)
    } catch (err: unknown) {
      const ax = err as { response?: { data?: { detail?: string }; status?: number } }
      if (ax.response?.status === 409) {
        try {
          const invite = await send(true)
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
  const returning = sent?.existing_client === true

  return (
    <div className="studio-modal-backdrop" role="presentation" onClick={onClose}>
      <div className="studio-modal" role="dialog" aria-labelledby="invite-title" onClick={e => e.stopPropagation()}>
        <p className="studio-meta">Invitation</p>
        <h2 id="invite-title">{initialEmail ? 'Assign new project' : 'Invite client'}</h2>
        {sent ? (
          <div className="studio-stack">
            <p>Invitation sent successfully.</p>
            <p className="wf-hint">
              {returning
                ? `${sent.email} already has a KIYUB account. They can accept this invitation to open a new independent project.`
                : `KIYUB emailed ${sent.email}. The project appears after they complete their account.`}
              {' '}A backup link is available for development.
            </p>
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
            <label htmlFor="invite-email">Client email</label>
            <input
              id="invite-email"
              type="email"
              value={email}
              onChange={e => setEmail(e.target.value)}
              placeholder="client@studio.local"
              required
              readOnly={!!initialEmail}
            />
            <label htmlFor="invite-name">Project name (optional)</label>
            <input
              id="invite-name"
              value={projectName}
              onChange={e => setProjectName(e.target.value)}
              placeholder="Residence"
            />
            <div className="studio-toolbar">
              <button className="catalog-generate-btn" type="submit" disabled={loading}>
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
