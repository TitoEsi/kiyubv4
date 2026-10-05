import { describe, expect, it } from 'vitest'
import { floorPlanToSceneDocument } from '../scene-graph/adapters/floorplan-to-scene-document'
import { FIDELITY_PLAN } from '../scene-graph/adapters/fidelity.fixture'
import { initialQuestionnaire } from '../types/questionnaire'
import { buildPublishedExport } from './publishedExport'

const scene = floorPlanToSceneDocument(FIDELITY_PLAN, { lotWidth: 15, lotDepth: 20, stories: 1 })

const ready = {
  projectId: 'p1',
  projectName: 'Lot A',
  scene,
  revisionId: 'rev-9',
  version: 4,
  publishedAt: '2026-10-05T02:15:00.000Z',
  lot: { width: 15, depth: 20, shape: 'rectangle' },
  questionnaire: initialQuestionnaire,
}

describe('buildPublishedExport', () => {
  it('is null before publication', () => {
    expect(buildPublishedExport({ ...ready, status: 'APPROVED' })).toBeNull()
    expect(buildPublishedExport({ ...ready, status: 'DRAFT' })).toBeNull()
    expect(buildPublishedExport({ ...ready, status: 'FOR_CHECKING' })).toBeNull()
  })

  it('is null when a published project has no scene', () => {
    expect(buildPublishedExport({ ...ready, status: 'PUBLISHED', scene: null })).toBeNull()
    expect(buildPublishedExport({ ...ready, status: 'PUBLISHED', revisionId: null })).toBeNull()
    expect(buildPublishedExport({ ...ready, status: 'PUBLISHED', version: null })).toBeNull()
    expect(buildPublishedExport({
      ...ready,
      status: 'PUBLISHED',
      scene: { ...scene, walls: [], rooms: [] },
    })).toBeNull()
  })

  it('returns the published SceneDocument itself', () => {
    const built = buildPublishedExport({ ...ready, status: 'PUBLISHED' })
    expect(built).not.toBeNull()
    expect(built!.scene).toBe(scene)
    expect(built!.version).toBe(4)
    expect(built!.revisionId).toBe('rev-9')
    expect(built!.projectName).toBe('Lot A')
  })
})
