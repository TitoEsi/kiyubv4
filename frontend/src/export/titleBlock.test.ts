import { describe, expect, it } from 'vitest'
import { titleBlockUnit } from './titleBlock'

describe('titleBlockUnit', () => {
  it('uses the measurement unit label', () => {
    expect(titleBlockUnit('m')).toBe('Meters')
    expect(titleBlockUnit('ft')).toBe('Feet')
  })
})
