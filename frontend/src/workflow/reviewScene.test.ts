import { describe, expect, it } from 'vitest'
import { clientVisibleScene } from './reviewScene'
import type { FloorPlan } from '../types/floorplan'

function scene(label: string) {
  return {
    version: '2.0' as const,
    units: 'metric' as const,
    walls: [],
    rooms: [{ id: label, name: label, position: { x: 0, y: 0 }, dimensions: { width: 3, height: 3 } }],
    openings: [],
    furniture: [],
    site: { width: 10, depth: 10 },
  }
}

const generated = { id: 'gen', name: 'Generated', rooms: [] } as unknown as FloorPlan
const submittedPlan = { id: 'sub', name: 'Submitted', rooms: [] } as unknown as FloorPlan

describe('clientVisibleScene', () => {
  it('prefers the submitted review SceneDocument', () => {
    const visible = clientVisibleScene({
      submitted_revision: { id: 'rev-b', scene_document: scene('B'), floor_plan: submittedPlan },
      current_revision: { id: 'rev-a', scene_document: scene('A'), floor_plan: generated },
      document: { working_scene_document: scene('C') },
    })
    expect(visible.revisionId).toBe('rev-b')
    expect(visible.scene?.rooms[0].id).toBe('B')
    expect(visible.floorPlan?.id).toBe('sub')
  })

  it('falls back to current floor plan when no review snapshot exists', () => {
    const visible = clientVisibleScene({
      current_revision: { id: 'rev-a', floor_plan: generated },
      document: { working_scene_document: scene('C') },
    })
    expect(visible.scene).toBeNull()
    expect(visible.revisionId).toBeNull()
    expect(visible.floorPlan?.id).toBe('gen')
  })

  it('ignores architect draft working copies', () => {
    const visible = clientVisibleScene({
      submitted_revision: { id: 'rev-b', scene_document: scene('B'), floor_plan: submittedPlan },
      document: { working_scene_document: scene('C') },
    })
    expect(visible.scene?.rooms[0].id).toBe('B')
  })
})
