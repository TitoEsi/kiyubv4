import { ARCHITECTURAL_STYLES, RETIRED_STYLES } from '../data/architecturalStyles'
import type { QuestionnaireData } from '../types/questionnaire'
import { formatArea, formatMeasurement, type MeasurementUnit } from '../units/measurement'

export interface DetailRow {
  label: string
  value: string
}

const LOT_SHAPES: Record<string, string> = {
  rectangle: 'Rectangle',
  square: 'Square',
  l_shape: 'L-Shape',
  irregular: 'Irregular',
}

const GARAGE: Record<string, string> = {
  none: 'None',
  '1car': '1-Car',
  '2car': '2-Car',
  '3car': '3-Car',
}

const LAUNDRY: Record<string, string> = {
  none: 'None',
  closet: 'Closet',
  room: 'Room',
}

const OUTDOOR: Record<string, string> = {
  none: 'None',
  patio: 'Patio',
  deck: 'Deck',
  both: 'Both',
}

const CEILING: Record<string, string> = {
  standard: 'Standard',
  high: 'High',
  vaulted: 'Vaulted',
}

function choice(labels: Record<string, string>, value: string): string {
  if (labels[value]) return labels[value]
  const words = value.replace(/[_-]+/g, ' ').trim()
  return words ? words.replace(/\b\w/g, c => c.toUpperCase()) : '—'
}

export function styleLabel(id: string): string {
  const known = ARCHITECTURAL_STYLES.find(s => s.id === id)?.label
  if (known) return known
  if (RETIRED_STYLES[id]) return RETIRED_STYLES[id]
  return choice({}, id)
}

function yesNo(value: boolean): string {
  return value ? 'Yes' : 'No'
}

/** Human-readable project-detail rows for every stored questionnaire answer. */
export function questionnaireDetailRows(data: QuestionnaireData, unit: MeasurementUnit): DetailRow[] {
  return [
    { label: 'Lot Shape', value: choice(LOT_SHAPES, data.site.lotShape) },
    { label: 'Lot Width', value: formatMeasurement(data.site.lotWidth, unit) },
    { label: 'Lot Depth', value: formatMeasurement(data.site.lotDepth, unit) },
    { label: 'Number of Floors', value: String(data.house.floors) },
    { label: 'Bedrooms', value: String(data.house.bedrooms) },
    { label: 'Bathrooms', value: String(data.house.bathrooms) },
    { label: 'Living area', value: formatArea(data.house.livingAreaM2, unit) },
    { label: 'Home Office', value: yesNo(data.spaces.homeOffice) },
    { label: 'Laundry', value: choice(LAUNDRY, data.spaces.laundry) },
    { label: 'Garage', value: choice(GARAGE, data.spaces.garage) },
    { label: 'Outdoor Space', value: choice(OUTDOOR, data.spaces.outdoor) },
    { label: 'Architectural Style', value: styleLabel(data.preferences.style) },
    { label: 'Open Plan', value: yesNo(data.preferences.openPlan) },
    { label: 'Primary Suite', value: yesNo(data.preferences.primarySuite) },
    { label: 'Formal Dining', value: yesNo(data.preferences.formalDining) },
    { label: 'Ceiling Height', value: choice(CEILING, data.preferences.ceilingHeight) },
  ]
}
