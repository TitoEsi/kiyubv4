import { describe, expect, it } from 'vitest'
import { ARCHITECTURAL_STYLES } from './architecturalStyles'
import { SAMPLE_PLANS } from './samplePlans'

describe('public gallery and style cards', () => {
  it('does not offer ranch in the UI style list', () => {
    expect(ARCHITECTURAL_STYLES.map(s => s.id)).not.toContain('ranch')
    expect(ARCHITECTURAL_STYLES.map(s => s.id)).toContain('japandi')
    expect(ARCHITECTURAL_STYLES.map(s => s.id)).toContain('filipino_contemporary')
  })

  it('ships three labeled conceptual sample plans', () => {
    expect(SAMPLE_PLANS).toHaveLength(3)
    for (const plan of SAMPLE_PLANS) {
      expect(plan.rooms.length).toBeGreaterThan(0)
      expect(plan.totalWidth).toBeGreaterThan(0)
    }
  })
})
