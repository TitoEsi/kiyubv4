import { describe, expect, it } from 'vitest'
import { initialQuestionnaire } from '../types/questionnaire'
import { questionnaireDetailRows } from './questionnaireDetails'

describe('questionnaireDetailRows', () => {
  it('renders stored answers as labels, not internal values', () => {
    const rows = questionnaireDetailRows({
      ...initialQuestionnaire,
      site: { lotShape: 'l_shape', lotWidth: 20, lotDepth: 30 },
      spaces: { ...initialQuestionnaire.spaces, garage: '1car', laundry: 'closet', outdoor: 'both', homeOffice: true },
      preferences: { ...initialQuestionnaire.preferences, style: 'japandi', ceilingHeight: 'vaulted', openPlan: false },
    }, 'm')
    const value = (label: string) => rows.find(row => row.label === label)?.value

    expect(value('Lot Shape')).toBe('L-Shape')
    expect(value('Garage')).toBe('1-Car')
    expect(value('Laundry')).toBe('Closet')
    expect(value('Outdoor Space')).toBe('Both')
    expect(value('Architectural Style')).toBe('Japandi')
    expect(value('Ceiling Height')).toBe('Vaulted')
    expect(value('Home Office')).toBe('Yes')
    expect(value('Open Plan')).toBe('No')
    expect(value('Lot Width')).toBe('20 m')
    expect(rows.map(row => row.value).join(' ')).not.toMatch(/japandi|1car|l_shape|vaulted/)
    expect(rows.map(row => row.label)).toEqual([
      'Lot Shape',
      'Lot Width',
      'Lot Depth',
      'Number of Floors',
      'Bedrooms',
      'Bathrooms',
      'Living area',
      'Home Office',
      'Laundry',
      'Garage',
      'Outdoor Space',
      'Architectural Style',
      'Open Plan',
      'Primary Suite',
      'Formal Dining',
      'Ceiling Height',
    ])
  })

  it('keeps a retired style readable', () => {
    const rows = questionnaireDetailRows({
      ...initialQuestionnaire,
      preferences: { ...initialQuestionnaire.preferences, style: 'craftsman' },
    }, 'ft')
    expect(rows.find(row => row.label === 'Architectural Style')?.value).toBe('Craftsman')
  })
})
