import { ArchitecturalSpecification } from '../types/architectural-specification'
import { QuestionnaireData } from '../types/questionnaire'

/**
 * Convert user questionnaire input into architectural requirements.
 * Copies the user's numbers; does not substitute a default program.
 */
export function questionnaireToSpecification(
  data: QuestionnaireData
): ArchitecturalSpecification {
  const required: string[] = ['kitchen', 'living_room', 'foyer']

  required.push('primary_bedroom')
  for (let i = 1; i < data.house.bedrooms; i++) {
    required.push(`bedroom_${i + 1}`)
  }

  for (let i = 0; i < data.house.bathrooms; i++) {
    required.push(i === 0 ? 'bathroom_1' : `bathroom_${i + 1}`)
  }

  if (data.preferences.formalDining) required.push('dining_room')
  if (data.spaces.homeOffice) required.push('home_office')
  if (data.spaces.laundry !== 'none') required.push('laundry')
  if (data.spaces.garage !== 'none') required.push('garage')
  if (data.spaces.outdoor === 'patio' || data.spaces.outdoor === 'both') {
    required.push('patio')
  }
  if (data.spaces.outdoor === 'deck' || data.spaces.outdoor === 'both') {
    required.push('deck')
  }

  return {
    site: {
      shape: data.site.lotShape,
      width: data.site.lotWidth,
      depth: data.site.lotDepth,
    },
    building: {
      floors: data.house.floors,
      bedrooms: data.house.bedrooms,
      bathrooms: data.house.bathrooms,
      livingAreaSqft: data.house.livingAreaSqft,
    },
    rooms: { required },
    features: {
      garage: data.spaces.garage,
      outdoor: data.spaces.outdoor,
      laundry: data.spaces.laundry,
      openPlan: data.preferences.openPlan,
      primarySuite: data.preferences.primarySuite,
      formalDining: data.preferences.formalDining,
      homeOffice: data.spaces.homeOffice,
      ceilingHeight: data.preferences.ceilingHeight,
    },
    style: data.preferences.style,
  }
}
