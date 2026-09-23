import { FormEvent, useRef, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import KiyubLogo from '../components/KiyubLogo'
import PasswordField from '../components/PasswordField'
import TermsAgree from '../components/TermsAgree'
import ThemeToggle from '../components/ThemeToggle'
import { useAuth } from '../workflow/auth'

export default function LoginPage() {
  const { login } = useAuth()
  const nav = useNavigate()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [agreed, setAgreed] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const summaryRef = useRef<HTMLDivElement>(null)

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    if (!agreed) {
      setError('Agree to the Terms and Privacy Policy to continue.')
      requestAnimationFrame(() => summaryRef.current?.focus())
      return
    }
    setLoading(true)
    setError(null)
    try {
      const user = await login(email, password)
      if (user.role === 'CLIENT') nav('/client')
      else if (user.role === 'ARCHITECT') nav('/architect')
      else if (user.role === 'MAIN_ADMIN') nav('/admin')
      else nav('/it')
    } catch (err: unknown) {
      const ax = err as { response?: { data?: { detail?: string } } }
      setError(ax.response?.data?.detail || 'Login failed')
      requestAnimationFrame(() => summaryRef.current?.focus())
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="studio-login">
      <section className="studio-login-identity" aria-label="KIYUB">
        <Link to="/" className="wf-brand" aria-label="KIYUB home">
          <KiyubLogo variant="full" decorative className="kiyub-logo-login" />
        </Link>
        <h1 className="studio-login-headline">Architectural Intelligence Studio</h1>
        <p className="studio-login-lede">AI-assisted floor plans, developed as drawings in a working studio.</p>
        <div className="studio-login-plate" aria-hidden>
          <svg viewBox="0 0 320 220" fill="none">
            <rect x="1" y="1" width="318" height="218" stroke="currentColor" strokeOpacity="0.18" />
            <rect x="28" y="36" width="168" height="148" stroke="currentColor" strokeWidth="1.2" />
            <rect x="196" y="36" width="96" height="72" stroke="currentColor" strokeWidth="1.2" />
            <rect x="196" y="108" width="96" height="76" stroke="currentColor" strokeWidth="1.2" />
            <rect x="48" y="56" width="72" height="52" stroke="currentColor" strokeOpacity="0.45" />
            <rect x="128" y="56" width="48" height="52" stroke="currentColor" strokeOpacity="0.45" />
            <rect x="48" y="124" width="128" height="40" stroke="currentColor" strokeOpacity="0.45" />
            <path d="M28 110h40" stroke="currentColor" strokeWidth="2" />
            <path d="M196 72h18" stroke="currentColor" strokeWidth="2" />
            <circle cx="86" cy="82" r="2" fill="currentColor" />
          </svg>
        </div>
      </section>
      <section className="studio-login-panel">
        <div className="studio-login-toolbar">
          <ThemeToggle />
        </div>
        <form className="wf-login-card" onSubmit={onSubmit}>
          <p className="studio-meta">Sign in</p>
          {error && (
            <div className="error-msg" role="alert" tabIndex={-1} ref={summaryRef}>
              {error}
            </div>
          )}
          <label htmlFor="login-email">Email</label>
          <input id="login-email" value={email} onChange={e => setEmail(e.target.value)} autoComplete="username" />
          <label htmlFor="login-password">Password</label>
          <PasswordField id="login-password" value={password} onChange={setPassword} required />
          <TermsAgree id="login-terms" checked={agreed} onChange={setAgreed} />
          <button className="catalog-generate-btn" disabled={loading} type="submit">
            {loading ? 'Signing in…' : 'Sign in'}
          </button>
        </form>
      </section>
    </div>
  )
}
