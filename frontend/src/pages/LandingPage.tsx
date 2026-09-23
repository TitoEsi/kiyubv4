import { FormEvent, useState } from 'react'
import { Link } from 'react-router-dom'
import FloorPlanPreview from '../components/FloorPlanPreview'
import KiyubLogo from '../components/KiyubLogo'
import ThemeToggle from '../components/ThemeToggle'
import { SAMPLE_PLANS } from '../data/samplePlans'
import { submitInquiry } from '../workflow/api'

export default function LandingPage() {
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [message, setMessage] = useState('')
  const [sent, setSent] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  async function onInquire(e: FormEvent) {
    e.preventDefault()
    setLoading(true)
    setError(null)
    try {
      await submitInquiry({ name, email, message })
      setSent(true)
    } catch {
      setError('Could not send this request. Try again.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="landing-page">
      <header className="landing-top">
        <Link to="/" className="wf-brand" aria-label="KIYUB home">
          <KiyubLogo variant="full" />
        </Link>
        <div className="wf-top-end">
          <ThemeToggle />
          <Link className="catalog-generate-btn landing-signin" to="/login">Sign in</Link>
        </div>
      </header>

      <section className="landing-hero">
        <p className="studio-meta">KIYUB</p>
        <h1>Design your space with intelligence.</h1>
        <p className="landing-lede">
          AI-assisted residential floor plans, developed as drawings in a working studio.
        </p>
        <div className="landing-hero-actions">
          <Link className="catalog-generate-btn" to="/login">Sign in</Link>
          <a className="wf-link" href="#contact">Request access</a>
        </div>
      </section>

      <section className="landing-section" id="about">
        <p className="studio-meta">About KIYUB</p>
        <h2>Design smarter. Explore faster.</h2>
        <p>
          KIYUB helps clients and architectural professionals transform requirements into
          residential floor-plan concepts through an interactive, AI-assisted design workflow.
        </p>
        <p>
          From the initial brief to floor-plan exploration and review, KIYUB brings the design
          process into one collaborative workspace.
        </p>
        <p>
          KIYUB is a conceptual design and planning tool. It does not replace licensed architects,
          and generated designs are not claimed to be building-code compliant.
        </p>
      </section>

      <section className="landing-section" id="gallery">
        <p className="studio-meta">Sample plans</p>
        <h2>Conceptual layouts</h2>
        <p className="wf-hint">Editorial plates for the public gallery — not live generation output.</p>
        <ul className="landing-gallery">
          {SAMPLE_PLANS.map(plan => (
            <li key={plan.id}>
              <article className="studio-tile">
                <div className="studio-tile-plate">
                  <FloorPlanPreview plan={plan} width={320} height={180} />
                </div>
                <div className="studio-tile-copy">
                  <h3 className="studio-tile-name">{plan.name}</h3>
                  <p className="studio-tile-meta">Labeled conceptual layout</p>
                </div>
              </article>
            </li>
          ))}
        </ul>
      </section>

      <section className="landing-section" id="contact">
        <p className="studio-meta">Request access</p>
        <h2>Contact</h2>
        <p>Tell us who you are. This form stores a request; it does not create an account.</p>
        {sent ? (
          <p className="landing-success" role="status">
            Request received. KIYUB follows up when outbound contact is configured.
          </p>
        ) : (
          <form className="landing-form" onSubmit={onInquire}>
            {error && <div className="error-msg" role="alert">{error}</div>}
            <label htmlFor="inquiry-name">Name</label>
            <input id="inquiry-name" value={name} onChange={e => setName(e.target.value)} required />
            <label htmlFor="inquiry-email">Email</label>
            <input
              id="inquiry-email"
              type="email"
              value={email}
              onChange={e => setEmail(e.target.value)}
              required
              autoComplete="email"
            />
            <label htmlFor="inquiry-message">Message</label>
            <textarea
              id="inquiry-message"
              value={message}
              onChange={e => setMessage(e.target.value)}
              required
              rows={5}
            />
            <button className="catalog-generate-btn" type="submit" disabled={loading}>
              {loading ? 'Sending…' : 'Send request'}
            </button>
          </form>
        )}
      </section>

      <footer className="landing-foot">
        <Link to="/terms">Terms</Link>
        <Link to="/privacy">Privacy</Link>
        <Link to="/login">Sign in</Link>
      </footer>
    </div>
  )
}
