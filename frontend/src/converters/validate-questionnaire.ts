import { ValidationIssue } from '../types/floorplan'
import { QuestionnaireData } from '../types/questionnaire'

/** Client-side feasibility checks. Mirrors backend lot and program rules. */
export function validateQuestionnaire(data: QuestionnaireData): ValidationIssue[] {
  const issues: ValidationIssue[] = []
  const { lotShape, lotWidth, lotDepth } = data.site
  const { bedrooms, bathrooms, livingAreaSqft: sqft, floors } = data.house
  const { primarySuite, formalDining } = data.preferences
  const { homeOffice, laundry, garage } = data.spaces
  const secondary = Math.max(0, bedrooms - 1)
  const sharedBaths = Math.max(0, bathrooms - 1)

  if (!(lotWidth > 0) || lotWidth < 1) {
    issues.push({
      field: 'lotWidth',
      severity: 'error',
      message: 'Lot width must be at least 1 meter.',
      detail: 'Enter a lot width greater than or equal to 1 m.',
    })
  }

  if (!(lotDepth > 0) || lotDepth < 1) {
    issues.push({
      field: 'lotDepth',
      severity: 'error',
      message: 'Lot depth must be at least 1 meter.',
      detail: 'Enter a lot depth greater than or equal to 1 m.',
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

  let minSqft = 528
  minSqft += primarySuite ? 240 : 168
  minSqft += secondary * 100
  minSqft += sharedBaths * 40
  if (homeOffice) minSqft += 90
  if (formalDining) minSqft += 121
  if (laundry === 'room') minSqft += 30

  if (sqft < minSqft) {
    const parts: string[] = []
    if (secondary) parts.push(`${secondary} secondary bedroom${secondary !== 1 ? 's' : ''}`)
    parts.push(`${bathrooms} bathroom${bathrooms !== 1 ? 's' : ''}`)
    if (homeOffice) parts.push('home office')
    if (formalDining) parts.push('formal dining')
    issues.push({
      field: 'sqft',
      severity: 'error',
      message: 'Not enough space for this configuration.',
      detail: `Your selections (${parts.join(', ')}) need at least ${minSqft.toLocaleString()} sqft. You set ${sqft.toLocaleString()} sqft. Increase size or reduce rooms.`,
    })
  }

  const baseOverhead = 528 + (primarySuite ? 240 : 168)
  const maxSecondary = Math.max(0, Math.floor((sqft - baseOverhead) / 100))
  if (secondary > maxSecondary && sqft >= minSqft) {
    issues.push({
      field: 'bedrooms',
      severity: 'error',
      message: `${bedrooms} bedrooms is not feasible in ${sqft.toLocaleString()} sqft.`,
      detail: `After essential rooms, only ${sqft - baseOverhead} sqft remains for secondary bedrooms (${maxSecondary} max at 100 sqft each). Reduce to ${maxSecondary + 1} total or increase sqft.`,
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

  if (floors === 2 && sqft < 1200) {
    issues.push({
      field: 'floors',
      severity: 'warning',
      message: 'Two-story layout under 1,200 sqft is cramped.',
      detail: 'Staircase overhead is significant in small homes. Consider single-story or 1,200+ sqft.',
    })
  }

  if (garage === '3car' && sqft < 1800) {
    issues.push({
      field: 'garage',
      severity: 'warning',
      message: 'A 3-car garage is disproportionate for this home size.',
      detail: `3-car garages suit 1,800+ sqft homes. With ${sqft.toLocaleString()} sqft, a 1 or 2-car garage fits better.`,
    })
  }

  return issues
}
