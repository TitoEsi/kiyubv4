import { ArchitecturalSpecification } from '../types/architectural-specification'
import { Constraints } from '../types/floorplan'

/**
 * Translate KIYUB architectural requirements into the existing
 * generation engine request shape. Always emits a complete payload
 * so backend missing-key defaults cannot fill in a program.
 */
export function specificationToConstraints(
  spec: ArchitecturalSpecification
): Constraints {
  return {
    lotShape: spec.site.shape,
    lotWidth: spec.site.width,
    lotDepth: spec.site.depth,
    bedrooms: spec.building.bedrooms,
    bathrooms: spec.building.bathrooms,
    livingAreaM2: spec.building.livingAreaM2,
    stories: spec.building.floors,
    style: spec.style,
    openPlan: spec.features.openPlan,
    primarySuite: spec.features.primarySuite,
    homeOffice: spec.features.homeOffice,
    formalDining: spec.features.formalDining,
    garage: spec.features.garage,
    laundry: spec.features.laundry,
    outdoor: spec.features.outdoor,
    ceilingHeight: spec.features.ceilingHeight,
  }
}
