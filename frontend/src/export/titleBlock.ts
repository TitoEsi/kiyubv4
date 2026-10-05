import type { MeasurementUnit } from '../units/measurement'
import { UNITS } from '../units/measurement'

/** Title-block measurement unit, matching the viewer's display preference. */
export function titleBlockUnit(unit: MeasurementUnit): string {
  return UNITS[unit].label
}
