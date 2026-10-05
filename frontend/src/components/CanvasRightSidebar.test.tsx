import { describe, expect, it } from 'vitest'
import { renderToStaticMarkup } from 'react-dom/server'
import CanvasRightSidebar from './CanvasRightSidebar'
import ArchitectCanvas from './ArchitectCanvas'
import RoomsPanel from './RoomsPanel'
import { MeasurementInput } from './MeasurementInput'
import { planRoomRows, planSummary, sceneRoomRows, sceneSummary } from './room-rows'
import { FIDELITY_PLAN } from '../scene-graph/adapters/fidelity.fixture'
import { floorPlanToSceneDocument } from '../scene-graph/adapters/floorplan-to-scene-document'
import { ROOM_MAX_M, ROOM_MIN_M } from '../scene-graph/edit/room-ops'
import { DEFAULT_UNIT, formatArea, formatDimensions, formatMeasurement } from '../units/measurement'
import type { FloorPlan } from '../types/floorplan'

const noop = () => {}
const text = (s: string) => renderToStaticMarkup(<>{s}</>)
const plan = FIDELITY_PLAN

/** The Client inspector as it was written inline in FloorPlanEditor. */
function LegacyClientInspector({ plan, selectedId, readOnly }: { plan: FloorPlan; selectedId: string | null; readOnly: boolean }) {
  const selectedRoom = plan.rooms.find(r => r.id === selectedId)
  const ceilH = plan.ceilingHeight || 2.7432
  const livingAreaM2 = plan.rooms
    .filter(r => !['garage', 'patio', 'deck', 'rear_patio', 'outdoor_living', 'front_porch'].includes(r.type))
    .reduce((s, r) => s + r.width * r.height, 0)
  return (
    <div className="inspector">
      <RoomsPanel rooms={planRoomRows(plan.rooms)} selectedId={selectedId} onSelect={noop} onExpand={noop} />
      {selectedRoom && (
        <div className="inspector-section room-edit">
          <div className="inspector-title">{readOnly ? 'Room' : 'Edit Room'}</div>
          <div className="inspector-name">{selectedRoom.name}</div>
          <div className="inspector-field">
            <label htmlFor="room-width">Width ({DEFAULT_UNIT})</label>
            <MeasurementInput id="room-width" min={ROOM_MIN_M} max={ROOM_MAX_M} value={selectedRoom.width} disabled={readOnly} showUnit={false} onCommit={noop} />
          </div>
          <div className="inspector-field">
            <label htmlFor="room-depth">Depth ({DEFAULT_UNIT})</label>
            <MeasurementInput id="room-depth" min={ROOM_MIN_M} max={ROOM_MAX_M} value={selectedRoom.height} disabled={readOnly} showUnit={false} onCommit={noop} />
          </div>
          <div className="inspector-area">{formatArea(selectedRoom.width * selectedRoom.height, DEFAULT_UNIT)}</div>
          <button type="button" className="view-interior-btn">
            View Interior
          </button>
        </div>
      )}
      <div className="inspector-section stats">
        <div className="inspector-title">Summary</div>
        <div className="stat-row"><span>Rooms</span><span>{plan.rooms.length}</span></div>
        <div className="stat-row">
          <span>Living area</span>
          <span>{formatArea(livingAreaM2, DEFAULT_UNIT)}</span>
        </div>
        <div className="stat-row">
          <span>Building footprint</span>
          <span>{formatDimensions(plan.totalWidth, plan.totalHeight, DEFAULT_UNIT)}</span>
        </div>
        <div className="stat-row"><span>Ceiling Height</span><span>{formatMeasurement(ceilH, DEFAULT_UNIT)}</span></div>
      </div>
    </div>
  )
}

function clientSidebar(selectedId: string | null, readOnly: boolean) {
  return renderToStaticMarkup(
    <CanvasRightSidebar
      rooms={planRoomRows(plan.rooms)}
      selectedId={selectedId}
      onSelect={noop}
      onExpand={noop}
      summary={planSummary(plan)}
      roomTitle={readOnly ? 'Room' : 'Edit Room'}
      editable={!readOnly}
      onResize={noop}
      onViewInterior={noop}
    />,
  )
}

describe('CanvasRightSidebar, Client configuration', () => {
  it.each([
    [null, false],
    [plan.rooms[0].id, false],
    [plan.rooms[1].id, true],
  ])('matches the original inspector markup (selected=%s, readOnly=%s)', (selectedId, readOnly) => {
    expect(clientSidebar(selectedId, readOnly))
      .toBe(renderToStaticMarkup(<LegacyClientInspector plan={plan} selectedId={selectedId} readOnly={readOnly} />))
  })
})

describe('CanvasRightSidebar, Architect configuration', () => {
  const scene = floorPlanToSceneDocument(plan, { lotWidth: 15, lotDepth: 20, stories: 1 })
  const rows = sceneRoomRows(scene)
  const summary = sceneSummary(scene)
  const render = (selectedId: string | null) => renderToStaticMarkup(
    <CanvasRightSidebar
      id="architect-sidebar"
      aria-label="Plan details"
      rooms={rows}
      selectedId={selectedId}
      onSelect={noop}
      onExpand={noop}
      expandLabel={n => `Focus ${n}`}
      summary={summary}
      roomTitle="Room"
      editable
      onResize={noop}
      emptyHint="Select a room"
    />,
  )

  it('shows "Select a room" instead of room details when nothing is selected', () => {
    const html = render(null)
    expect(html).toContain('<div class="inspector-title">Room</div><div class="inspector-area">Select a room</div>')
    expect(html).not.toContain('id="room-width"')
  })

  it('shows editable dimensions and area for the selected room, without View Interior', () => {
    const row = rows[0]
    const html = render(row.id)
    expect(html).toContain(`<div class="inspector-name">${text(row.name)}</div>`)
    expect(html).toMatch(/<input id="room-width"(?![^>]*disabled)/)
    expect(html).toMatch(/<input id="room-depth"(?![^>]*disabled)/)
    expect(html).toContain(`<div class="inspector-area">${text(formatArea(row.area, DEFAULT_UNIT))}</div>`)
    expect(html).not.toContain('View Interior')
    expect(html).not.toContain('View interior')
    expect(html).not.toContain('Select a room')
  })

  it('renders summary values from the scene', () => {
    const html = render(null)
    expect(html).toContain(`<span>Rooms</span><span>${scene.rooms.length}</span>`)
    expect(html).toContain('Building footprint')
    expect(html).toContain('Ceiling Height')
    expect(html).toContain(text(formatArea(summary.livingAreaM2, DEFAULT_UNIT)))
    expect(html).toContain(text(formatDimensions(summary.footprintW, summary.footprintD, DEFAULT_UNIT)))
    expect(html).toContain(text(formatMeasurement(summary.ceilingM, DEFAULT_UNIT)))
  })
})

describe('ArchitectCanvas sidebar', () => {
  const scene = floorPlanToSceneDocument(plan, { lotWidth: 15, lotDepth: 20, stories: 1 })
  const render = (editingEnabled: boolean, onBack?: () => void) => renderToStaticMarkup(
    <ArchitectCanvas scene={scene} onSceneChange={noop} onCommit={noop} onBack={onBack} editingEnabled={editingEnabled} />,
  )

  it('puts a Back to Project icon first in the toolbar and offers no version-creating save', () => {
    const html = render(true, noop)
    const toolbar = html.slice(html.indexOf('aria-label="Architect tools"'))
    expect(toolbar).toMatch(/^aria-label="Architect tools"><button type="button" class="architect-back" title="Back to Project" aria-label="Back to Project">/)
    expect(html).not.toContain('Save Revision')
    expect(html).not.toContain('Accept candidate')
  })

  it('omits the back icon when no back action is given', () => {
    expect(render(true)).not.toContain('Back to Project')
  })

  it('renders the unified sidebar beside the stage, open by default', () => {
    const html = render(true)
    expect(html).toMatch(/<div class="architect-body"><div class="architect-stage">[\s\S]*<div id="architect-sidebar" class="inspector" aria-label="Plan details">/)
    expect(html).toMatch(/aria-pressed="true" aria-controls="architect-sidebar"/)
    for (const row of sceneRoomRows(scene)) expect(html).toContain(`aria-label="Focus ${text(row.name)}"`)
    expect(html).toContain('Select a room')
    expect(html).toContain('<div class="inspector-title">Summary</div>')
    expect(html).not.toContain('View interior')
  })

  it('keeps the existing toolbar tools and zoom controls', () => {
    const html = render(true)
    for (const label of ['Select', 'Wall', 'Door', 'Window', 'Measure', 'Undo', 'Redo']) {
      expect(html).toContain(`aria-label="${label}"`)
    }
    const stage = html.slice(html.indexOf('class="architect-stage"'), html.indexOf('id="architect-sidebar"'))
    expect(stage).toContain('class="architect-zoom"')
  })
})
