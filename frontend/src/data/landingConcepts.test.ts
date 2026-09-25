import { describe, expect, it } from 'vitest'
import { LANDING_CONCEPTS } from './landingConcepts'

describe('landingConcepts', () => {
  it('lists six replaceable example concepts', () => {
    expect(LANDING_CONCEPTS).toHaveLength(6)
    expect(LANDING_CONCEPTS.every(c => c.isExample && c.renderImage.startsWith('/landing/concepts/'))).toBe(true)
    expect(new Set(LANDING_CONCEPTS.map(c => c.id)).size).toBe(6)
  })
})
