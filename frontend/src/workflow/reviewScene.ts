import type { FloorPlan } from '../types/floorplan'
import type { SceneDocument } from '../scene-graph/types'
import { isSceneDocument } from '../scene-graph/edit/load-scene'

export type ReviewDetail = {
  project?: {
    status?: string
  } | null
  submitted_revision?: {
    id?: string
    scene_document?: unknown
    floor_plan?: FloorPlan
  } | null
  current_revision?: {
    id?: string
    scene_document?: unknown
    floor_plan?: FloorPlan
  } | null
  document?: {
    working_scene_document?: unknown
  }
}

export function clientVisibleScene(detail: ReviewDetail): {
  scene: SceneDocument | null
  revisionId: string | null
  floorPlan: FloorPlan | null
} {
  // REVIEW is only the visible source while the project is actually awaiting
  // checking. Once approved/published, the formal current revision is the source
  // of truth and the old REVIEW snapshot must not override it.
  if (detail.project?.status === 'FOR_CHECKING') {
    const submitted = detail.submitted_revision
    if (submitted && isSceneDocument(submitted.scene_document)) {
      return {
        scene: submitted.scene_document,
        revisionId: submitted.id || null,
        floorPlan: submitted.floor_plan || null,
      }
    }
  }

  const current = detail.current_revision
  if (current && isSceneDocument(current.scene_document)) {
    return {
      scene: current.scene_document,
      revisionId: current.id || null,
      floorPlan: current.floor_plan || null,
    }
  }

  return {
    scene: null,
    revisionId: null,
    floorPlan: current?.floor_plan || null,
  }
}
