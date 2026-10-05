import { describe, expect, it } from 'vitest'
import { renderToStaticMarkup } from 'react-dom/server'
import { ArrowsOut } from '@phosphor-icons/react'
import RoomsPanel from './RoomsPanel'
import { planRoomRows } from './room-rows'
import { FIDELITY_PLAN } from '../scene-graph/adapters/fidelity.fixture'
import { DEFAULT_UNIT, formatArea, formatDimensions } from '../units/measurement'
import type { Room } from '../types/floorplan'

const noop = () => {}
const text = (s: string) => renderToStaticMarkup(<>{s}</>)

/** The Client inspector list as it was written inline in FloorPlanEditor. */
function LegacyClientList({ rooms, selectedId }: { rooms: Room[]; selectedId: string | null }) {
  return (
    <div className="inspector-section">
      <div className="inspector-title">Rooms</div>
      <div className="room-list">
        {rooms.map(room => (
          <div key={room.id} className={`room-item ${room.id === selectedId ? 'selected' : ''}`} role="button" tabIndex={0}>
            <div className="room-swatch" style={{ background: room.color }} />
            <div style={{ flex: 1 }}>
              <div className="room-item-name">{room.name}</div>
              <div className="room-item-size">
                {formatDimensions(room.width, room.height, DEFAULT_UNIT)} · {formatArea(room.width * room.height, DEFAULT_UNIT)}
              </div>
            </div>
            <button type="button" className="room-interior-btn" aria-label={`View interior of ${room.name}`}>
              <ArrowsOut size={14} />
            </button>
          </div>
        ))}
      </div>
    </div>
  )
}

describe('RoomsPanel', () => {
  const rooms = FIDELITY_PLAN.rooms

  it('renders the same markup as the original Client list', () => {
    const selected = rooms[1].id
    const html = renderToStaticMarkup(
      <RoomsPanel rooms={planRoomRows(rooms)} selectedId={selected} onSelect={noop} onExpand={noop} />,
    )
    expect(html).toBe(renderToStaticMarkup(<LegacyClientList rooms={rooms} selectedId={selected} />))
  })

  it('shows heading, swatch, name, dimensions, area and one selected row', () => {
    const html = renderToStaticMarkup(
      <RoomsPanel rooms={planRoomRows(rooms)} selectedId={rooms[0].id} onSelect={noop} onExpand={noop} />,
    )
    expect(html).toContain('<div class="inspector-title">Rooms</div>')
    for (const r of rooms) {
      expect(html).toContain(`background:${r.color}`)
      expect(html).toContain(`>${text(r.name)}<`)
      expect(html).toContain(text(formatDimensions(r.width, r.height, DEFAULT_UNIT)))
      expect(html).toContain(text(formatArea(r.width * r.height, DEFAULT_UNIT)))
    }
    expect(html.match(/class="room-item selected"/g)).toHaveLength(1)
    expect(html.match(/class="room-interior-btn"/g)).toHaveLength(rooms.length)
  })
})

describe('RoomsPanel expand label', () => {
  it('defaults to the Client interior label and accepts an override', () => {
    const rows = planRoomRows(FIDELITY_PLAN.rooms)
    const name = text(FIDELITY_PLAN.rooms[0].name)
    const client = renderToStaticMarkup(<RoomsPanel rooms={rows} selectedId={null} onSelect={noop} onExpand={noop} />)
    const focus = renderToStaticMarkup(
      <RoomsPanel rooms={rows} selectedId={null} onSelect={noop} onExpand={noop} expandLabel={n => `Focus ${n}`} />,
    )
    expect(client).toContain(`aria-label="View interior of ${name}"`)
    expect(focus).toContain(`aria-label="Focus ${name}"`)
    expect(focus).not.toContain('View interior')
  })
})
