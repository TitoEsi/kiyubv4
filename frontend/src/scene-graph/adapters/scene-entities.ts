import type { SceneDocument } from '../types'
import { wallLength } from '../edit/geometry'
import type { FloorPlan } from '../../types/floorplan'

export function sceneRenderIds(scene: SceneDocument) {
  return {
    rooms: scene.rooms.map(r => r.id).sort(),
    walls: scene.walls.filter(w => wallLength(w) > 0.05).map(w => w.id).sort(),
    openings: scene.openings.map(o => o.id).sort(),
    furniture: (scene.furniture || []).map(f => f.id).sort(),
  }
}

export function fidelityReport(plan: FloorPlan, scene: SceneDocument) {
  const planOpenings = [...(plan.openings || []).map(o => o.id), ...(plan.doors || []).map(d => d.id).filter(Boolean) as string[]]
  const uniquePlanOpenings = Array.from(new Set(planOpenings))
  const rows = [
    ...plan.rooms.map(r => ({ kind: 'room', id: r.id, name: r.name, inPlan: true, inScene: scene.rooms.some(s => s.id === r.id) })),
    ...uniquePlanOpenings.map(id => ({ kind: 'opening', id, name: id, inPlan: true, inScene: scene.openings.some(s => s.id === id) })),
    ...(plan.furniture || []).map(f => ({ kind: 'furniture', id: f.id, name: f.kind, inPlan: true, inScene: (scene.furniture || []).some(s => s.id === f.id) })),
  ]
  return rows
}
