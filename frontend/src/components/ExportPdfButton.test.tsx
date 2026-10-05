import { describe, expect, it } from 'vitest'
import { renderToStaticMarkup } from 'react-dom/server'
import { floorPlanToSceneDocument } from '../scene-graph/adapters/floorplan-to-scene-document'
import { FIDELITY_PLAN } from '../scene-graph/adapters/fidelity.fixture'
import { initialQuestionnaire } from '../types/questionnaire'
import { buildPublishedExport } from '../workflow/publishedExport'
import ExportPdfButton from './ExportPdfButton'

const scene = floorPlanToSceneDocument(FIDELITY_PLAN, { lotWidth: 15, lotDepth: 20, stories: 1 })
const published = buildPublishedExport({
  status: 'PUBLISHED',
  projectId: 'p1',
  projectName: 'Lot A',
  scene,
  revisionId: 'rev-9',
  version: 3,
  publishedAt: null,
  lot: null,
  questionnaire: initialQuestionnaire,
})

describe('ExportPdfButton', () => {
  it('is disabled when the project is not published', () => {
    const html = renderToStaticMarkup(<ExportPdfButton published={null} />)
    expect(html).toMatch(/<button[^>]* disabled=""/)
    expect(html).toContain('Export is available after the project is published')
    expect(html).toContain('aria-disabled="true"')
  })

  it('is enabled for the published scene and names that version', () => {
    const html = renderToStaticMarkup(<ExportPdfButton published={published} />)
    expect(html).not.toMatch(/<button[^>]* disabled=""/)
    expect(html).toContain('Exports Published Version v3')
    expect(html).toContain('aria-disabled="false"')
  })
})
