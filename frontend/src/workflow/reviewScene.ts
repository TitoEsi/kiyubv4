import type { FloorPlan } from '../types/floorplan'
import type { SceneDocument } from '../scene-graph/types'
import { isSceneDocument } from '../scene-graph/edit/load-scene'

export type ReviewDetail = {
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
  const submitted = detail.submitted_revision
  if (submitted && isSceneDocument(submitted.scene_document)) {
    return {
      scene: submitted.scene_document,
      revisionId: submitted.id || null,
      floorPlan: submitted.floor_plan || null,
    }
  }
  return {
    scene: null,
    revisionId: null,
    floorPlan: detail.current_revision?.floor_plan || null,
  }
}
