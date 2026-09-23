import type { Point2D, SceneDocument } from '../types'
import { cloneScene, touchScene } from './clone'

export function moveFurniture(scene: SceneDocument, id: string, to: Point2D): SceneDocument {
  const next = cloneScene(scene)
  const item = (next.furniture || []).find(f => f.id === id)
  if (!item) return scene
  item.position = { ...to }
  return touchScene(next)
}

export function rotateFurniture(scene: SceneDocument, id: string, deltaDeg = 90): SceneDocument {
  const next = cloneScene(scene)
  const item = (next.furniture || []).find(f => f.id === id)
  if (!item) return scene
  item.rotation = ((item.rotation || 0) + deltaDeg) % 360
  return touchScene(next)
}

export function deleteFurniture(scene: SceneDocument, id: string): SceneDocument {
  const next = cloneScene(scene)
  next.furniture = (next.furniture || []).filter(f => f.id !== id)
  return touchScene(next)
}
