import { useState, useRef, useEffect, useMemo, type ReactNode } from 'react'
import {
  ChatCircle,
  Cube,
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
import ExportPdfButton from './ExportPdfButton'
import ScenePlan2D from './ScenePlan2D'
import { loadLiveScene } from '../scene-graph/edit/load-scene'
import type { Comment } from '../workflow/api'
import { buildThreads } from '../workflow/commentThreads'
import type { CommentActions } from './CommentThread'
import type { SiteLot } from '../scene-graph/site/site-context'
import { useFormat } from '../units/UnitsProvider'
import CanvasRightSidebar from './CanvasRightSidebar'
import { DEFAULT_CEILING_M, sceneRoomRows, sceneSummary } from './room-rows'
import type { PublishedExport } from '../workflow/publishedExport'

interface Props {
  plan: FloorPlan
  onUpdate: (plan: FloorPlan) => void
  readOnly?: boolean
  projectId?: string
  revisionId?: string
  role?: string
  dirty?: boolean
  onSave?: () => void
  comments?: Comment[]
  commentActions?: CommentActions
  allowAnnotations?: boolean
  /** Show the Comments section in the sidebar (also when pinning is disabled). */
  showComments?: boolean
  onAddAnnotation?: (payload: { body: string; x: number; y: number; object_id: string | null }) => void
  selectedAnnotationId?: string | null
  onSelectAnnotation?: (id: string | null) => void
  existingScene?: SceneDocument | null
  lot?: SiteLot | null
  /** Replaces the default read-only banner text. */
  readOnlyBanner?: ReactNode
  /** Published scene to export. Null until the project is published. */
  publishedExport?: PublishedExport | null
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
  comments = [], commentActions, allowAnnotations = false, showComments = allowAnnotations,
  onAddAnnotation,
  selectedAnnotationId: selectedAnnotationIdProp,
  onSelectAnnotation: onSelectAnnotationProp,
  existingScene,
  lot,
  readOnlyBanner,
  publishedExport = null,
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
  const threads = useMemo(() => buildThreads(comments), [comments])
  const [draft, setDraft] = useState<{ x: number; y: number; object_id: string | null; body: string } | null>(null)
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

  const fmt = useFormat()
  const ceilH = plan.ceilingHeight || DEFAULT_CEILING_M
  const openInterior = (id: string) => setInteriorRoom(plan.rooms.find(r => r.id === id) ?? null)
  const viewOnlyCopy = readOnly && role === 'CLIENT'

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
          {readOnlyBanner ?? (viewOnlyCopy
            ? 'Viewing published or client copy — editing disabled'
            : 'View only — editing disabled')}
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
        <span className="editor-ceiling-tag">Ceiling Height {fmt.length(ceilH)}</span>
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

        <ExportPdfButton published={publishedExport} />
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
            </div>
            {viewMode === '2d' && (
              <div className="architect-zoom">
                <button type="button" aria-label="Zoom in" onClick={() => setZoom(z => Math.min(4, z * 1.15))}>+</button>
                <button type="button" aria-label="Zoom out" onClick={() => setZoom(z => Math.max(0.4, z / 1.15))}>−</button>
              </div>
            )}

            {viewMode === '2d' ? (
              <ScenePlan2D
                scene={liveScene}
                lot={lot}
                insets={{ top: 56 }}
                tool="select"
                snapEnabled={false}
                grid={0.3}
                editingEnabled={false}
                selected={selectedId ? { kind: 'room', id: selectedId } : null}
                onSelect={sel => setSelectedId(sel?.kind === 'room' ? sel.id : sel ? sel.id : null)}
                zoom={zoom}
                pan={pan}
                onPanZoom={(z, p) => { setZoom(z); setPan(p) }}
                annotations={showComments ? threads : []}
                annotationMode={commentMode}
                selectedAnnotationId={selectedAnnotationId}
                commentActions={commentActions}
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
              />
            ) : (
              <View3D scene={liveScene} viewMode={viewMode} />
            )}
          </div>

          <CanvasRightSidebar
            rooms={sceneRoomRows(liveScene)}
            selectedId={selectedId}
            onSelect={setSelectedId}
            onExpand={openInterior}
            summary={sceneSummary(liveScene)}
            roomTitle={readOnly ? 'Room' : 'Edit Room'}
            editable={!readOnly}
            onResize={(id, axis, v) => updateRoomDim(id, axis === 'width' ? 'width' : 'height', v)}
            onViewInterior={openInterior}
            comments={showComments ? {
              threads,
              actions: commentActions,
              selectedId: selectedAnnotationId,
              onSelect: selectAnnotation,
            } : undefined}
          />
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
