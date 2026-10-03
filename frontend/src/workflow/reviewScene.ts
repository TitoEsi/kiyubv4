import type { FloorPlan } from '../types/floorplan'
import type { SceneDocument } from '../scene-graph/types'
import { isSceneDocument } from '../scene-graph/edit/load-scene'

export type ReviewDetail = {
  project?: { status?: string }
  submitted_revision?: {
    id?: string
    version?: number
    scene_document?: unknown
    floor_plan?: FloorPlan
  } | null
  current_revision?: {
    id?: string
    version?: number
    scene_document?: unknown
    floor_plan?: FloorPlan
  } | null
  document?: {
    working_scene_document?: unknown
  }
}

function pinSubmittedReview(detail: ReviewDetail): boolean {
  const status = detail.project?.status
  if (status !== 'FOR_CHECKING' && status !== 'APPROVED') return false
  const submitted = detail.submitted_revision
  if (!submitted || !isSceneDocument(submitted.scene_document)) return false
  if (status === 'APPROVED') return true
  const currentVersion = detail.current_revision?.version ?? 0
  const submittedVersion = submitted.version ?? 0
  return !(currentVersion > submittedVersion)
}

function fromRevision(rev: ReviewDetail['current_revision'] | ReviewDetail['submitted_revision']) {
  if (!rev) {
    return { scene: null as SceneDocument | null, revisionId: null as string | null, floorPlan: null as FloorPlan | null }
  }
  return {
    scene: isSceneDocument(rev.scene_document) ? rev.scene_document : null,
    revisionId: rev.id || null,
    floorPlan: rev.floor_plan || null,
  }
}

export function clientVisibleScene(detail: ReviewDetail): {
  scene: SceneDocument | null
  revisionId: string | null
  floorPlan: FloorPlan | null
} {
  if (pinSubmittedReview(detail) && detail.submitted_revision) {
    return fromRevision(detail.submitted_revision)
  }
  return fromRevision(detail.current_revision)
}
