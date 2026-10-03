import { describe, expect, it } from 'vitest'
import { questionnaireToSpecification } from './questionnaire-to-specification'
import { specificationToConstraints } from './specification-to-generation'
import { validateQuestionnaire } from './validate-questionnaire'
import { QuestionnaireData } from '../types/questionnaire'

function sample(overrides: (data: QuestionnaireData) => void): QuestionnaireData {
  const data: QuestionnaireData = {
    site: { lotShape: 'rectangle', lotWidth: 10, lotDepth: 15 },
    house: { floors: 2, bedrooms: 4, bathrooms: 3, livingAreaM2: 204 },
    spaces: { homeOffice: true, laundry: 'room', garage: '1car', outdoor: 'deck' },
    preferences: {
      style: 'modern',
      openPlan: true,
      primarySuite: true,
      formalDining: false,
      ceilingHeight: 'high',
    },
  }
  overrides(data)
  return data
}

describe('questionnaireToSpecification', () => {
  it('preserves user lot, bedroom, bathroom, and floor values', () => {
    const spec = questionnaireToSpecification(sample(() => {}))
    expect(spec.site.width).toBe(10)
    expect(spec.site.depth).toBe(15)
    expect(spec.building.bedrooms).toBe(4)
    expect(spec.building.bathrooms).toBe(3)
    expect(spec.building.floors).toBe(2)
    expect(spec.building.livingAreaM2).toBe(204)
  })

  it('does not substitute a 3-bed / 20x30 program', () => {
    const spec = questionnaireToSpecification(sample(() => {}))
    expect(spec.building.bedrooms).not.toBe(3)
    expect(spec.site.width).not.toBe(20)
    expect(spec.site.depth).not.toBe(30)
  })

  it('includes optional spaces when selected', () => {
    const spec = questionnaireToSpecification(sample(() => {}))
    expect(spec.rooms.required).toContain('kitchen')
    expect(spec.rooms.required).toContain('living_room')
    expect(spec.rooms.required).toContain('foyer')
    expect(spec.rooms.required).toContain('home_office')
    expect(spec.rooms.required).toContain('laundry')
    expect(spec.rooms.required).toContain('garage')
    expect(spec.rooms.required).toContain('deck')
    expect(spec.features.homeOffice).toBe(true)
    expect(spec.features.openPlan).toBe(true)
    expect(spec.features.garage).toBe('1car')
    expect(spec.features.outdoor).toBe('deck')
  })

  it('omits optional rooms when not selected', () => {
    const spec = questionnaireToSpecification(sample(d => {
      d.spaces.homeOffice = false
      d.spaces.garage = 'none'
      d.spaces.outdoor = 'none'
      d.spaces.laundry = 'none'
      d.preferences.formalDining = false
    }))
    expect(spec.rooms.required).not.toContain('home_office')
    expect(spec.rooms.required).not.toContain('garage')
    expect(spec.rooms.required).not.toContain('patio')
    expect(spec.rooms.required).not.toContain('deck')
    expect(spec.rooms.required).not.toContain('laundry')
    expect(spec.rooms.required).not.toContain('dining_room')
  })
})

describe('specificationToConstraints', () => {
  it('maps specification fields onto a complete generation request', () => {
    const constraints = specificationToConstraints(
      questionnaireToSpecification(sample(() => {}))
    )
    expect(constraints.lotWidth).toBe(10)
    expect(constraints.lotDepth).toBe(15)
    expect(constraints.bedrooms).toBe(4)
    expect(constraints.bathrooms).toBe(3)
    expect(constraints.stories).toBe(2)
    expect(constraints.livingAreaM2).toBe(204)
    expect(constraints.homeOffice).toBe(true)
    expect(constraints.garage).toBe('1car')
    expect(constraints.outdoor).toBe('deck')
    expect(constraints.openPlan).toBe(true)
    expect(constraints.ceilingHeight).toBe('high')
    expect(constraints.style).toBe('modern')
  })
})

describe('validateQuestionnaire', () => {
  it('rejects L-shaped lots as not yet supported', () => {
    const issues = validateQuestionnaire(sample(d => {
      d.site.lotShape = 'l_shape'
    }))
    expect(issues.some(i => i.field === 'lotShape' && i.severity === 'error')).toBe(true)
  })

  it('checks area in m² and reports it in the selected unit', () => {
    const tooSmall = sample(d => { d.house.livingAreaM2 = 40 })
    const m = validateQuestionnaire(tooSmall, 'm').find(i => i.field === 'livingAreaM2')
    const ft = validateQuestionnaire(tooSmall, 'ft').find(i => i.field === 'livingAreaM2')
    expect(m?.detail).toContain('You set 40 m²')
    expect(ft?.detail).toContain('You set 430.56 ft²')
  })

  it('accepts the default living area without a 3-car warning edge case', () => {
    const issues = validateQuestionnaire(sample(d => {
      d.house = { floors: 1, bedrooms: 3, bathrooms: 2, livingAreaM2: 1800 * 0.3048 * 0.3048 }
      d.spaces.garage = '3car'
    }))
    expect(issues.some(i => i.field === 'garage')).toBe(false)
  })
})

describe('KIYUB v4 20 × 30 lot baseline', () => {
  it('preserves 20m × 30m from questionnaire through specification and constraints', () => {
    const data: QuestionnaireData = {
      site: { lotShape: 'rectangle', lotWidth: 20, lotDepth: 30 },
      house: { floors: 1, bedrooms: 3, bathrooms: 2, livingAreaM2: 167 },
      spaces: { homeOffice: false, laundry: 'room', garage: 'none', outdoor: 'none' },
      preferences: {
        style: 'modern',
        openPlan: false,
        primarySuite: true,
        formalDining: true,
        ceilingHeight: 'standard',
      },
    }
    const spec = questionnaireToSpecification(data)
    const constraints = specificationToConstraints(spec)
    expect(spec.site.width).toBe(20)
    expect(spec.site.depth).toBe(30)
    expect(spec.building.floors).toBe(1)
    expect(spec.building.bedrooms).toBe(3)
    expect(spec.building.bathrooms).toBe(2)
    expect(constraints.lotWidth).toBe(20)
    expect(constraints.lotDepth).toBe(30)
    expect(constraints.stories).toBe(1)
    expect(constraints.formalDining).toBe(true)
  })
})
