import type { SceneDocument } from '../scene-graph/types'
import type { SiteLot } from '../scene-graph/site/site-context'
import type { QuestionnaireData } from '../types/questionnaire'
import { displayNameFromEmail } from './displayName'

export const PUBLISHED_PLAN_UNAVAILABLE = 'Published floor plan is unavailable.'

/** The frozen published scene and the sheet metadata the PDF is allowed to read. */
export interface PublishedExport {
  scene: SceneDocument
  lot: SiteLot | null
  projectId: string
  revisionId: string
  projectName: string
  clientName: string
  version: number
  publishedAt: string | null
  questionnaire: QuestionnaireData
}

export function clientLabel(clientEmail?: string | null, invitationEmail?: string | null): string {
  const email = clientEmail || invitationEmail
  return email ? displayNameFromEmail(email) : 'Not assigned'
}

export function buildPublishedExport(input: {
  status?: string
  projectId: string
  projectName: string
  clientEmail?: string | null
  invitationEmail?: string | null
  scene: SceneDocument | null
  revisionId: string | null
  version: number | null
  publishedAt: string | null
  lot: SiteLot | null
  questionnaire: QuestionnaireData
}): PublishedExport | null {
  if (input.status !== 'PUBLISHED') return null
  const scene = input.scene
  if (!scene || !input.revisionId || input.version == null) return null
  if (!scene.walls?.length && !scene.rooms?.length) return null
  return {
    scene,
    lot: input.lot,
    projectId: input.projectId,
    revisionId: input.revisionId,
    projectName: input.projectName || 'Project',
    clientName: clientLabel(input.clientEmail, input.invitationEmail),
    version: input.version,
    publishedAt: input.publishedAt,
    questionnaire: input.questionnaire,
  }
}
