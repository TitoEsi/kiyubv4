import { useFormat } from '../units/UnitsProvider'
import { MeasurementInput } from './MeasurementInput'
import RoomsPanel from './RoomsPanel'
import SidebarComments, { type SidebarCommentsProps } from './SidebarComments'
import type { RoomRow, SidebarSummary } from './room-rows'
import { ROOM_MAX_M, ROOM_MIN_M, type RoomAxis } from '../scene-graph/edit/room-ops'

/** Rooms list, selected-room details and summary, shared by the Client and Architect canvases. */
export default function CanvasRightSidebar({
  rooms,
  selectedId,
  onSelect,
  onExpand,
  expandLabel,
  summary,
  roomTitle,
  editable,
  onResize,
  onViewInterior,
  emptyHint,
  comments,
  id,
  'aria-label': ariaLabel,
}: {
  /** Comments section renders only when provided. */
  comments?: SidebarCommentsProps
  rooms: RoomRow[]
  selectedId: string | null
  onSelect: (id: string | null) => void
  onExpand: (id: string) => void
  expandLabel?: (name: string) => string
  summary: SidebarSummary
  roomTitle: string
  editable: boolean
  onResize?: (id: string, axis: RoomAxis, meters: number) => void
  /** The View Interior button renders only when this is provided. */
  onViewInterior?: (id: string) => void
  /** Shown in place of the room details when nothing is selected; omitted means render nothing. */
  emptyHint?: string
  id?: string
  'aria-label'?: string
}) {
  const fmt = useFormat()
  const room = rooms.find(r => r.id === selectedId)

  return (
    <div id={id} className="inspector" aria-label={ariaLabel}>
      <RoomsPanel
        rooms={rooms}
        selectedId={selectedId}
        onSelect={onSelect}
        onExpand={onExpand}
        expandLabel={expandLabel}
      />

      {room ? (
        <div className="inspector-section room-edit">
          <div className="inspector-title">{roomTitle}</div>
          <div className="inspector-name">{room.name}</div>
          <div className="inspector-field">
            <label htmlFor="room-width">Width ({fmt.unit})</label>
            <MeasurementInput
              key={`${room.id}:w:${room.width}`}
              id="room-width"
              min={ROOM_MIN_M}
              max={ROOM_MAX_M}
              value={room.width}
              disabled={!editable}
              showUnit={false}
              onCommit={v => onResize?.(room.id, 'width', v)}
            />
          </div>
          <div className="inspector-field">
            <label htmlFor="room-depth">Depth ({fmt.unit})</label>
            <MeasurementInput
              key={`${room.id}:d:${room.depth}`}
              id="room-depth"
              min={ROOM_MIN_M}
              max={ROOM_MAX_M}
              value={room.depth}
              disabled={!editable}
              showUnit={false}
              onCommit={v => onResize?.(room.id, 'depth', v)}
            />
          </div>
          <div className="inspector-area">{fmt.area(room.area)}</div>
          {onViewInterior && (
            <button type="button" className="view-interior-btn" onClick={() => onViewInterior(room.id)}>
              View Interior
            </button>
          )}
        </div>
      ) : emptyHint ? (
        <div className="inspector-section room-edit">
          <div className="inspector-title">{roomTitle}</div>
          <div className="inspector-area">{emptyHint}</div>
        </div>
      ) : null}

      <div className="inspector-section stats">
        <div className="inspector-title">Summary</div>
        <div className="stat-row"><span>Rooms</span><span>{summary.roomCount}</span></div>
        <div className="stat-row">
          <span>Living area</span>
          <span>{fmt.area(summary.livingAreaM2)}</span>
        </div>
        <div className="stat-row">
          <span>Building footprint</span>
          <span>{fmt.dims(summary.footprintW, summary.footprintD)}</span>
        </div>
        <div className="stat-row"><span>Ceiling Height</span><span>{fmt.length(summary.ceilingM)}</span></div>
      </div>

      {comments && <SidebarComments {...comments} />}
    </div>
  )
}
