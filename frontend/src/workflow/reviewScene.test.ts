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
const publishedPlan = { id: 'pub', name: 'Published', rooms: [] } as unknown as FloorPlan

describe('clientVisibleScene', () => {
  it('pins the submitted review SceneDocument during an active checking cycle', () => {
    const visible = clientVisibleScene({
      project: { status: 'FOR_CHECKING' },
      submitted_revision: { id: 'rev-b', version: 2, scene_document: scene('B'), floor_plan: submittedPlan },
      current_revision: { id: 'rev-a', version: 2, scene_document: scene('A'), floor_plan: generated },
      document: { working_scene_document: scene('C') },
    })
    expect(visible.revisionId).toBe('rev-b')
    expect(visible.scene?.rooms[0].id).toBe('B')
    expect(visible.floorPlan?.id).toBe('sub')
  })

  it('falls back to current floor plan when no review snapshot exists', () => {
    const visible = clientVisibleScene({
      project: { status: 'IN_PROGRESS' },
      current_revision: { id: 'rev-a', version: 1, floor_plan: generated },
      document: { working_scene_document: scene('C') },
    })
    expect(visible.scene).toBeNull()
    expect(visible.revisionId).toBe('rev-a')
    expect(visible.floorPlan?.id).toBe('gen')
  })

  it('ignores architect draft working copies while checking', () => {
    const visible = clientVisibleScene({
      project: { status: 'FOR_CHECKING' },
      submitted_revision: { id: 'rev-b', version: 2, scene_document: scene('B'), floor_plan: submittedPlan },
      current_revision: { id: 'rev-a', version: 2, floor_plan: generated },
      document: { working_scene_document: scene('C') },
    })
    expect(visible.scene?.rooms[0].id).toBe('B')
  })

  it('does not pin a stale review after a newer revision is current', () => {
    const visible = clientVisibleScene({
      project: { status: 'FOR_CHECKING' },
      submitted_revision: { id: 'rev-b', version: 2, scene_document: scene('B'), floor_plan: submittedPlan },
      current_revision: { id: 'rev-c', version: 3, scene_document: scene('C'), floor_plan: generated },
    })
    expect(visible.revisionId).toBe('rev-c')
    expect(visible.scene?.rooms[0].id).toBe('C')
    expect(visible.floorPlan?.id).toBe('gen')
  })

  it('pins the approved review until the project is published', () => {
    const visible = clientVisibleScene({
      project: { status: 'APPROVED' },
      submitted_revision: { id: 'rev-b', version: 2, scene_document: scene('B'), floor_plan: submittedPlan },
      current_revision: { id: 'rev-a', version: 1, scene_document: scene('A'), floor_plan: generated },
    })
    expect(visible.revisionId).toBe('rev-b')
    expect(visible.scene?.rooms[0].id).toBe('B')
  })

  it('uses the published current revision after publication', () => {
    const visible = clientVisibleScene({
      project: { status: 'PUBLISHED' },
      submitted_revision: { id: 'rev-b', version: 2, scene_document: scene('B'), floor_plan: submittedPlan },
      current_revision: { id: 'rev-p', version: 8, scene_document: scene('PUBLISHED-CURRENT'), floor_plan: publishedPlan },
    })
    expect(visible.revisionId).toBe('rev-p')
    expect(visible.scene?.rooms[0].id).toBe('PUBLISHED-CURRENT')
    expect(visible.floorPlan?.id).toBe('pub')
  })

  it('does not pin review after the project leaves checking without approval', () => {
    const visible = clientVisibleScene({
      project: { status: 'IN_PROGRESS' },
      submitted_revision: { id: 'rev-b', version: 2, scene_document: scene('B'), floor_plan: submittedPlan },
      current_revision: { id: 'rev-a', version: 2, floor_plan: generated },
    })
    expect(visible.scene).toBeNull()
    expect(visible.floorPlan?.id).toBe('gen')
  })
})
