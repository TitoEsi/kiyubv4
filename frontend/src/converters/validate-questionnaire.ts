import { ValidationIssue } from '../types/floorplan'
import { QuestionnaireData } from '../types/questionnaire'
import { RETIRED_STYLES } from '../data/architecturalStyles'
import { formatArea, formatMeasurement, MeasurementUnit, toSquareMeters } from '../units/measurement'

/** Program area rules mirror the feet-native generation engine; thresholds are its ft² values. */
const ft2 = (v: number) => toSquareMeters(v, 'ft')

const MIN_LOT_M = 1
const BASE_PROGRAM_M2 = ft2(528)
const PRIMARY_SUITE_M2 = ft2(240)
const STANDARD_PRIMARY_M2 = ft2(168)
const SECONDARY_BEDROOM_M2 = ft2(100)
const SHARED_BATH_M2 = ft2(40)
const HOME_OFFICE_M2 = ft2(90)
const FORMAL_DINING_M2 = ft2(121)
const LAUNDRY_ROOM_M2 = ft2(30)
const TWO_STORY_MIN_M2 = ft2(1200)
const THREE_CAR_MIN_M2 = ft2(1800)
const EPS_M2 = 1e-6

/**
 * Client-side feasibility checks. Mirrors backend lot and program rules.
 * Geometry is canonical (lot in m, living area in m²); `unit` only affects message text.
 */
export function validateQuestionnaire(data: QuestionnaireData, unit: MeasurementUnit = 'm'): ValidationIssue[] {
  const issues: ValidationIssue[] = []
  const { lotShape, lotWidth, lotDepth } = data.site
  const { bedrooms, bathrooms, livingAreaM2: area, floors } = data.house
  const { primarySuite, formalDining } = data.preferences
  const { homeOffice, laundry, garage } = data.spaces
  const secondary = Math.max(0, bedrooms - 1)
  const sharedBaths = Math.max(0, bathrooms - 1)
  const len = (m: number) => formatMeasurement(m, unit)
  const sq = (m2: number) => formatArea(m2, unit)

  if (!(lotWidth > 0) || lotWidth < MIN_LOT_M) {
    issues.push({
      field: 'lotWidth',
      severity: 'error',
      message: `Lot width must be at least ${len(MIN_LOT_M)}.`,
      detail: `Enter a lot width greater than or equal to ${len(MIN_LOT_M)}.`,
    })
  }

  if (!(lotDepth > 0) || lotDepth < MIN_LOT_M) {
    issues.push({
      field: 'lotDepth',
      severity: 'error',
      message: `Lot depth must be at least ${len(MIN_LOT_M)}.`,
      detail: `Enter a lot depth greater than or equal to ${len(MIN_LOT_M)}.`,
    })
  }

  if (lotShape === 'l_shape' || lotShape === 'irregular') {
    const label = lotShape === 'l_shape' ? 'L-shaped' : 'irregular'
    issues.push({
      field: 'lotShape',
      severity: 'error',
      message: `${label.charAt(0).toUpperCase() + label.slice(1)} lots are not yet supported.`,
      detail: 'True L-shaped and irregular lot geometry is not implemented. Choose Rectangle or Square for this phase.',
    })
  }

  const retiredStyle = RETIRED_STYLES[data.preferences.style]
  if (retiredStyle) {
    issues.push({
      field: 'style',
      severity: 'error',
      message: `${retiredStyle} is no longer offered.`,
      detail: 'Choose an architectural style before generating.',
    })
  }

  if (bedrooms < 0) {
    issues.push({
      field: 'bedrooms',
      severity: 'error',
      message: 'Bedrooms cannot be negative.',
      detail: 'Enter zero or more bedrooms.',
    })
  }

  if (bathrooms < 0) {
    issues.push({
      field: 'bathrooms',
      severity: 'error',
      message: 'Bathrooms cannot be negative.',
      detail: 'Enter zero or more bathrooms.',
    })
  }

  if (floors < 1) {
    issues.push({
      field: 'floors',
      severity: 'error',
      message: 'A house needs at least one floor.',
      detail: 'Set number of floors to 1 or 2.',
    })
  }

  const baseOverhead = BASE_PROGRAM_M2 + (primarySuite ? PRIMARY_SUITE_M2 : STANDARD_PRIMARY_M2)
  let minArea = baseOverhead
  minArea += secondary * SECONDARY_BEDROOM_M2
  minArea += sharedBaths * SHARED_BATH_M2
  if (homeOffice) minArea += HOME_OFFICE_M2
  if (formalDining) minArea += FORMAL_DINING_M2
  if (laundry === 'room') minArea += LAUNDRY_ROOM_M2

  if (area < minArea - EPS_M2) {
    const parts: string[] = []
    if (secondary) parts.push(`${secondary} secondary bedroom${secondary !== 1 ? 's' : ''}`)
    parts.push(`${bathrooms} bathroom${bathrooms !== 1 ? 's' : ''}`)
    if (homeOffice) parts.push('home office')
    if (formalDining) parts.push('formal dining')
    issues.push({
      field: 'livingAreaM2',
      severity: 'error',
      message: 'Not enough space for this configuration.',
      detail: `Your selections (${parts.join(', ')}) need at least ${sq(minArea)}. You set ${sq(area)}. Increase size or reduce rooms.`,
    })
  }

  const maxSecondary = Math.max(0, Math.floor((area - baseOverhead + EPS_M2) / SECONDARY_BEDROOM_M2))
  if (secondary > maxSecondary && area >= minArea - EPS_M2) {
    issues.push({
      field: 'bedrooms',
      severity: 'error',
      message: `${bedrooms} bedrooms is not feasible in ${sq(area)}.`,
      detail: `After essential rooms, only ${sq(Math.max(0, area - baseOverhead))} remains for secondary bedrooms (${maxSecondary} max at ${sq(SECONDARY_BEDROOM_M2)} each). Reduce to ${maxSecondary + 1} total or increase the living area.`,
    })
  }

  if (bathrooms > bedrooms + 1) {
    issues.push({
      field: 'bathrooms',
      severity: 'warning',
      message: `${bathrooms} bathrooms for ${bedrooms} bedrooms is unusual.`,
      detail: `Standard practice is 1 bathroom per bedroom. Consider ${Math.min(bathrooms, bedrooms)} bathrooms.`,
    })
  }

  if (floors === 2 && area < TWO_STORY_MIN_M2 - EPS_M2) {
    issues.push({
      field: 'floors',
      severity: 'warning',
      message: `Two-story layout under ${sq(TWO_STORY_MIN_M2)} is cramped.`,
      detail: `Staircase overhead is significant in small homes. Consider single-story or ${sq(TWO_STORY_MIN_M2)}+.`,
    })
  }

  if (garage === '3car' && area < THREE_CAR_MIN_M2 - EPS_M2) {
    issues.push({
      field: 'garage',
      severity: 'warning',
      message: 'A 3-car garage is disproportionate for this home size.',
      detail: `3-car garages suit ${sq(THREE_CAR_MIN_M2)}+ homes. With ${sq(area)}, a 1 or 2-car garage fits better.`,
    })
  }

  return issues
}
