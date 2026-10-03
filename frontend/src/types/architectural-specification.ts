import { LotShape } from './floorplan'
import { CeilingHeight, GarageChoice, LaundryChoice, OutdoorChoice } from './questionnaire'

/** Architectural requirements derived from the questionnaire. No geometry. */
export interface ArchitecturalSpecification {
  site: {
    shape: LotShape
    width: number
    depth: number
  }
  building: {
    floors: number
    bedrooms: number
    bathrooms: number
    /** Square meters. */
    livingAreaM2: number
  }
  rooms: {
    required: string[]
  }
  features: {
    garage: GarageChoice
    outdoor: OutdoorChoice
    laundry: LaundryChoice
    openPlan: boolean
    primarySuite: boolean
    formalDining: boolean
    homeOffice: boolean
    ceilingHeight: CeilingHeight
  }
  style: string
}
