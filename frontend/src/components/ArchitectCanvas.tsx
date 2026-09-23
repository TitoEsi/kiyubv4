import { useEffect, useMemo, useRef, useState } from 'react'
import {
  ArrowClockwise,
  ArrowCounterClockwise,
  Cube,
  Door,
  FrameCorners,
  GridFour,
  NotePencil,
  Plus,
  Minus,
  Square,
  VectorTwo,
  Selection as SelectIcon,
  Ruler,
} from '@phosphor-icons/react'
import type { OpeningType, SceneDocument } from '../scene-graph/types'
import { mToFt, ftToM } from '../scene-graph/units'
import { commit, createHistory, redo, undo, type EditorHistory } from '../scene-graph/edit/history'
import { createWall, deleteWall, joinWalls, moveEndpoint, moveWall, setWallLength, setWallThickness, splitWall } from '../scene-graph/edit/wall-ops'
import { createOpening, deleteOpening, moveOpening, resizeOpening, rotateOpening, setOpeningType, syncOpeningsToWalls } from '../scene-graph/edit/opening-ops'
import { deleteFurniture, moveFurniture, rotateFurniture } from '../scene-graph/edit/furniture-ops'
import { deriveRoomsFromWalls } from '../scene-graph/edit/derive-rooms'
import { wallLength } from '../scene-graph/edit/geometry'
import ScenePlan2D, { EditorTool, Selection } from './ScenePlan2D'
import View3D from './View3D'
import { PlanAnnotation } from './planAnnotations'

type ViewKind = '2d' | '3d'

function afterGeom(scene: SceneDocument): SceneDocument {
  return deriveRoomsFromWalls(syncOpeningsToWalls(scene))
}

export default function ArchitectCanvas({
  scene,
  onSceneChange,
  onCommit,
  onSaveRevision,
  workingSaved,
  dirty,
  formalLabel,
  editingEnabled,
  comments = [],
  currentUserId,
  allowAnnotations = false,
  onAddAnnotation,
  onUpdateAnnotation,
  onDeleteAnnotation,
  onMoveAnnotation,
  selectedAnnotationId,
  onSelectAnnotation,
}: {
  scene: SceneDocument
  onSceneChange: (scene: SceneDocument) => void
  onCommit: (scene: SceneDocument) => void
  onSaveRevision: () => void
  workingSaved?: boolean
  dirty?: boolean
  formalLabel?: string
  editingEnabled: boolean
  comments?: PlanAnnotation[]
  currentUserId?: string
  allowAnnotations?: boolean
  onAddAnnotation?: (payload: { body: string; x: number; y: number; object_id: string | null }) => void
  onUpdateAnnotation?: (id: string, body: string) => void
  onDeleteAnnotation?: (id: string) => void
  onMoveAnnotation?: (id: string, x: number, y: number) => void
  selectedAnnotationId?: string | null
  onSelectAnnotation?: (id: string | null) => void
}) {
  const [history, setHistory] = useState<EditorHistory>(() => createHistory(scene))
  const [tool, setTool] = useState<EditorTool>('select')
  const [view, setView] = useState<ViewKind>('2d')
  const [snapEnabled, setSnapEnabled] = useState(true)
  const grid = 0.3
  const [selected, setSelected] = useState<Selection>(null)
  const [zoom, setZoom] = useState(1)
  const [pan, setPan] = useState({ x: 0, y: 0 })
  const [commentMode, setCommentMode] = useState(false)
  const [draft, setDraft] = useState<{ x: number; y: number; object_id: string | null; body: string } | null>(null)
  const [lengthDraft, setLengthDraft] = useState('')
  const skipSync = useRef(false)
  const presentRef = useRef(scene)
  presentRef.current = history.present

  useEffect(() => {
    if (skipSync.current) {
      skipSync.current = false
      return
    }
    setHistory(createHistory(scene))
  }, [scene.metadata.updatedAt, scene.walls.length, scene.openings.length, scene.furniture?.length])

  const live = history.present

  function apply(next: SceneDocument, record = true) {
    const geom = afterGeom(next)
    skipSync.current = true
    setHistory(h => record ? commit(h, geom) : { ...h, present: geom })
    onSceneChange(geom)
    if (record) onCommit(geom)
  }

  function liveMove(next: SceneDocument) {
    const geom = syncOpeningsToWalls(next)
    skipSync.current = true
    setHistory(h => ({ ...h, present: geom }))
    onSceneChange(geom)
  }

  const wall = selected?.kind === 'wall' ? live.walls.find(w => w.id === selected.id) : null
  const opening = selected?.kind === 'opening' ? live.openings.find(o => o.id === selected.id) : null
  const furn = selected?.kind === 'furniture' ? (live.furniture || []).find(f => f.id === selected.id) : null

  useEffect(() => {
    setLengthDraft(wall ? mToFt(wallLength(wall)).toFixed(2) : '')
  }, [wall?.id, wall?.start.x, wall?.end.x, wall?.start.y, wall?.end.y])

  const compatibleJoin = useMemo(() => {
    if (!wall) return null
    return live.walls.find(w => w.id !== wall.id && (
      (w.metadata?.startNodeId && w.metadata.startNodeId === wall.metadata?.endNodeId)
      || (w.metadata?.endNodeId && w.metadata.endNodeId === wall.metadata?.startNodeId)
      || (w.metadata?.startNodeId && w.metadata.startNodeId === wall.metadata?.startNodeId)
      || (w.metadata?.endNodeId && w.metadata.endNodeId === wall.metadata?.endNodeId)
    )) || null
  }, [wall, live.walls])

  return (
    <div className="architect-canvas">
      <div className="architect-toolbar" role="toolbar" aria-label="Architect tools">
        {editingEnabled && (
          <>
            {([
              ['select', SelectIcon, 'Select'],
              ['wall', VectorTwo, 'Wall'],
              ['door', Door, 'Door'],
              ['window', FrameCorners, 'Window'],
              ['measure', Ruler, 'Measure'],
            ] as const).map(([id, Icon, label]) => (
              <button key={id} type="button" className={tool === id ? 'active' : ''} aria-pressed={tool === id} aria-label={label} onClick={() => setTool(id)}>
                <Icon size={16} /> {label}
              </button>
            ))}
            <span className="architect-sep" />
            <button type="button" aria-label="Undo" disabled={!history.past.length} onClick={() => {
              const h = undo(history)
              setHistory(h)
              onSceneChange(h.present)
              onCommit(h.present)
            }}><ArrowCounterClockwise size={16} /></button>
            <button type="button" aria-label="Redo" disabled={!history.future.length} onClick={() => {
              const h = redo(history)
              setHistory(h)
              onSceneChange(h.present)
              onCommit(h.present)
            }}><ArrowClockwise size={16} /></button>
            <button type="button" className={snapEnabled ? 'active' : ''} aria-pressed={snapEnabled} onClick={() => setSnapEnabled(v => !v)}>
              <GridFour size={16} /> Snap
            </button>
          </>
        )}
        <span className="architect-sep" />
        <button type="button" className={view === '2d' ? 'active' : ''} onClick={() => setView('2d')}><Square size={16} /> 2D</button>
        <button type="button" className={view === '3d' ? 'active' : ''} onClick={() => setView('3d')}><Cube size={16} /> 3D</button>
        {allowAnnotations && view === '2d' && (
          <button type="button" className={commentMode ? 'active' : ''} aria-pressed={commentMode} onClick={() => { setCommentMode(v => !v); setDraft(null) }}>
            <NotePencil size={16} /> Note
          </button>
        )}
        <span className="architect-grow" />
        {editingEnabled && (
          <button type="button" className="catalog-generate-btn" onClick={onSaveRevision}>Save Revision</button>
        )}
        {editingEnabled && (
          <span className="wf-hint architect-save-state">
            {dirty ? 'Unsaved' : workingSaved ? 'Working copy saved' : formalLabel || ''}
          </span>
        )}
      </div>

      {wall && editingEnabled && (
        <div className="architect-context">
          <span>Wall · {mToFt(wallLength(wall)).toFixed(2)} ft</span>
          <label>
            Length
            <input value={lengthDraft} onChange={e => setLengthDraft(e.target.value)} onBlur={() => {
              const ft = parseFloat(lengthDraft)
              if (Number.isFinite(ft) && ft > 0.5) apply(setWallLength(live, wall.id, ftToM(ft)))
            }} />
          </label>
          <label>
            Thickness
            <input type="number" step="0.01" value={wall.thickness} onChange={e => apply(setWallThickness(live, wall.id, Number(e.target.value) || wall.thickness))} />
          </label>
          <button type="button" onClick={() => apply(splitWall(live, wall.id, 0.5))}>Split</button>
          {compatibleJoin && <button type="button" onClick={() => apply(joinWalls(live, wall.id, compatibleJoin.id))}>Join</button>}
          <button type="button" onClick={() => { apply(deleteWall(live, wall.id)); setSelected(null) }}>Delete</button>
        </div>
      )}
      {opening && editingEnabled && (
        <div className="architect-context">
          <span>{opening.type}</span>
          <label>
            Type
            <select value={opening.type} onChange={e => apply(setOpeningType(live, opening.id, e.target.value as OpeningType))}>
              <option value="door">Door</option>
              <option value="sliding_door">Sliding</option>
              <option value="window">Window</option>
              <option value="garage_door">Garage</option>
            </select>
          </label>
          <label>
            Width
            <input type="number" step="0.05" value={opening.width} onChange={e => apply(resizeOpening(live, opening.id, Number(e.target.value) || opening.width))} />
          </label>
          <button type="button" onClick={() => apply(rotateOpening(live, opening.id))}>Rotate</button>
          <button type="button" onClick={() => { apply(deleteOpening(live, opening.id)); setSelected(null) }}>Delete</button>
        </div>
      )}
      {furn && editingEnabled && (
        <div className="architect-context">
          <span>{furn.kind}</span>
          <button type="button" onClick={() => apply(rotateFurniture(live, furn.id, 90))}>Rotate</button>
          <button type="button" onClick={() => { apply(deleteFurniture(live, furn.id)); setSelected(null) }}>Delete</button>
        </div>
      )}

      <div className="architect-stage">
        {view === '2d' ? (
          <ScenePlan2D
            scene={live}
            tool={tool}
            snapEnabled={snapEnabled}
            grid={grid}
            editingEnabled={editingEnabled}
            selected={selected}
            onSelect={setSelected}
            zoom={zoom}
            pan={pan}
            onPanZoom={(z, p) => { setZoom(z); setPan(p) }}
            onDrawWall={(a, b) => apply(createWall(live, a, b))}
            onMoveWall={(id, dx, dy) => liveMove(moveWall(live, id, { x: dx, y: dy }))}
            onMoveEndpoint={(id, which, x, y) => liveMove(moveEndpoint(live, id, which, { x, y }))}
            onPlaceOpening={(wallId, t, kind) => apply(createOpening(live, wallId, kind, t))}
            onMoveOpening={(id, t) => liveMove(moveOpening(live, id, t))}
            onMoveFurniture={(id, x, y) => liveMove(moveFurniture(live, id, { x, y }))}
            onEditEnd={() => {
              const geom = afterGeom(presentRef.current)
              skipSync.current = true
              setHistory(h => ({ ...h, present: geom }))
              onSceneChange(geom)
              onCommit(geom)
            }}
            annotations={comments}
            annotationMode={commentMode}
            selectedAnnotationId={selectedAnnotationId}
            currentUserId={currentUserId}
            draft={draft}
            onPlaceAnnotation={(x, y, roomId) => setDraft({ x, y, object_id: roomId, body: draft?.body || '' })}
            onSelectAnnotation={onSelectAnnotation}
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
          <View3D scene={live} viewMode="dollhouse" />
        )}
        <div className="architect-zoom">
          <button type="button" aria-label="Zoom in" onClick={() => setZoom(z => Math.min(4, z * 1.15))}><Plus size={14} /></button>
          <button type="button" aria-label="Zoom out" onClick={() => setZoom(z => Math.max(0.4, z / 1.15))}><Minus size={14} /></button>
        </div>
      </div>
    </div>
  )
}
