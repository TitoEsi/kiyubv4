import { describe, expect, it } from 'vitest'
import { ARCHITECTURAL_STYLES, RETIRED_STYLES } from './architecturalStyles'
import { SAMPLE_PLANS } from './samplePlans'
import { validateQuestionnaire } from '../converters/validate-questionnaire'
import { initialQuestionnaire, QuestionnaireData } from '../types/questionnaire'

const SUPPORTED = [
  'modern', 'traditional', 'contemporary', 'japandi', 'minimalist', 'brutalist',
  'modern_tropical', 'filipino_contemporary', 'tropical_minimalist',
]

const withStyle = (style: string): QuestionnaireData => ({
  ...initialQuestionnaire,
  preferences: { ...initialQuestionnaire.preferences, style },
})

describe('public gallery and style cards', () => {
  it('does not offer ranch in the UI style list', () => {
    expect(ARCHITECTURAL_STYLES.map(s => s.id)).not.toContain('ranch')
    expect(ARCHITECTURAL_STYLES.map(s => s.id)).toContain('japandi')
    expect(ARCHITECTURAL_STYLES.map(s => s.id)).toContain('filipino_contemporary')
  })

  it('does not offer farmhouse or craftsman and keeps every supported style', () => {
    const ids = ARCHITECTURAL_STYLES.map(s => s.id as string)
    const labels = ARCHITECTURAL_STYLES.map(s => s.label.toLowerCase())
    for (const retired of ['farmhouse', 'craftsman']) {
      expect(ids).not.toContain(retired)
      expect(labels).not.toContain(retired)
    }
    expect(ids).toEqual(SUPPORTED)
  })

  it('ships three labeled conceptual sample plans', () => {
    expect(SAMPLE_PLANS).toHaveLength(3)
    for (const plan of SAMPLE_PLANS) {
      expect(plan.rooms.length).toBeGreaterThan(0)
      expect(plan.totalWidth).toBeGreaterThan(0)
    }
  })
})

describe('retired style validation', () => {
  it.each(Object.keys(RETIRED_STYLES))('blocks generation for a saved %s brief without changing it', style => {
    const q = withStyle(style)
    const issues = validateQuestionnaire(q).filter(i => i.field === 'style')
    expect(issues).toHaveLength(1)
    expect(issues[0].severity).toBe('error')
    expect(issues[0].message).toContain(RETIRED_STYLES[style])
    expect(q.preferences.style).toBe(style)
  })

  it.each(SUPPORTED)('accepts %s', style => {
    expect(validateQuestionnaire(withStyle(style)).filter(i => i.field === 'style')).toEqual([])
  })
})
