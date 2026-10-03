/**
 * KIYUB measurement units.
 *
 * Canonical rule: every architectural length in the app is meters and every area is
 * square meters. A MeasurementUnit is only a display/input preference. Convert at the
 * UI boundary with toMeters/fromMeters; never store display-unit values in geometry.
 *
 * This module is the only place that holds unit conversion factors.
 */

export type MeasurementUnit = 'm' | 'ft' | 'cm' | 'mm' | 'in'

export interface UnitDefinition {
  id: MeasurementUnit
  label: string
  symbol: string
  metersPerUnit: number
  decimals: number
  areaDecimals: number
}

export const UNITS: Record<MeasurementUnit, UnitDefinition> = {
  m: { id: 'm', label: 'Meters', symbol: 'm', metersPerUnit: 1, decimals: 2, areaDecimals: 2 },
  ft: { id: 'ft', label: 'Feet', symbol: 'ft', metersPerUnit: 0.3048, decimals: 2, areaDecimals: 2 },
  cm: { id: 'cm', label: 'Centimeters', symbol: 'cm', metersPerUnit: 0.01, decimals: 1, areaDecimals: 0 },
  mm: { id: 'mm', label: 'Millimeters', symbol: 'mm', metersPerUnit: 0.001, decimals: 0, areaDecimals: 0 },
  in: { id: 'in', label: 'Inches', symbol: 'in', metersPerUnit: 0.0254, decimals: 1, areaDecimals: 0 },
}

export const UNIT_ORDER: MeasurementUnit[] = ['m', 'ft', 'cm', 'mm', 'in']

export const DEFAULT_UNIT: MeasurementUnit = 'm'

export function isMeasurementUnit(value: unknown): value is MeasurementUnit {
  return typeof value === 'string' && value in UNITS
}

export function toMeters(value: number, unit: MeasurementUnit): number {
  return value * UNITS[unit].metersPerUnit
}

export function fromMeters(meters: number, unit: MeasurementUnit): number {
  return meters / UNITS[unit].metersPerUnit
}

export function toSquareMeters(value: number, unit: MeasurementUnit): number {
  const f = UNITS[unit].metersPerUnit
  return value * f * f
}

export function fromSquareMeters(squareMeters: number, unit: MeasurementUnit): number {
  const f = UNITS[unit].metersPerUnit
  return squareMeters / (f * f)
}

/** Rounds to `decimals` and drops trailing zeros (3.50 -> "3.5", 350.0 -> "350"). */
export function roundForDisplay(value: number, decimals: number): string {
  if (!Number.isFinite(value)) return '—'
  const rounded = Number(value.toFixed(decimals))
  return String(Object.is(rounded, -0) ? 0 : rounded)
}

export function displayLength(meters: number, unit: MeasurementUnit): string {
  return roundForDisplay(fromMeters(meters, unit), UNITS[unit].decimals)
}

export function formatMeasurement(meters: number, unit: MeasurementUnit): string {
  return `${displayLength(meters, unit)} ${UNITS[unit].symbol}`
}

export function areaSymbol(unit: MeasurementUnit): string {
  return `${UNITS[unit].symbol}²`
}

export function displayArea(squareMeters: number, unit: MeasurementUnit): string {
  return roundForDisplay(fromSquareMeters(squareMeters, unit), UNITS[unit].areaDecimals)
}

export function formatArea(squareMeters: number, unit: MeasurementUnit): string {
  return `${displayArea(squareMeters, unit)} ${areaSymbol(unit)}`
}

export function formatDimensions(widthM: number, depthM: number, unit: MeasurementUnit): string {
  return `${displayLength(widthM, unit)} × ${displayLength(depthM, unit)} ${UNITS[unit].symbol}`
}

/** Parses user input typed in `unit`; returns meters, or null when not a finite number. */
export function parseMeasurement(text: string, unit: MeasurementUnit): number | null {
  const v = Number(String(text).trim().replace(',', '.'))
  return text.trim() !== '' && Number.isFinite(v) ? toMeters(v, unit) : null
}

export function parseArea(text: string, unit: MeasurementUnit): number | null {
  const v = Number(String(text).trim().replace(',', '.'))
  return text.trim() !== '' && Number.isFinite(v) ? toSquareMeters(v, unit) : null
}

/** Input step in the display unit that corresponds to roughly `meters` of geometry. */
export function inputStep(unit: MeasurementUnit, meters = 0.01): number {
  const raw = fromMeters(meters, unit)
  const pow = Math.pow(10, Math.floor(Math.log10(raw)))
  return Number(pow.toPrecision(1))
}

/** Legacy feet values (solver-native data, old saved plans and pins). */
export function legacyFeetToMeters(feet: number): number {
  return toMeters(feet, 'ft')
}

export function legacySquareFeetToSquareMeters(sqft: number): number {
  return toSquareMeters(sqft, 'ft')
}
