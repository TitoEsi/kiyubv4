import { describe, expect, it } from 'vitest'
import {
  UNIT_ORDER,
  formatArea,
  formatMeasurement,
  fromMeters,
  fromSquareMeters,
  parseArea,
  parseMeasurement,
  roundForDisplay,
  toMeters,
  toSquareMeters,
} from './measurement'

describe('length conversion', () => {
  it('converts meters to every unit', () => {
    expect(fromMeters(1, 'm')).toBe(1)
    expect(fromMeters(1, 'ft')).toBeCloseTo(3.28084, 5)
    expect(fromMeters(1, 'cm')).toBeCloseTo(100, 9)
    expect(fromMeters(1, 'mm')).toBeCloseTo(1000, 9)
    expect(fromMeters(1, 'in')).toBeCloseTo(39.3701, 4)
  })

  it('converts every unit back to meters', () => {
    expect(toMeters(3.28084, 'ft')).toBeCloseTo(1, 5)
    expect(toMeters(100, 'cm')).toBeCloseTo(1, 9)
    expect(toMeters(1000, 'mm')).toBeCloseTo(1, 9)
    expect(toMeters(39.3701, 'in')).toBeCloseTo(1, 5)
  })

  it('interprets input in the selected unit', () => {
    expect(parseMeasurement('10', 'ft')).toBeCloseTo(3.048, 9)
    expect(parseMeasurement('300', 'cm')).toBeCloseTo(3, 9)
    expect(parseMeasurement('3000', 'mm')).toBeCloseTo(3, 9)
    expect(parseMeasurement('120', 'in')).toBeCloseTo(3.048, 9)
    expect(parseMeasurement('4.25', 'm')).toBe(4.25)
    expect(parseMeasurement('', 'm')).toBeNull()
    expect(parseMeasurement('abc', 'ft')).toBeNull()
  })
})

describe('area conversion', () => {
  it('squares the linear factor', () => {
    expect(fromSquareMeters(20, 'ft')).toBeCloseTo(215.278, 2)
    expect(toSquareMeters(200, 'ft')).toBeCloseTo(18.5806, 4)
    expect(fromSquareMeters(1, 'cm')).toBeCloseTo(10_000, 6)
    expect(parseArea('200', 'ft')).toBeCloseTo(18.5806, 4)
  })
})

describe('formatting', () => {
  it('drops trailing zeros and float noise', () => {
    expect(roundForDisplay(3.5000000000000004, 2)).toBe('3.5')
    expect(roundForDisplay(3, 2)).toBe('3')
    expect(roundForDisplay(350.00000000001, 1)).toBe('350')
    expect(roundForDisplay(-0.0001, 2)).toBe('0')
  })

  it('displays the same geometry in every unit', () => {
    const shown = UNIT_ORDER.map(u => formatMeasurement(3.5, u))
    expect(shown).toEqual(['3.5 m', '11.48 ft', '350 cm', '3500 mm', '137.8 in'])
    expect(formatMeasurement(4, 'ft')).toBe('13.12 ft')
  })

  it('uses decimal feet, never feet-inches', () => {
    expect(formatMeasurement(3.5, 'ft')).not.toMatch(/['"]/)
  })

  it('formats squared units', () => {
    expect(formatArea(20, 'm')).toBe('20 m²')
    expect(formatArea(20, 'ft')).toBe('215.28 ft²')
    expect(formatArea(1, 'cm')).toBe('10000 cm²')
  })
})
