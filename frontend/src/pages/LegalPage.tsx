import { Link } from 'react-router-dom'
import KiyubLogo from '../components/KiyubLogo'
import ThemeToggle from '../components/ThemeToggle'

export default function LegalPage({ kind }: { kind: 'terms' | 'privacy' }) {
  const title = kind === 'terms' ? 'Terms and Conditions' : 'Privacy Policy'
  return (
    <div className="legal-page">
      <header className="landing-top">
        <Link to="/" className="wf-brand" aria-label="KIYUB home">
          <KiyubLogo variant="full" />
        </Link>
        <div className="wf-top-end">
          <ThemeToggle />
          <Link className="wf-link" to="/login">Sign in</Link>
        </div>
      </header>
      <article className="studio-home studio-prose legal-body">
        <p className="studio-meta">{title}</p>
        <h1 className="studio-greeting-title">{title}</h1>
        <p>
          This document is a configuration point. KIYUB has not published {title.toLowerCase()} copy yet.
          Do not treat this page as legal advice or as an executed agreement.
        </p>
        <p className="wf-hint">Studio legal text: not configured.</p>
        <Link className="wf-link" to="/">Back to KIYUB</Link>
      </article>
    </div>
  )
}
