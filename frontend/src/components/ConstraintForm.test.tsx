import { describe, expect, it } from 'vitest'
import { renderToStaticMarkup } from 'react-dom/server'
import ConstraintForm from './ConstraintForm'
import { initialQuestionnaire } from '../types/questionnaire'

function render(style: string) {
  const value = { ...initialQuestionnaire, preferences: { ...initialQuestionnaire.preferences, style } }
  return renderToStaticMarkup(<ConstraintForm value={value} onChange={() => {}} onGenerate={() => {}} loading={false} />)
}

const cardLabels = (html: string) =>
  [...html.matchAll(/class="catalog-style-card-label">([^<]*)</g)].map(m => m[1])

describe('ConstraintForm style cards', () => {
  it('never renders Farmhouse or Craftsman cards', () => {
    const labels = cardLabels(render('modern'))
    expect(labels).toContain('Japandi')
    expect(labels).not.toContain('Farmhouse')
    expect(labels).not.toContain('Craftsman')
  })

  it.each([['farmhouse', 'Farmhouse'], ['craftsman', 'Craftsman']])(
    'renders a saved %s brief with a notice and no active card',
    (style, label) => {
      const html = render(style)
      expect(html).toContain(`Saved style: ${label}, no longer offered`)
      expect(cardLabels(html)).not.toContain(label)
      expect(html).not.toMatch(/class="catalog-style-card active"/)
      expect(html).toContain(`${label} is no longer offered.`)
    },
  )

  it('marks a supported style active without a notice', () => {
    const html = render('japandi')
    expect(html).toMatch(/class="catalog-style-card active"[^>]*aria-pressed="true"[^>]*><span class="catalog-style-card-label">Japandi/)
    expect(html).not.toContain('no longer offered')
  })
})
