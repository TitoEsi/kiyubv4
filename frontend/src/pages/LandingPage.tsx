import { FormEvent, useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import ConceptCarousel from '../components/ConceptCarousel'
import LandingHeader from '../components/LandingHeader'
import { LANDING_CONCEPTS } from '../data/landingConcepts'
import { submitInquiry } from '../workflow/api'

const ABOUT = [
  { n: '01', title: 'AI-Assisted Floor-Plan Generation', body: 'Generate residential floor-plan concepts from architectural requirements and preferences.' },
  { n: '02', title: '2D + 3D Architectural Visualization', body: 'Explore designs through both 2D floor plans and 3D visualization.' },
  { n: '03', title: 'Collaborative Architect-Client Workflow', body: 'Allow architects and clients to work around the same project and review design updates.' },
  { n: '04', title: 'Design Review and Version Management', body: 'Keep design iterations organized so project changes can be reviewed throughout the workflow.' },
]

export default function LandingPage() {
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [message, setMessage] = useState('')
  const [sent, setSent] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const pageRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const root = pageRef.current
    if (!root) return
    const nodes = root.querySelectorAll('.landing-reveal')
    const io = new IntersectionObserver((entries) => {
      for (const entry of entries) {
        if (entry.isIntersecting) entry.target.classList.add('is-in')
      }
    }, { threshold: 0.16 })
    nodes.forEach(n => io.observe(n))
    return () => io.disconnect()
  }, [])

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
    <div className="landing-page" ref={pageRef}>
      <LandingHeader />

      <section className="landing-hero">
        <p className="studio-meta landing-enter landing-enter-1">KIYUB</p>
        <h1 className="landing-enter landing-enter-2">Design your space with intelligence.</h1>
        <p className="landing-lede landing-enter landing-enter-3">
          AI-assisted architectural floor-plan design — residential concepts developed as drawings in a working studio.
        </p>
        <div className="landing-hero-actions landing-enter landing-enter-4">
          <Link className="landing-hero-cta" to="/login">Sign in</Link>
          <a className="wf-link" href="#contact">Request access</a>
        </div>
        <figure className="landing-hero-visual landing-enter landing-enter-5">
          <img
            src={LANDING_CONCEPTS[0].renderImage}
            alt="Example architectural visualization for KIYUB"
          />
        </figure>
      </section>

      <section className="landing-section landing-reveal" id="about">
        <p className="studio-meta">About KIYUB</p>
        <h2>Design smarter. Explore faster.</h2>
        <ol className="landing-about">
          {ABOUT.map(item => (
            <li key={item.n}>
              <span className="landing-about-n">{item.n}</span>
              <div>
                <h3>{item.title}</h3>
                <p>{item.body}</p>
              </div>
            </li>
          ))}
        </ol>
        <p className="landing-disclaimer">
          KIYUB is a conceptual design and planning tool. It does not replace licensed architects,
          and generated designs are not claimed to be building-code compliant.
        </p>
      </section>

      <section className="landing-section landing-reveal landing-gallery-section" id="gallery">
        <p className="studio-meta">Example Concepts</p>
        <h2>Concept layouts</h2>
        <p className="landing-disclaimer">Example concepts shown for demonstration purposes only.</p>
        <ConceptCarousel />
      </section>

      <section className="landing-section landing-reveal" id="contact">
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
            <button className="landing-hero-cta" type="submit" disabled={loading}>
              {loading ? 'Sending…' : 'Send request'}
            </button>
          </form>
        )}
      </section>

      <footer className="landing-foot">
        <a href="#about">About</a>
        <a href="#gallery">Concepts</a>
        <a href="#contact">Contact</a>
        <Link to="/terms">Terms</Link>
        <Link to="/privacy">Privacy</Link>
      </footer>
    </div>
  )
}
