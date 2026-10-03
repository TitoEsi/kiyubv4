import { LotShape } from './floorplan'
import { legacySquareFeetToSquareMeters } from '../units/measurement'

export type GarageChoice = 'none' | '1car' | '2car' | '3car'
export type LaundryChoice = 'none' | 'closet' | 'room'
export type OutdoorChoice = 'none' | 'patio' | 'deck' | 'both'
export type CeilingHeight = 'standard' | 'high' | 'vaulted'

/** User requirements from the KIYUB questionnaire. No generator internals. */
export interface QuestionnaireData {
  site: {
    lotShape: LotShape
    lotWidth: number
    lotDepth: number
  }
  house: {
    floors: number
    bedrooms: number
    bathrooms: number
    /** Square meters. Legacy briefs stored `livingAreaSqft`; see units/legacy.ts. */
    livingAreaM2: number
  }
  spaces: {
    homeOffice: boolean
    laundry: LaundryChoice
    garage: GarageChoice
    outdoor: OutdoorChoice
  }
  preferences: {
    style: string
    openPlan: boolean
    primarySuite: boolean
    formalDining: boolean
    ceilingHeight: CeilingHeight
  }
}

/** Initial questionnaire field defaults only — not generation overrides. */
export const initialQuestionnaire: QuestionnaireData = {
  site: {
    lotShape: 'rectangle',
    lotWidth: 20,
    lotDepth: 30,
  },
  house: {
    floors: 1,
    bedrooms: 3,
    bathrooms: 2,
    livingAreaM2: legacySquareFeetToSquareMeters(1800),
  },
  spaces: {
    homeOffice: false,
    laundry: 'room',
    garage: '2car',
    outdoor: 'patio',
  },
  preferences: {
    style: 'modern',
    openPlan: false,
    primarySuite: true,
    formalDining: false,
    ceilingHeight: 'standard',
  },
}
