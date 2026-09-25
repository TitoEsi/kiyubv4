import { useState } from 'react'
import { Link } from 'react-router-dom'
import LandingHeader from '../components/LandingHeader'
import { PRIVACY_EFFECTIVE, PRIVACY_SECTIONS } from '../data/legalPrivacy'
import { LEGAL_DRAFT_NOTICE, TERMS_EFFECTIVE, TERMS_SECTIONS } from '../data/legalTerms'

export default function LegalPage({ kind }: { kind: 'terms' | 'privacy' }) {
  const title = kind === 'terms' ? 'Terms and Conditions' : 'Privacy Policy'
  const effective = kind === 'terms' ? TERMS_EFFECTIVE : PRIVACY_EFFECTIVE
  const sections = kind === 'terms' ? TERMS_SECTIONS : PRIVACY_SECTIONS
  const other = kind === 'terms' ? { to: '/privacy', label: 'Privacy Policy' } : { to: '/terms', label: 'Terms and Conditions' }
  const [jump, setJump] = useState(sections[0].id)

  function go(id: string) {
    setJump(id)
    const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    document.getElementById(id)?.scrollIntoView({ behavior: reduce ? 'auto' : 'smooth', block: 'start' })
  }

  return (
    <div className="legal-page">
      <LandingHeader />
      <div className="legal-layout">
        <aside className="legal-toc" aria-label="Sections">
          <p className="studio-meta">{title}</p>
          <label className="legal-toc-mobile" htmlFor="legal-jump">Section</label>
          <select
            id="legal-jump"
            className="legal-toc-select"
            value={jump}
            onChange={e => go(e.target.value)}
          >
            {sections.map(s => (
              <option key={s.id} value={s.id}>{s.title}</option>
            ))}
          </select>
          <nav className="legal-toc-list">
            <ol>
              {sections.map(s => (
                <li key={s.id}>
                  <a href={`#${s.id}`} onClick={e => { e.preventDefault(); go(s.id) }}>{s.title}</a>
                </li>
              ))}
            </ol>
          </nav>
        </aside>
        <article className="legal-body">
          <p className="studio-meta">{title}</p>
          <h1>{title}</h1>
          <p className="legal-effective">{effective}</p>
          <p className="legal-banner" role="note">{LEGAL_DRAFT_NOTICE}</p>
          {sections.map(s => (
            <section key={s.id} id={s.id} className="legal-section">
              <h2>{s.title}</h2>
              {s.paragraphs.map((p, i) => <p key={i}>{p}</p>)}
            </section>
          ))}
          <p className="legal-cross">
            <Link className="wf-link" to={other.to}>{other.label}</Link>
            {' · '}
            <Link className="wf-link" to="/">Back to KIYUB</Link>
          </p>
        </article>
      </div>
    </div>
  )
}
