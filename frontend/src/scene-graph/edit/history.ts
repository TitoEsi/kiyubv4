import type { SceneDocument } from '../types'
import { cloneScene } from './clone'

export interface EditorHistory {
  past: SceneDocument[]
  present: SceneDocument
  future: SceneDocument[]
}

export function createHistory(present: SceneDocument): EditorHistory {
  return { past: [], present, future: [] }
}

export function commit(history: EditorHistory, next: SceneDocument): EditorHistory {
  return {
    past: [...history.past, history.present].slice(-80),
    present: next,
    future: [],
  }
}

export function undo(history: EditorHistory): EditorHistory {
  const prev = history.past[history.past.length - 1]
  if (!prev) return history
  return {
    past: history.past.slice(0, -1),
    present: prev,
    future: [history.present, ...history.future],
  }
}

export function redo(history: EditorHistory): EditorHistory {
  const nxt = history.future[0]
  if (!nxt) return history
  return {
    past: [...history.past, history.present],
    present: nxt,
    future: history.future.slice(1),
  }
}

export function replacePresent(history: EditorHistory, present: SceneDocument): EditorHistory {
  return { ...history, present: cloneScene(present) }
}
