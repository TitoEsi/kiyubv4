import type { SceneDocument } from '../types'

export function cloneScene(scene: SceneDocument): SceneDocument {
  const next = structuredClone(scene)
  if (!next.furniture) next.furniture = []
  if (!next.openings) next.openings = []
  if (!next.walls) next.walls = []
  return next
}

export function touchScene(scene: SceneDocument): SceneDocument {
  const next = cloneScene(scene)
  next.metadata = {
    ...next.metadata,
    updatedAt: new Date().toISOString(),
  }
  return next
}
