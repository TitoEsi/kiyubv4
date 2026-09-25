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
        setStatus(info.status)
        setNeedsRegistration(info.needs_registration)
      })
      .catch(() => setError('This invitation is invalid or has expired.'))
      .finally(() => setReady(true))
  }, [token])

  async function finishAccept() {
    if (!token) return
    const result = await acceptInvitation(token)
    nav(result.project?.id ? `/projects/${result.project.id}` : '/client')
  }

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    if (!token) return
    const completing = needsRegistration || !user || user.email.toLowerCase() !== email.toLowerCase()
    if (completing && password !== confirm) {
      setError('Passwords do not match.')
      return
    }
    if (completing && !agreed) {
      setError('Agree to the Terms and Privacy Policy to continue.')
      return
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
      if (user && user.email.toLowerCase() === email.toLowerCase()) {
        await finishAccept()
        return
      }
      if (user && user.email.toLowerCase() !== email.toLowerCase()) {
        logout()
      }
      const next = await apiLogin(email, password)
      applySession(next.token, next.user)
      const result = await acceptInvitation(token)
      nav(result.project?.id ? `/projects/${result.project.id}` : '/client')
    } catch (err: unknown) {
      const ax = err as { response?: { data?: { detail?: string } } }
      setError(ax.response?.data?.detail || 'Could not complete your account')
    } finally {
      setLoading(false)
    }
  }

  const blocked = status && status !== 'PENDING'

  return (
    <WorkflowShell>
      <div className="studio-home">
        <p className="studio-meta">Client invitation</p>
        <h1 className="studio-page-title">Complete Your Account</h1>
        {!ready && <p className="wf-hint">Loading invitation…</p>}
        {error && <div className="error-msg" role="alert">{error}</div>}
        {ready && blocked && (
          <p>This invitation is {status.toLowerCase()} and can no longer be used.</p>
        )}
        {ready && !blocked && (
          <form className="studio-stack" onSubmit={onSubmit}>
            <p>
              {needsRegistration
                ? `You have been invited to KIYUB to work on ${projectName}. Create your password to continue. Accepting creates the project.`
                : `Sign in as ${email} to accept. Accepting creates the project.`}
            </p>
            <label htmlFor="invite-email">Email</label>
            <input id="invite-email" value={email} readOnly />
            {needsRegistration && (
              <>
                <label htmlFor="invite-name">Full name</label>
                <input
                  id="invite-name"
                  value={fullName}
                  onChange={e => setFullName(e.target.value)}
                  required
                />
              </>
            )}
            {(needsRegistration || !user || user.email.toLowerCase() !== email.toLowerCase()) && (
              <>
                <label htmlFor="invite-password">{needsRegistration ? 'Password' : 'Password'}</label>
                <PasswordField
                  id="invite-password"
                  value={password}
                  onChange={setPassword}
                  autoComplete={needsRegistration ? 'new-password' : 'current-password'}
                  required
                />
                {needsRegistration && (
                  <>
                    <label htmlFor="invite-confirm">Confirm password</label>
                    <PasswordField
                      id="invite-confirm"
                      value={confirm}
                      onChange={setConfirm}
                      autoComplete="new-password"
                      required
                    />
                  </>
                )}
                <TermsAgree id="invite-terms" checked={agreed} onChange={setAgreed} />
              </>
            )}
            <button className="catalog-generate-btn" type="submit" disabled={loading}>
              {loading ? 'Continuing…' : needsRegistration ? 'Complete account' : 'Accept invitation'}
            </button>
          </form>
        )}
      </div>
    </WorkflowShell>
  )
}
