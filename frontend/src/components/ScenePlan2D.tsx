import { useEffect, useId, useMemo, useRef, useState } from 'react'
import type { CSSProperties } from 'react'
import type { Opening, SceneDocument, Wall } from '../scene-graph/types'
import { nodeIdOf, wallPointAtT, projectT } from '../scene-graph/edit/geometry'
import { snapPoint, snapToleranceFor, type SnapResult } from '../scene-graph/edit/snap'
import { Note, X } from '@phosphor-icons/react'
import { commentRoleLabel, isStickyVisible, PlanAnnotation } from './planAnnotations'
import { displayNameFromEmail } from '../workflow/displayName'
import CommentThread, { type CommentActions } from './CommentThread'
import { OpeningSymbol, furnitureContains, openingContains, wallStrokeSegments } from './opening-symbols'
import { FurnitureSymbol, furnitureBackSide } from './furniture-symbols'
import { canStartEmptyPan, clampPan, fitRoomView, screenToPlan } from './plan-viewport'
import { buildSiteContext, type SiteLot } from '../scene-graph/site/site-context'
import { LotDimensions, LotLayer, SheetDimensions, SiteDefs, VegetationSymbol, WallLengthDimension } from './site-symbols'
import { roomFill } from '../scene-graph/room-colors'
import { layoutRoomLabel, roomLabelText, sheetRoomLabel, type LabelRect } from '../scene-graph/room-labels'
import { DOCUMENT_MARGIN, fitDrawingFrame } from './plan-fit'
import { sceneRoomRows } from './room-rows'
import NorthIndicator, { NorthMark } from './NorthIndicator'

export type EditorTool = 'select' | 'wall' | 'door' | 'window' | 'measure'
export type Selection =
  | { kind: 'wall'; id: string }
  | { kind: 'opening'; id: string }
  | { kind: 'room'; id: string }
  | { kind: 'furniture'; id: string }
  | null

const BG = '#faf9f5'
const MARGIN = 48
const PAN_THRESHOLD_PX = 4

function sceneBounds(scene: SceneDocument) {
  let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity
  for (const wall of scene.walls) {
    minX = Math.min(minX, wall.start.x, wall.end.x)
    minY = Math.min(minY, wall.start.y, wall.end.y)
    maxX = Math.max(maxX, wall.start.x, wall.end.x)
    maxY = Math.max(maxY, wall.start.y, wall.end.y)
  }
  for (const room of scene.rooms) {
    minX = Math.min(minX, room.position.x)
    minY = Math.min(minY, room.position.y)
    maxX = Math.max(maxX, room.position.x + room.dimensions.width)
    maxY = Math.max(maxY, room.position.y + room.dimensions.height)
  }
  if (!Number.isFinite(minX)) {
    minX = 0; minY = 0
    maxX = scene.site.width
    maxY = scene.site.depth
  }
  return { minX, minY, maxX, maxY, w: Math.max(maxX - minX, 1), h: Math.max(maxY - minY, 1) }
}

function withLot(b: ReturnType<typeof sceneBounds>, lot: { x: number; y: number; width: number; height: number } | null) {
  if (!lot) return b
  const minX = Math.min(b.minX, lot.x), minY = Math.min(b.minY, lot.y)
  const maxX = Math.max(b.maxX, lot.x + lot.width), maxY = Math.max(b.maxY, lot.y + lot.height)
  return { minX, minY, maxX, maxY, w: Math.max(maxX - minX, 1), h: Math.max(maxY - minY, 1) }
}

function poly(room: SceneDocument['rooms'][number]) {
  if (room.polygon?.length) return room.polygon
  const { x, y } = room.position
  const { width, height } = room.dimensions
  return [
    { x, y }, { x: x + width, y }, { x: x + width, y: y + height }, { x, y: y + height },
  ]
}

const MIN_WALL_PX = 2

export function wallStrokePx(wall: Wall, S: number): number {
  return Math.max((wall.thickness || 0.15) * S, MIN_WALL_PX)
}

/**
 * Points where two or more walls meet. Butt-capped thick strokes leave a notch there, so each gets a
 * filled cap of the thickest wall's size: a square when every wall is axis-aligned, else a disc.
 */
export function wallJunctions(walls: Wall[]): Array<{ key: string; p: { x: number; y: number }; thickness: number; square: boolean }> {
  const byNode = new Map<string, { p: { x: number; y: number }; walls: Wall[] }>()
  for (const wall of walls) {
    for (const which of ['start', 'end'] as const) {
      const p = wall[which]
      const key = nodeIdOf(wall, which) ?? `${p.x.toFixed(4)},${p.y.toFixed(4)}`
      const entry = byNode.get(key) ?? { p, walls: [] }
      entry.walls.push(wall)
      byNode.set(key, entry)
    }
  }
  const axis = (w: Wall) => Math.abs(w.start.x - w.end.x) < 1e-6 || Math.abs(w.start.y - w.end.y) < 1e-6
  return [...byNode.entries()]
    .filter(([, e]) => e.walls.length >= 2)
    .map(([key, e]) => ({
      key,
      p: e.p,
      thickness: Math.max(...e.walls.map(w => w.thickness || 0.15)),
      square: e.walls.every(axis),
    }))
}

export default function ScenePlan2D({
  scene,
  tool,
  snapEnabled,
  grid,
  editingEnabled,
  selected,
  onSelect,
  onDrawWall,
  onMoveWall,
  onMoveEndpoint,
  onPlaceOpening,
  onMoveOpening,
  onMoveFurniture,
  onEditEnd,
  zoom,
  pan,
  onPanZoom,
  annotations = [],
  annotationMode = false,
  selectedAnnotationId,
  draft,
  onPlaceAnnotation,
  onSelectAnnotation,
  onDraftChange,
  onDraftSubmit,
  onDraftCancel,
  commentActions,
  guides = [],
  lot,
  insets,
  focusRequest,
  trueWallThickness = false,
  frame,
}: {
  scene: SceneDocument
  /** Draw walls at their real thickness around the centerline instead of a fixed hairline stroke. */
  trueWallThickness?: boolean
  /** Fixed page frame. Fits the whole plan, draws stored wall thickness, and omits editor UI. */
  frame?: { width: number; height: number }
  /** Zoom/pan to a room; a new `nonce` re-triggers the focus. */
  focusRequest?: { roomId: string; nonce: number } | null
  /** Screen pixels reserved for viewport overlays (toolbars, zoom controls); the fit avoids them. */
  insets?: { top?: number; right?: number; bottom?: number; left?: number }
  /** Project lot from the brief (meters); site context is inferred from the footprint when absent. */
  lot?: SiteLot | null
  tool: EditorTool
  snapEnabled: boolean
  grid: number
  editingEnabled: boolean
  selected: Selection
  onSelect: (sel: Selection) => void
  onDrawWall?: (a: { x: number; y: number }, b: { x: number; y: number }) => void
  onMoveWall?: (id: string, dx: number, dy: number) => void
  onMoveEndpoint?: (id: string, which: 'start' | 'end', x: number, y: number) => void
  onPlaceOpening?: (wallId: string, t: number, kind: 'door' | 'window') => void
  onMoveOpening?: (id: string, t: number) => void
  onMoveFurniture?: (id: string, x: number, y: number) => void
  onEditEnd?: () => void
  zoom: number
  pan: { x: number; y: number }
  onPanZoom?: (zoom: number, pan: { x: number; y: number }) => void
  annotations?: PlanAnnotation[]
  annotationMode?: boolean
  selectedAnnotationId?: string | null
  draft?: { x: number; y: number; object_id: string | null; body: string } | null
  /** Pin position in plan meters. */
  onPlaceAnnotation?: (xM: number, yM: number, roomId: string | null) => void
  onSelectAnnotation?: (id: string | null) => void
  onDraftChange?: (body: string) => void
  onDraftSubmit?: () => void
  onDraftCancel?: () => void
  /** Reply / edit / resolve handlers for the sticky-note popup. */
  commentActions?: CommentActions
  guides?: Array<{ x1: number; y1: number; x2: number; y2: number }>
}) {
  const svgRef = useRef<SVGSVGElement>(null)
  const altRef = useRef(false)
  const [spaceHeld, setSpaceHeld] = useState(false)
  const [panning, setPanning] = useState(false)
  const [liveGuides, setLiveGuides] = useState<Array<{ x1: number; y1: number; x2: number; y2: number }>>([])
  const [cw, setCw] = useState(800)
  const [ch, setCh] = useState(600)
  const wrapRef = useRef<HTMLDivElement>(null)
  const zoomRef = useRef(zoom)
  const panRef = useRef(pan)
  const onPanZoomRef = useRef(onPanZoom)
  zoomRef.current = zoom
  panRef.current = pan
  onPanZoomRef.current = onPanZoom
  const [drawStart, setDrawStart] = useState<{ x: number; y: number } | null>(null)
  const [cursor, setCursor] = useState<{ x: number; y: number } | null>(null)
  const [snapKind, setSnapKind] = useState<SnapResult['kind']>('none')
  /** Latest snap, read on pointer-up so the committed wall ends exactly where the preview ended. */
  const snapRef = useRef<SnapResult | null>(null)

  useEffect(() => {
    const el = wrapRef.current
    if (!el) return
    const obs = new ResizeObserver(() => {
      setCw(el.clientWidth)
      setCh(el.clientHeight)
    })
    obs.observe(el)
    return () => obs.disconnect()
  }, [])

  useEffect(() => {
    const down = (e: KeyboardEvent) => {
      if (e.code !== 'Space') return
      const t = e.target as HTMLElement | null
      if (t && (t.tagName === 'INPUT' || t.tagName === 'TEXTAREA')) return
      e.preventDefault()
      setSpaceHeld(true)
    }
    const up = (e: KeyboardEvent) => {
      if (e.code === 'Space') setSpaceHeld(false)
      if (e.key === 'Alt') altRef.current = false
    }
    window.addEventListener('keydown', down)
    window.addEventListener('keyup', up)
    return () => {
      window.removeEventListener('keydown', down)
      window.removeEventListener('keyup', up)
    }
  }, [])

  useEffect(() => {
    const el = wrapRef.current
    if (!el) return
    const onWheel = (e: WheelEvent) => {
      if (!onPanZoomRef.current) return
      if (e.target instanceof Element && e.target.closest('.plan-note-popup')) return
      e.preventDefault()
      const factor = e.deltaY > 0 ? 0.92 : 1.08
      onPanZoomRef.current(Math.min(4, Math.max(0.4, zoomRef.current * factor)), panRef.current)
    }
    el.addEventListener('wheel', onWheel, { passive: false })
    return () => el.removeEventListener('wheel', onWheel)
  }, [])

  const site = useMemo(
    () => buildSiteContext(scene, lot),
    [scene.rooms, scene.walls, scene.openings, lot?.width, lot?.depth, lot?.shape],
  )
  const grassId = `grass-${useId().replace(/:/g, '')}`

  const documentMode = frame != null
  const building = sceneBounds(scene)
  const bounds = withLot(building, site.lot)
  const inset = { top: insets?.top ?? 0, right: insets?.right ?? 0, bottom: insets?.bottom ?? 0, left: insets?.left ?? 0 }
  const viewW = frame?.width ?? cw
  const viewH = frame?.height ?? ch
  const baseS = Math.max(
    0.01,
    Math.min((viewW - MARGIN * 2 - inset.left - inset.right) / bounds.w, (viewH - MARGIN * 2 - inset.top - inset.bottom) / bounds.h),
  )
  const fitted = frame ? fitDrawingFrame(bounds, frame, DOCUMENT_MARGIN) : null
  const S = fitted ? fitted.S : baseS * zoom
  const clampView = (p: { x: number; y: number }) => clampPan({ pan: p, S, bounds, cw: viewW, ch: viewH, inset, margin: MARGIN })
  const view = fitted ? { x: 0, y: 0 } : clampView(pan)
  const ox = fitted ? fitted.ox : MARGIN + inset.left + view.x - bounds.minX * S
  const oy = fitted ? fitted.oy : MARGIN + inset.top + view.y - bounds.minY * S
  const panAvailable = !documentMode && !!onPanZoom && canStartEmptyPan({ zoom, tool, annotationMode, button: 0 })
  const drawThickness = documentMode || trueWallThickness
  const selection = documentMode ? null : selected

  const handledFocusNonce = useRef(focusRequest?.nonce)
  useEffect(() => {
    if (!focusRequest || focusRequest.nonce === handledFocusNonce.current || !onPanZoomRef.current) return
    handledFocusNonce.current = focusRequest.nonce
    const room = scene.rooms.find(r => r.id === focusRequest.roomId)
    if (!room) return
    const pts = poly(room)
    const rect = {
      minX: Math.min(...pts.map(p => p.x)),
      minY: Math.min(...pts.map(p => p.y)),
      maxX: Math.max(...pts.map(p => p.x)),
      maxY: Math.max(...pts.map(p => p.y)),
    }
    const next = fitRoomView({ rect, bounds, baseS, cw, ch, inset, margin: MARGIN })
    onPanZoomRef.current(next.zoom, next.pan)
    // Only a new request should move the camera; later scene edits must not.
  }, [focusRequest?.nonce])

  const backSides = useMemo(
    () => new Map((scene.furniture || []).map(item => [item.id, furnitureBackSide(item, scene.walls)])),
    [scene.furniture, scene.walls],
  )
  const roomLabels = useMemo(() => {
    if (documentMode) {
      const rows = sceneRoomRows(scene)
      return scene.rooms.map((room, i) => ({
        room,
        layout: sheetRoomLabel(room, rows[i]?.name || room.name, S, ox, oy),
      }))
    }
    const byRoom = new Map<string, LabelRect[]>()
    for (const f of scene.furniture || []) {
      const rects = byRoom.get(f.roomId) ?? []
      rects.push({ x: f.position.x, y: f.position.y, width: f.dimensions.width, height: f.dimensions.height })
      byRoom.set(f.roomId, rects)
    }
    return scene.rooms.map(room => ({ room, layout: layoutRoomLabel(room, S, ox, oy, byRoom.get(room.id)) }))
  }, [documentMode, scene, scene.rooms, scene.furniture, S, ox, oy])
  const junctions = useMemo(() => (drawThickness ? wallJunctions(scene.walls) : []), [drawThickness, scene.walls])
  const selectedWall = selection?.kind === 'wall' ? scene.walls.find(w => w.id === selection.id) ?? null : null

  const toScene = (clientX: number, clientY: number) => {
    const svg = svgRef.current
    if (!svg) return { x: 0, y: 0 }
    const ctm = svg.getScreenCTM()
    if (!ctm) return { x: 0, y: 0 }
    const p = svg.createSVGPoint()
    p.x = clientX
    p.y = clientY
    return screenToPlan(p.matrixTransform(ctm.inverse()), ox, oy, S)
  }

  const snapped = (p: { x: number; y: number }, ev?: { altKey?: boolean }, excludeWallIds?: string[]) => {
    if (ev?.altKey != null) altRef.current = ev.altKey
    const result = snapPoint(p, {
      grid,
      enabled: snapEnabled && !altRef.current && (editingEnabled || false),
      walls: scene.walls,
      tolerance: snapToleranceFor(S),
      excludeWallIds,
    })
    snapRef.current = result
    setSnapKind(result.kind)
    setLiveGuides(result.guides)
    return result.point
  }

  function roomAt(x: number, y: number): string | null {
    for (const room of scene.rooms) {
      const pts = poly(room)
      let inside = false
      for (let i = 0, j = pts.length - 1; i < pts.length; j = i++) {
        const xi = pts[i].x, yi = pts[i].y, xj = pts[j].x, yj = pts[j].y
        if ((yi > y) !== (yj > y) && x < ((xj - xi) * (y - yi)) / (yj - yi + 1e-12) + xi) inside = !inside
      }
      if (inside) return room.id
    }
    return null
  }

  function objectAt(p: { x: number; y: number }): Selection {
    const opening = scene.openings.find(o => {
      const host = scene.walls.find(w => w.id === o.wallId)
      return host ? openingContains(o, host, p) : false
    })
    if (opening) return { kind: 'opening', id: opening.id }
    const furn = (scene.furniture || []).find(f => furnitureContains(f, p))
    if (furn) return { kind: 'furniture', id: furn.id }
    const wall = nearestWall(p)
    return wall ? { kind: 'wall', id: wall.id } : null
  }

  function roomSelection(p: { x: number; y: number }): Selection {
    const rid = roomAt(p.x, p.y)
    return rid ? { kind: 'room', id: rid } : null
  }

  /** Viewport pan from a pointer-down; with `threshold`, a release without movement counts as a click. */
  function beginPan(clientX: number, clientY: number, threshold: boolean, onClick?: () => void) {
    const start = { ...view }
    const clamp = clampView
    let moved = !threshold
    if (moved) setPanning(true)
    const move = (ev: PointerEvent) => {
      const dx = ev.clientX - clientX, dy = ev.clientY - clientY
      if (!moved) {
        if (Math.hypot(dx, dy) < PAN_THRESHOLD_PX) return
        moved = true
        setPanning(true)
      }
      onPanZoomRef.current?.(zoomRef.current, clamp({ x: start.x + dx, y: start.y + dy }))
    }
    const end = (click: boolean) => {
      window.removeEventListener('pointermove', move)
      window.removeEventListener('pointerup', up)
      window.removeEventListener('pointercancel', cancel)
      window.removeEventListener('blur', cancel)
      setPanning(false)
      if (click && !moved) onClick?.()
    }
    const up = () => end(true)
    const cancel = () => end(false)
    window.addEventListener('pointermove', move)
    window.addEventListener('pointerup', up)
    window.addEventListener('pointercancel', cancel)
    window.addEventListener('blur', cancel)
  }

  function nearestWall(p: { x: number; y: number }): Wall | null {
    let best: Wall | null = null
    let bestD = 0.35
    for (const wall of scene.walls) {
      const t = projectT(wall, p)
      const q = wallPointAtT(wall, t)
      const d = Math.hypot(q.x - p.x, q.y - p.y)
      if (d < bestD) {
        bestD = d
        best = wall
      }
    }
    return best
  }

  const renderRoomLabels = () => (
    <g data-layer="labels" pointerEvents="none">
      {roomLabels.map(({ room, layout }) => {
        if (!layout) return null
        const top = layout.y - ((layout.lines.length - 1) * layout.lineHeight) / 2
        return (
          <text
            key={room.id}
            className="plan-room-label"
            x={layout.x}
            y={top}
            dy="0.35em"
            textAnchor="middle"
            fontSize={layout.fontSize}
            fontFamily={documentMode ? 'Helvetica' : undefined}
            fontWeight={documentMode ? 'bold' : 500}
            letterSpacing="0.06em"
            fill={documentMode ? '#17191c' : '#2a2d31'}
            stroke={documentMode ? 'none' : roomFill(room.type)}
            strokeWidth={documentMode ? undefined : 3}
            strokeLinejoin={documentMode ? undefined : 'round'}
            paintOrder={documentMode ? undefined : 'stroke'}
          >
            {layout.lines.map((line, i) => (
              <tspan key={i} x={layout.x} dy={i === 0 ? undefined : layout.lineHeight}>{line}</tspan>
            ))}
          </text>
        )
      })}
    </g>
  )

  return (
    <div
      className="scene-plan-wrap"
      ref={wrapRef}
      style={{ width: '100%', height: '100%', position: 'relative', '--plan-inset-top': `${inset.top}px` } as CSSProperties}
    >
      <svg
        ref={svgRef}
        data-document={documentMode ? 'true' : undefined}
        xmlns={documentMode ? 'http://www.w3.org/2000/svg' : undefined}
        width={frame ? frame.width : '100%'}
        height={frame ? frame.height : '100%'}
        fontFamily={documentMode ? 'Helvetica' : undefined}
        style={{ display: 'block', background: BG, userSelect: 'none', WebkitUserSelect: 'none', cursor: documentMode ? 'default' : panning ? 'grabbing' : panAvailable ? 'grab' : annotationMode || tool === 'wall' ? 'crosshair' : tool === 'select' ? 'default' : 'copy' }}
        onPointerDown={documentMode ? undefined : e => {
          altRef.current = e.altKey
          const raw = toScene(e.clientX, e.clientY)
          const p = snapped(raw, e)
          setCursor(p)
          if (annotationMode && onPlaceAnnotation) {
            onPlaceAnnotation(p.x, p.y, roomAt(p.x, p.y))
            return
          }
          if (e.button === 1 || e.shiftKey || spaceHeld) {
            beginPan(e.clientX, e.clientY, false)
            return
          }
          if (!editingEnabled || (tool !== 'wall' && tool !== 'door' && tool !== 'window')) {
            const hit = objectAt(p)
            if (hit) {
              onSelect(hit)
              return
            }
            if (onPanZoom && canStartEmptyPan({ zoom, tool, annotationMode, button: e.button })) {
              beginPan(e.clientX, e.clientY, true, () => onSelect(roomSelection(p)))
              return
            }
            onSelect(roomSelection(p))
            return
          }
          if (tool === 'wall') {
            if (e.button === 0) e.preventDefault()
            setDrawStart(p)
            return
          }
          if (tool === 'door' || tool === 'window') {
            const wall = nearestWall(p)
            if (wall) onPlaceOpening?.(wall.id, projectT(wall, p), tool)
            return
          }
        }}
        onPointerMove={documentMode ? undefined : e => {
          const p = snapped(toScene(e.clientX, e.clientY), e)
          setCursor(p)
        }}
        onPointerUp={documentMode ? undefined : () => {
          const end = snapRef.current?.point ?? cursor
          if (drawStart && end && tool === 'wall') {
            onDrawWall?.(drawStart, end)
          }
          setDrawStart(null)
        }}
      >
        {!documentMode && <SiteDefs id={grassId} ox={ox} oy={oy} S={S} />}
        {documentMode && frame && (
          <rect data-paper="true" x={0} y={0} width={frame.width} height={frame.height} fill={BG} />
        )}
        <g data-layer="site" className="plan-site-context" pointerEvents="none">
          {site.lot && (
            <LotLayer
              lot={site.lot}
              inferred={site.inferred}
              patternId={grassId}
              solid={documentMode}
              ox={ox}
              oy={oy}
              S={S}
            />
          )}
        </g>
        <g data-layer="landscape" pointerEvents="none">
          {site.vegetation.map((item, i) => (
            <VegetationSymbol key={i} item={item} ox={ox} oy={oy} S={S} />
          ))}
        </g>
        <g data-layer="rooms">
          {scene.rooms.map(room => (
            <polygon
              key={room.id}
              points={poly(room).map(p => `${ox + p.x * S},${oy + p.y * S}`).join(' ')}
              fill={roomFill(room.type)}
              stroke={selection?.kind === 'room' && selection.id === room.id ? '#c45c26' : 'none'}
              strokeWidth={1.5}
            >
              <title>{roomLabelText(room)}</title>
            </polygon>
          ))}
          {snapEnabled && Array.from({ length: 40 }, (_, i) => i * grid).map(g => (
            <g key={g} opacity={0.12} pointerEvents="none">
              <line x1={ox + (bounds.minX + g) * S} y1={oy + bounds.minY * S} x2={ox + (bounds.minX + g) * S} y2={oy + (bounds.minY + bounds.h) * S} stroke="#888" />
              <line x1={ox + bounds.minX * S} y1={oy + (bounds.minY + g) * S} x2={ox + (bounds.minX + bounds.w) * S} y2={oy + (bounds.minY + g) * S} stroke="#888" />
            </g>
          ))}
        </g>
        <g data-layer="furniture">
        {(scene.furniture || []).map(item => {
          const active = selection?.kind === 'furniture' && selection.id === item.id
          return (
            <g
              key={item.id}
              style={{ cursor: editingEnabled ? 'grab' : 'pointer' }}
              onPointerDown={e => {
                e.stopPropagation()
                onSelect({ kind: 'furniture', id: item.id })
                if (!editingEnabled) return
                const grab = toScene(e.clientX, e.clientY)
                const origin = { ...item.position }
                const move = (ev: PointerEvent) => {
                  const now = toScene(ev.clientX, ev.clientY)
                  onMoveFurniture?.(item.id, origin.x + now.x - grab.x, origin.y + now.y - grab.y)
                }
                const up = () => {
                  window.removeEventListener('pointermove', move)
                  window.removeEventListener('pointerup', up)
                  onEditEnd?.()
                }
                window.addEventListener('pointermove', move)
                window.addEventListener('pointerup', up)
              }}
            >
              <FurnitureSymbol item={item} ox={ox} oy={oy} S={S} active={active} back={backSides.get(item.id)} />
            </g>
          )
        })}
        </g>
        <g data-layer="walls">
        {scene.walls.map((wall: Wall) => {
          const active = selection?.kind === 'wall' && selection.id === wall.id
          return (
            <g key={wall.id}>
              {wallStrokeSegments(wall, scene.openings).map((seg, i) => (
                <line
                  key={i}
                  x1={ox + seg.a.x * S} y1={oy + seg.a.y * S}
                  x2={ox + seg.b.x * S} y2={oy + seg.b.y * S}
                  stroke={active ? '#c45c26' : '#17191c'}
                  strokeWidth={drawThickness ? wallStrokePx(wall, S) : active ? 5 : 3.5}
                  strokeLinecap={drawThickness ? 'butt' : 'square'}
                  style={panAvailable ? { cursor: 'default' } : undefined}
                  onPointerDown={e => {
                  if (!editingEnabled || tool !== 'select') return
                  e.stopPropagation()
                  onSelect({ kind: 'wall', id: wall.id })
                  const origin = toScene(e.clientX, e.clientY)
                  let last = origin
                  const move = (ev: PointerEvent) => {
                    const now = toScene(ev.clientX, ev.clientY)
                    onMoveWall?.(wall.id, now.x - last.x, now.y - last.y)
                    last = now
                  }
                  const up = () => {
                    window.removeEventListener('pointermove', move)
                    window.removeEventListener('pointerup', up)
                    onEditEnd?.()
                  }
                  window.addEventListener('pointermove', move)
                  window.addEventListener('pointerup', up)
                }}
              />
              ))}
              {active && editingEnabled && (['start', 'end'] as const).map(which => {
                const pt = wall[which]
                return (
                  <circle
                    key={which}
                    cx={ox + pt.x * S}
                    cy={oy + pt.y * S}
                    r={6}
                    fill="#faf9f5"
                    stroke="#c45c26"
                    strokeWidth={2}
                    style={{ cursor: 'grab' }}
                    onPointerDown={e => {
                      e.stopPropagation()
                      const node = nodeIdOf(wall, which)
                      const attached = scene.walls
                        .filter(w => w.id === wall.id || (node && (nodeIdOf(w, 'start') === node || nodeIdOf(w, 'end') === node)))
                        .map(w => w.id)
                      const move = (ev: PointerEvent) => {
                        const now = snapped(toScene(ev.clientX, ev.clientY), ev, attached)
                        onMoveEndpoint?.(wall.id, which, now.x, now.y)
                      }
                      const up = () => {
                        window.removeEventListener('pointermove', move)
                        window.removeEventListener('pointerup', up)
                        onEditEnd?.()
                      }
                      window.addEventListener('pointermove', move)
                      window.addEventListener('pointerup', up)
                    }}
                  />
                )
              })}
            </g>
          )
        })}
        {drawThickness && junctions.map(j => {
          const side = Math.max(j.thickness * S, MIN_WALL_PX)
          return j.square
            ? <rect key={j.key} x={ox + j.p.x * S - side / 2} y={oy + j.p.y * S - side / 2} width={side} height={side} fill="#17191c" pointerEvents="none" />
            : <circle key={j.key} cx={ox + j.p.x * S} cy={oy + j.p.y * S} r={side / 2} fill="#17191c" pointerEvents="none" />
        })}
        </g>
        <g data-layer="openings">
        {scene.openings.map((o: Opening) => {
          const wall = scene.walls.find(w => w.id === o.wallId)
          if (!wall) return null
          const active = selection?.kind === 'opening' && selection.id === o.id
          return (
            <g key={o.id} style={{ cursor: editingEnabled ? 'grab' : 'pointer' }}
              onPointerDown={e => {
                e.stopPropagation()
                onSelect({ kind: 'opening', id: o.id })
                if (!editingEnabled) return
                const move = (ev: PointerEvent) => {
                  const now = toScene(ev.clientX, ev.clientY)
                  onMoveOpening?.(o.id, projectT(wall, now))
                }
                const up = () => {
                  window.removeEventListener('pointermove', move)
                  window.removeEventListener('pointerup', up)
                  onEditEnd?.()
                }
                window.addEventListener('pointermove', move)
                window.addEventListener('pointerup', up)
              }}
            >
              <OpeningSymbol opening={o} wall={wall} ox={ox} oy={oy} S={S} active={active} />
            </g>
          )
        })}
        </g>
        {!documentMode && renderRoomLabels()}
        {!documentMode && (
          <g data-layer="dimensions" pointerEvents="none">
            {site.lot && !site.inferred && <LotDimensions lot={site.lot} ox={ox} oy={oy} S={S} />}
            {selectedWall && (
              <WallLengthDimension
                wall={selectedWall}
                center={{ x: building.minX + building.w / 2, y: building.minY + building.h / 2 }}
                ox={ox}
                oy={oy}
                S={S}
              />
            )}
          </g>
        )}
        {documentMode && (
          <g data-layer="dimension-lines" pointerEvents="none">
            {site.lot && !site.inferred && <LotDimensions sheet part="line" lot={site.lot} ox={ox} oy={oy} S={S} />}
            <SheetDimensions part="line" scene={scene} ox={ox} oy={oy} S={S} />
          </g>
        )}
        {documentMode && (
          <g data-layer="dimension-text" pointerEvents="none">
            {site.lot && !site.inferred && <LotDimensions sheet part="text" lot={site.lot} ox={ox} oy={oy} S={S} />}
            <SheetDimensions part="text" scene={scene} ox={ox} oy={oy} S={S} />
          </g>
        )}
        {documentMode && renderRoomLabels()}
        {!documentMode && [...guides, ...liveGuides].map((g, i) => (
          <line key={i} x1={ox + g.x1 * S} y1={oy + g.y1 * S} x2={ox + g.x2 * S} y2={oy + g.y2 * S} stroke="#3d7a78" strokeDasharray="4 4" opacity={0.7} />
        ))}
        {drawStart && cursor && (
          <line x1={ox + drawStart.x * S} y1={oy + drawStart.y * S} x2={ox + cursor.x * S} y2={oy + cursor.y * S} stroke="#3d7a78" strokeDasharray="6 4" />
        )}
        {tool === 'wall' && editingEnabled && cursor && (snapKind === 'vertex' || snapKind === 'intersection') && (
          <rect data-snap={snapKind} x={ox + cursor.x * S - 5} y={oy + cursor.y * S - 5} width={10} height={10} fill="none" stroke="#3d7a78" strokeWidth={1.5} pointerEvents="none" />
        )}
        {tool === 'wall' && editingEnabled && cursor && snapKind === 'segment' && (
          <circle data-snap={snapKind} cx={ox + cursor.x * S} cy={oy + cursor.y * S} r={5} fill="none" stroke="#3d7a78" strokeWidth={1.5} pointerEvents="none" />
        )}
        {documentMode && frame && (
          <g data-north="sheet" transform={`translate(${frame.width - 46} 18)`} aria-label="North">
            <NorthMark />
          </g>
        )}
      </svg>
      {!documentMode && <NorthIndicator />}
      {!documentMode && (
      <div className="archplan-note-overlay">
        {annotations.filter(isStickyVisible).map(a => (
          <button
            key={`sticky-${a.id}`}
            type="button"
            className={`plan-sticky ${a.author_role === 'CLIENT' ? 'is-client' : 'is-architect'}${a.id === selectedAnnotationId ? ' is-active' : ''}`}
            style={{ left: ox + a.x! * S, top: oy + a.y! * S }}
            data-comment-id={a.id}
            aria-label={`${commentRoleLabel(a.author_role)} by ${displayNameFromEmail(a.author_email || 'user')}`}
            title={a.body}
            onPointerDown={e => e.stopPropagation()}
            onClick={e => { e.stopPropagation(); onSelectAnnotation?.(a.id === selectedAnnotationId ? null : a.id) }}
          >
            <Note size={22} weight="fill" />
          </button>
        ))}
        {annotations.map(a => {
          if (a.id !== selectedAnnotationId || !isStickyVisible(a)) return null
          const px = ox + a.x! * S
          const py = oy + a.y! * S
          return (
            <div
              key={a.id}
              className={`plan-note-card plan-note-popup ${a.author_role === 'CLIENT' ? 'plan-note-card-client' : 'plan-note-card-architect'}`}
              style={{ left: px + 16, top: Math.max(8, py - 24) }}
              role="dialog"
              aria-label="Comment"
              onPointerDown={e => e.stopPropagation()}
            >
              <button type="button" className="plan-note-close" aria-label="Close comment" title="Close" onClick={() => onSelectAnnotation?.(null)}>
                <X size={14} weight="bold" />
              </button>
              <CommentThread thread={{ ...a, replies: a.replies || [] }} actions={commentActions} />
            </div>
          )
        })}
        {draft && (
          <form className="plan-note-card" style={{ left: ox + draft.x * S + 10, top: Math.max(8, oy + draft.y * S - 56) }}
            onSubmit={e => { e.preventDefault(); onDraftSubmit?.() }}>
            <textarea value={draft.body} onChange={e => onDraftChange?.(e.target.value)} placeholder="Write a note" autoFocus />
            <div className="plan-note-actions">
              <button type="submit">Post</button>
              <button type="button" onClick={onDraftCancel}>Cancel</button>
            </div>
          </form>
        )}
      </div>
      )}
    </div>
  )
}
