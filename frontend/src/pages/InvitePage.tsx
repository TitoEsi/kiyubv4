import { FormEvent, useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import PasswordField from '../components/PasswordField'
import TermsAgree from '../components/TermsAgree'
import WorkflowShell from './WorkflowShell'
import { useAuth } from '../workflow/auth'
import { acceptInvitation, completeClientAccount, getInvitationByToken, login as apiLogin } from '../workflow/api'

export default function InvitePage() {
  const { token } = useParams()
  const nav = useNavigate()
  const { user, applySession, logout } = useAuth()
  const [email, setEmail] = useState('')
  const [fullName, setFullName] = useState('')
  const [projectName, setProjectName] = useState('')
  const [architectName, setArchitectName] = useState('')
  const [status, setStatus] = useState('')
  const [needsRegistration, setNeedsRegistration] = useState(true)
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [agreed, setAgreed] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [ready, setReady] = useState(false)

  useEffect(() => {
    if (!token) return
    getInvitationByToken(token)
      .then(info => {
        setEmail(info.email)
        setProjectName(info.project_name || 'KIYUB')
        setArchitectName(info.architect_name || 'your architect')
        setStatus(info.status)
        setNeedsRegistration(info.needs_registration)
      })
      .catch(() => setError('This invitation is invalid or has expired.'))
      .finally(() => setReady(true))
  }, [token])

  const invitedEmail = email.toLowerCase()
  const signedInAsInvitee = !!(user && user.email.toLowerCase() === invitedEmail)
  const wrongAccount = !!(user && invitedEmail && user.email.toLowerCase() !== invitedEmail)

  async function finishAccept() {
    if (!token) return
    const result = await acceptInvitation(token)
    nav(result.project?.id ? `/projects/${result.project.id}` : '/client')
  }

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    if (!token) return
    if (wrongAccount) {
      setError(`This invitation is for ${email}. Sign out and sign in as that client.`)
      return
    }
    if (needsRegistration) {
      if (password !== confirm) {
        setError('Passwords do not match.')
        return
      }
      if (!agreed) {
        setError('Agree to the Terms and Privacy Policy to continue.')
        return
      }
    }
    setLoading(true)
    setError(null)
    try {
      if (needsRegistration) {
        const data = await completeClientAccount(email, password, token, fullName.trim())
        if (data.token) applySession(data.token, data.user)
        nav(data.project?.id ? `/projects/${data.project.id}` : '/client')
        return
      }
      if (signedInAsInvitee) {
        await finishAccept()
        return
      }
      const next = await apiLogin(email, password)
      applySession(next.token, next.user)
      await finishAccept()
    } catch (err: unknown) {
      const ax = err as { response?: { data?: { detail?: string } } }
      setError(ax.response?.data?.detail || 'Could not accept this invitation')
    } finally {
      setLoading(false)
    }
  }

  const blocked = status && status !== 'PENDING'
  const title = needsRegistration ? 'Complete Your Account' : `You've been invited to a new project by ${architectName}`
  const lede = needsRegistration
    ? `You have been invited to KIYUB to work on ${projectName}. Create your password to continue. Accepting creates the project.`
    : `Project: ${projectName}. Accepting attaches this project to your existing account.`

  return (
    <WorkflowShell>
      <div className="studio-home">
        <p className="studio-meta">Client invitation</p>
        <h1 className="studio-page-title">{title}</h1>
        {!ready && <p className="wf-hint">Loading invitation…</p>}
        {error && <div className="error-msg" role="alert">{error}</div>}
        {ready && blocked && (
          <p>This invitation is {status.toLowerCase()} and can no longer be used.</p>
        )}
        {ready && !blocked && (
          <form className="studio-stack" onSubmit={onSubmit}>
            <p>{lede}</p>
            <label htmlFor="invite-email">Email</label>
            <input id="invite-email" value={email} readOnly />
            {wrongAccount && (
              <p className="wf-hint">
                You are signed in as {user?.email}. Sign out and sign in as {email} to accept.
              </p>
            )}
            {needsRegistration && (
              <>
                <label htmlFor="invite-name">Full name</label>
                <input
                  id="invite-name"
                  value={fullName}
                  onChange={e => setFullName(e.target.value)}
                  required
                />
                <label htmlFor="invite-password">Password</label>
                <PasswordField
                  id="invite-password"
                  value={password}
                  onChange={setPassword}
                  autoComplete="new-password"
                  required
                />
                <label htmlFor="invite-confirm">Confirm password</label>
                <PasswordField
                  id="invite-confirm"
                  value={confirm}
                  onChange={setConfirm}
                  autoComplete="new-password"
                  required
                />
                <TermsAgree id="invite-terms" checked={agreed} onChange={setAgreed} />
              </>
            )}
            {!needsRegistration && !signedInAsInvitee && !wrongAccount && (
              <>
                <label htmlFor="invite-password">Password</label>
                <PasswordField
                  id="invite-password"
                  value={password}
                  onChange={setPassword}
                  autoComplete="current-password"
                  required
                />
              </>
            )}
            <div className="studio-toolbar">
              {wrongAccount && (
                <button className="back-btn" type="button" onClick={() => logout()}>
                  Sign out
                </button>
              )}
              <button className="catalog-generate-btn" type="submit" disabled={loading || wrongAccount}>
                {loading ? 'Continuing…' : needsRegistration ? 'Complete account' : 'Accept invitation'}
              </button>
            </div>
          </form>
        )}
      </div>
    </WorkflowShell>
  )
}
