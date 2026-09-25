import { FormEvent, useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import PasswordField from '../components/PasswordField'
import TermsAgree from '../components/TermsAgree'
import WorkflowShell from './WorkflowShell'
import { useAuth } from '../workflow/auth'
import { completeArchitectApplication, getArchitectApplicationByToken } from '../workflow/api'

export default function ArchitectCompletePage() {
  const { token } = useParams()
  const nav = useNavigate()
  const { applySession } = useAuth()
  const [email, setEmail] = useState('')
  const [fullName, setFullName] = useState('')
  const [status, setStatus] = useState('')
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [agreed, setAgreed] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [ready, setReady] = useState(false)

  useEffect(() => {
    if (!token) return
    getArchitectApplicationByToken(token)
      .then(info => {
        setEmail(info.email)
        setFullName(info.full_name)
        setStatus(info.status)
      })
      .catch(() => setError('This invitation is invalid or has expired.'))
      .finally(() => setReady(true))
  }, [token])

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    if (!token) return
    if (password !== confirm) {
      setError('Passwords do not match.')
      return
    }
    if (!agreed) {
      setError('Agree to the Terms and Privacy Policy to continue.')
      return
    }
    setLoading(true)
    setError(null)
    try {
      const data = await completeArchitectApplication(token, password)
      if (data.token) applySession(data.token, data.user)
      nav('/architect')
    } catch (err: unknown) {
      const ax = err as { response?: { data?: { detail?: string } } }
      setError(ax.response?.data?.detail || 'Could not complete your account')
    } finally {
      setLoading(false)
    }
  }

  const readyToComplete = status === 'APPROVED'

  return (
    <WorkflowShell>
      <div className="studio-home">
        <p className="studio-meta">Architect invitation</p>
        <h1 className="studio-page-title">Complete Your Account</h1>
        {!ready && <p className="wf-hint">Loading invitation…</p>}
        {error && <div className="error-msg" role="alert">{error}</div>}
        {ready && !readyToComplete && (
          <p>This invitation is {status.toLowerCase().replace(/_/g, ' ')} and cannot be completed.</p>
        )}
        {ready && readyToComplete && (
          <form className="studio-stack" onSubmit={onSubmit}>
            <p>Your KIYUB architect registration has been approved. Create your password to activate the account.</p>
            <label htmlFor="arch-email">Email</label>
            <input id="arch-email" value={email} readOnly />
            <label htmlFor="arch-name">Name</label>
            <input id="arch-name" value={fullName} readOnly />
            <label htmlFor="arch-password">Password</label>
            <PasswordField
              id="arch-password"
              value={password}
              onChange={setPassword}
              autoComplete="new-password"
              required
            />
            <label htmlFor="arch-confirm">Confirm password</label>
            <PasswordField
              id="arch-confirm"
              value={confirm}
              onChange={setConfirm}
              autoComplete="new-password"
              required
            />
            <TermsAgree id="arch-terms" checked={agreed} onChange={setAgreed} />
            <button className="catalog-generate-btn" type="submit" disabled={loading}>
              {loading ? 'Continuing…' : 'Complete account'}
            </button>
          </form>
        )}
      </div>
    </WorkflowShell>
  )
}
