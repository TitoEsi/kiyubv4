import { useState, useRef, useEffect, useMemo } from 'react'
import {
  ArrowsOut,
  ChatCircle,
  Cube,
  DownloadSimple,
  House,
  NotePencil,
  SquaresFour,
  Stack,
  Path,
} from '@phosphor-icons/react'
import { FloorPlan, Room } from '../types/floorplan'
import type { SceneDocument } from '../scene-graph/types'
import View3D from './View3D'
import RoomInteriorView from './RoomInteriorView'
import DesignScore from './DesignScore'
import ChatPanel from './ChatPanel'
import { exportPdf } from '../api/client'
import ScenePlan2D from './ScenePlan2D'
import { loadLiveScene } from '../scene-graph/edit/load-scene'
import { PlanAnnotation } from './planAnnotations'
import { MeasurementInput } from './MeasurementInput'
import { useFormat } from '../units/UnitsProvider'

const DEFAULT_CEILING_M = 2.7432
const ROOM_MIN_M = 1.8288
const ROOM_MAX_M = 18.288

interface Props {
  plan: FloorPlan
  onUpdate: (plan: FloorPlan) => void
  readOnly?: boolean
  projectId?: string
  revisionId?: string
  role?: string
  dirty?: boolean
  onSave?: () => void
  comments?: PlanAnnotation[]
  currentUserId?: string
  allowAnnotations?: boolean
  onAddAnnotation?: (payload: { body: string; x: number; y: number; object_id: string | null }) => void
  onUpdateAnnotation?: (id: string, body: string) => void
  onDeleteAnnotation?: (id: string) => void
  onMoveAnnotation?: (id: string, x: number, y: number) => void
  selectedAnnotationId?: string | null
  onSelectAnnotation?: (id: string | null) => void
  existingScene?: SceneDocument | null
}

type MainTab = 'plan' | 'score' | 'chat'
export type ViewMode = '2d' | 'exterior' | 'dollhouse' | 'walkthrough' | 'topview'

const TAB_LABELS: { id: MainTab; label: string }[] = [
  { id: 'plan', label: '2D / 3D Plan' },
  { id: 'score', label: 'Design Score' },
  { id: 'chat', label: 'AI Chat' },
]

const VIEW_BUTTONS: { id: ViewMode; label: string; Icon: typeof SquaresFour }[] = [
  { id: '2d', label: '2D Plan', Icon: SquaresFour },
  { id: 'exterior', label: 'Exterior', Icon: House },
  { id: 'dollhouse', label: 'Dollhouse', Icon: Cube },
  { id: 'walkthrough', label: 'Walk', Icon: Path },
  { id: 'topview', label: 'Top View', Icon: Stack },
]

export default function FloorPlanEditor({
  plan, onUpdate, readOnly = false, projectId, revisionId, role, dirty, onSave,
  comments = [], currentUserId, allowAnnotations = false,
  onAddAnnotation, onUpdateAnnotation, onDeleteAnnotation, onMoveAnnotation,
  selectedAnnotationId: selectedAnnotationIdProp,
  onSelectAnnotation: onSelectAnnotationProp,
  existingScene,
}: Props) {
  const [tab, setTab] = useState<MainTab>('plan')
  const [viewMode, setViewMode] = useState<ViewMode>('2d')
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [interiorRoom, setInteriorRoom] = useState<Room | null>(null)
  const [narrow, setNarrow] = useState(false)
  const [moreOpen, setMoreOpen] = useState(false)
  const [commentMode, setCommentMode] = useState(false)
  const [internalAnnotationId, setInternalAnnotationId] = useState<string | null>(null)
  const [zoom, setZoom] = useState(1)
  const [pan, setPan] = useState({ x: 0, y: 0 })
  const liveScene = useMemo(
    () => loadLiveScene(plan, undefined, { projectId, existing: existingScene }),
    [plan, projectId, existingScene],
  )
  const selectedAnnotationId = selectedAnnotationIdProp ?? internalAnnotationId
  const [draft, setDraft] = useState<{ x: number; y: number; object_id: string | null; body: string } | null>(null)
  const [exportError, setExportError] = useState<string | null>(null)
  const containerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const mq = window.matchMedia('(max-width: 1200px)')
    const sync = () => setNarrow(mq.matches)
    sync()
    mq.addEventListener('change', sync)
    return () => mq.removeEventListener('change', sync)
  }, [])

  function updateRoomDim(roomId: string, field: 'width' | 'height', val: number) {
    if (readOnly) return
    onUpdate({ ...plan, rooms: plan.rooms.map(r => (r.id === roomId ? { ...r, [field]: val } : r)) })
  }

  function selectAnnotation(id: string | null) {
    setInternalAnnotationId(id)
    onSelectAnnotationProp?.(id)
    const note = comments.find(c => c.id === id)
    if (note?.object_id) setSelectedId(note.object_id)
  }

  useEffect(() => {
    if (!selectedAnnotationIdProp) return
    const note = comments.find(c => c.id === selectedAnnotationIdProp)
    if (note?.object_id) setSelectedId(note.object_id)
  }, [selectedAnnotationIdProp, comments])

  const tabs = TAB_LABELS.filter(t => !(readOnly && t.id === 'chat'))
  const primary = tabs.filter(t => !narrow || t.id === 'plan')
  const extra = tabs.filter(t => narrow && t.id !== 'plan')

  const selectedRoom = plan.rooms.find(r => r.id === selectedId)
  const fmt = useFormat()
  const ceilH = plan.ceilingHeight || DEFAULT_CEILING_M
  const livingAreaM2 = plan.rooms
    .filter(r => !['garage', 'patio', 'deck', 'rear_patio', 'outdoor_living', 'front_porch'].includes(r.type))
    .reduce((s, r) => s + r.width * r.height, 0)
  const viewOnlyCopy = readOnly && (role === 'CLIENT' || role === 'MAIN_ADMIN' || role === 'IT_PERSONNEL')

  return (
    <div className="editor">
      {interiorRoom && (
        <RoomInteriorView
          room={interiorRoom}
          ceilingHeight={ceilH}
          onClose={() => setInteriorRoom(null)}
        />
      )}

      {readOnly && (
        <div className="editor-readonly-banner" role="status">
          {viewOnlyCopy
            ? 'Viewing published or client copy — editing disabled'
            : 'View only — editing disabled'}
        </div>
      )}
      {!readOnly && dirty && onSave && (
        <div className="editor-unsaved">
          Unsaved design
          <button type="button" className="catalog-generate-btn" onClick={onSave}>Save revision</button>
        </div>
      )}

      <div className="editor-toolbar">
        <span className="editor-title">{plan.name}</span>
        <span className="editor-ceiling-tag">{fmt.length(ceilH)} ceilings</span>
        {role && <span className="editor-ceiling-tag">{role}</span>}
        {projectId && revisionId && (
          <span className="editor-ceiling-tag" title={`${projectId} / ${revisionId}`}>Rev</span>
        )}

        <div className="editor-tabs" role="tablist" aria-label="Design views">
          {primary.map(t => (
            <button
              type="button"
              key={t.id}
              role="tab"
              aria-selected={tab === t.id}
              className={`editor-tab ${tab === t.id ? 'active' : ''}`}
              onClick={() => setTab(t.id)}
            >
              {t.id === 'chat' ? <><ChatCircle size={14} aria-hidden /> {t.label}</> : t.label}
            </button>
          ))}
          {extra.length > 0 && (
            <div className="editor-more">
              <button type="button" className="editor-tab" aria-expanded={moreOpen} onClick={() => setMoreOpen(o => !o)}>
                More
              </button>
              {moreOpen && (
                <div className="editor-more-menu" role="menu">
                  {extra.map(t => (
                    <button
                      type="button"
                      key={t.id}
                      role="menuitem"
                      onClick={() => { setTab(t.id); setMoreOpen(false) }}
                    >
                      {t.label}
                    </button>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>

        <button
          type="button"
          className="export-btn"
          onClick={async () => {
            try {
              setExportError(null)
              await exportPdf(plan, fmt.unit)
            } catch {
              setExportError('Could not export PDF.')
            }
          }}
        >
          <DownloadSimple size={16} aria-hidden /> Export PDF
        </button>
        {exportError && <span className="error-msg editor-export-error" role="alert">{exportError}</span>}
        {allowAnnotations && viewMode === '2d' && tab === 'plan' && (
          <button
            type="button"
            className={`export-btn ${commentMode ? 'active' : ''}`}
            aria-pressed={commentMode}
            onClick={() => { setCommentMode(v => !v); setDraft(null) }}
          >
            <NotePencil size={16} aria-hidden /> Note
          </button>
        )}
      </div>

      {tab === 'plan' && (
        <div className="editor-body">
          <div className="editor-canvas" ref={containerRef}>
            <div className="plan-sub-controls">
              <div className="view-toggle view-toggle-expanded" role="group" aria-label="View mode">
                {VIEW_BUTTONS.map(btn => (
                  <button
                    type="button"
                    key={btn.id}
                    className={viewMode === btn.id ? 'active' : ''}
                    aria-pressed={viewMode === btn.id}
                    aria-label={btn.label}
                    onClick={() => setViewMode(btn.id)}
                  >
                    <span className="view-btn-icon"><btn.Icon size={16} /></span>
                    <span className="view-btn-label">{btn.label}</span>
                  </button>
                ))}
              </div>
              {viewMode === '2d' && (
                <div className="architect-zoom">
                  <button type="button" aria-label="Zoom in" onClick={() => setZoom(z => Math.min(4, z * 1.15))}>+</button>
                  <button type="button" aria-label="Zoom out" onClick={() => setZoom(z => Math.max(0.4, z / 1.15))}>−</button>
                </div>
              )}
            </div>

            {viewMode === '2d' ? (
              <ScenePlan2D
                scene={liveScene}
                tool="select"
                snapEnabled={false}
                grid={0.3}
                editingEnabled={false}
                selected={selectedId ? { kind: 'room', id: selectedId } : null}
                onSelect={sel => setSelectedId(sel?.kind === 'room' ? sel.id : sel ? sel.id : null)}
                zoom={zoom}
                pan={pan}
                onPanZoom={(z, p) => { setZoom(z); setPan(p) }}
                annotations={comments}
                annotationMode={commentMode}
                selectedAnnotationId={selectedAnnotationId}
                currentUserId={currentUserId}
                draft={draft}
                onPlaceAnnotation={(x, y, roomId) => setDraft({ x, y, object_id: roomId, body: draft?.body || '' })}
                onSelectAnnotation={selectAnnotation}
                onDraftChange={body => setDraft(d => d ? { ...d, body } : d)}
                onDraftSubmit={() => {
                  if (!draft?.body.trim()) return
                  onAddAnnotation?.({ body: draft.body.trim(), x: draft.x, y: draft.y, object_id: draft.object_id })
                  setDraft(null)
                  setCommentMode(false)
                }}
                onDraftCancel={() => setDraft(null)}
                onUpdateAnnotation={onUpdateAnnotation}
                onDeleteAnnotation={onDeleteAnnotation}
                onMoveAnnotation={onMoveAnnotation}
              />
            ) : (
              <View3D scene={liveScene} viewMode={viewMode} />
            )}
          </div>

          <div className="inspector">
            <div className="inspector-section">
              <div className="inspector-title">Rooms</div>
              <div className="room-list">
                {plan.rooms.map(room => (
                  <div
                    key={room.id}
                    className={`room-item ${room.id === selectedId ? 'selected' : ''}`}
                    role="button"
                    tabIndex={0}
                    onClick={() => setSelectedId(room.id === selectedId ? null : room.id)}
                    onKeyDown={e => {
                      if (e.key === 'Enter' || e.key === ' ') {
                        e.preventDefault()
                        setSelectedId(room.id === selectedId ? null : room.id)
                      }
                    }}
                  >
                    <div className="room-swatch" style={{ background: room.color }} />
                    <div style={{ flex: 1 }}>
                      <div className="room-item-name">{room.name}</div>
                      <div className="room-item-size">
                        {fmt.dims(room.width, room.height)} · {fmt.area(room.width * room.height)}
                      </div>
                    </div>
                    <button
                      type="button"
                      className="room-interior-btn"
                      aria-label={`View interior of ${room.name}`}
                      onClick={e => { e.stopPropagation(); setInteriorRoom(room) }}
                    >
                      <ArrowsOut size={14} />
                    </button>
                  </div>
                ))}
              </div>
            </div>

            {selectedRoom && (
              <div className="inspector-section room-edit">
                <div className="inspector-title">{readOnly ? 'Room' : 'Edit Room'}</div>
                <div className="inspector-name">{selectedRoom.name}</div>
                <div className="inspector-field">
                  <label htmlFor="room-width">Width ({fmt.unit})</label>
                  <MeasurementInput
                    id="room-width"
                    min={ROOM_MIN_M}
                    max={ROOM_MAX_M}
                    value={selectedRoom.width}
                    disabled={readOnly}
                    showUnit={false}
                    onCommit={v => updateRoomDim(selectedRoom.id, 'width', v)}
                  />
                </div>
                <div className="inspector-field">
                  <label htmlFor="room-depth">Depth ({fmt.unit})</label>
                  <MeasurementInput
                    id="room-depth"
                    min={ROOM_MIN_M}
                    max={ROOM_MAX_M}
                    value={selectedRoom.height}
                    disabled={readOnly}
                    showUnit={false}
                    onCommit={v => updateRoomDim(selectedRoom.id, 'height', v)}
                  />
                </div>
                <div className="inspector-area">{fmt.area(selectedRoom.width * selectedRoom.height)}</div>
                <button type="button" className="view-interior-btn" onClick={() => setInteriorRoom(selectedRoom)}>
                  View Interior
                </button>
              </div>
            )}

            <div className="inspector-section stats">
              <div className="inspector-title">Summary</div>
              <div className="stat-row"><span>Rooms</span><span>{plan.rooms.length}</span></div>
              <div className="stat-row">
                <span>Living area</span>
                <span>{fmt.area(livingAreaM2)}</span>
              </div>
              <div className="stat-row">
                <span>Footprint</span>
                <span>{fmt.dims(plan.totalWidth, plan.totalHeight)}</span>
              </div>
              <div className="stat-row"><span>Ceiling</span><span>{fmt.length(ceilH)}</span></div>
            </div>
          </div>
        </div>
      )}

      {tab === 'score' && (
        <div className="tab-content-scroll" role="tabpanel">
          <DesignScore plan={plan} />
        </div>
      )}

      {tab === 'chat' && !readOnly && (
        <div className="tab-content-chat" role="tabpanel">
          <ChatPanel plan={plan} onPlanUpdate={onUpdate} />
        </div>
      )}
    </div>
  )
}
