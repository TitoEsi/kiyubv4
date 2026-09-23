import { useState } from 'react'

const KEY = 'kiyub-client-guide-dismissed'

const STEPS = [
  { n: '01', t: 'Create a project', d: 'Your architect opens a project and assigns it to you.' },
  { n: '02', t: 'Describe your site', d: 'Enter lot shape, width, depth, and site requirements.' },
  { n: '03', t: 'Define your spaces', d: 'Choose the rooms and spaces you want in your home.' },
  { n: '04', t: 'Add your preferences', d: 'Specify floors, bedrooms, bathrooms, and circulation.' },
  { n: '05', t: 'Generate your floor plan', d: 'KIYUB produces architectural floor-plan candidates from your brief.' },
  { n: '06', t: 'Review and refine', d: 'Open the drawing, comment on the plan, and request changes.' },
]

export default function GenerationGuide() {
  const [dismissed, setDismissed] = useState(() => {
    try {
      return localStorage.getItem(KEY) === '1'
    } catch {
      return false
    }
  })
  const [open, setOpen] = useState(!dismissed)

  function skip() {
    try {
      localStorage.setItem(KEY, '1')
    } catch { /* ignore */ }
    setDismissed(true)
    setOpen(false)
  }

  if (dismissed && !open) {
    return (
      <section className="studio-guide">
        <button type="button" className="wf-action" onClick={() => setOpen(true)}>How it works</button>
      </section>
    )
  }

  return (
    <section className="studio-guide" aria-label="How to create your floor plan">
      <div className="studio-guide-head">
        <h2 className="studio-section-title">How to create your floor plan</h2>
        <button type="button" className="wf-action" onClick={skip}>Skip tutorial</button>
      </div>
      {open && (
        <ol className="studio-guide-steps">
          {STEPS.map(s => (
            <li key={s.n}>
              <span className="studio-index">{s.n}</span>
              <span>
                <strong>{s.t}</strong>
                <span className="wf-hint">{s.d}</span>
              </span>
            </li>
          ))}
        </ol>
      )}
    </section>
  )
}
