import { ArrowsOut } from '@phosphor-icons/react'
import { useFormat } from '../units/UnitsProvider'
import type { RoomRow } from './room-rows'

export default function RoomsPanel({
  rooms,
  selectedId,
  onSelect,
  onExpand,
  expandLabel = name => `View interior of ${name}`,
}: {
  rooms: RoomRow[]
  selectedId: string | null
  onSelect: (id: string | null) => void
  onExpand: (id: string) => void
  expandLabel?: (name: string) => string
}) {
  const fmt = useFormat()
  const toggle = (id: string) => onSelect(id === selectedId ? null : id)

  return (
    <div className="inspector-section">
      <div className="inspector-title">Rooms</div>
      <div className="room-list">
        {rooms.map(room => (
          <div
            key={room.id}
            className={`room-item ${room.id === selectedId ? 'selected' : ''}`}
            role="button"
            tabIndex={0}
            onClick={() => toggle(room.id)}
            onKeyDown={e => {
              if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault()
                toggle(room.id)
              }
            }}
          >
            <div className="room-swatch" style={{ background: room.color }} />
            <div style={{ flex: 1 }}>
              <div className="room-item-name">{room.name}</div>
              <div className="room-item-size">
                {fmt.dims(room.width, room.depth)} · {fmt.area(room.area)}
              </div>
            </div>
            <button
              type="button"
              className="room-interior-btn"
              aria-label={expandLabel(room.name)}
              onClick={e => { e.stopPropagation(); onExpand(room.id) }}
            >
              <ArrowsOut size={14} />
            </button>
          </div>
        ))}
      </div>
    </div>
  )
}
