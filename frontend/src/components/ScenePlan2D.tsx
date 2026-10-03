import { useEffect, useRef, useState } from 'react'
import type { Opening, SceneDocument, Wall } from '../scene-graph/types'
import { useFormat } from '../units/UnitsProvider'
import { wallLength, wallPointAtT, projectT } from '../scene-graph/edit/geometry'
import { snapPoint } from '../scene-graph/edit/snap'
import { commentRoleLabel, PlanAnnotation } from './planAnnotations'
import { displayNameFromEmail, formatDate } from '../workflow/displayName'
import { FurnitureSymbol, OpeningSymbol, furnitureContains, openingContains, wallStrokeSegments } from './opening-symbols'

export type EditorTool = 'select' | 'wall' | 'door' | 'window' | 'measure'
export type Selection =
  | { kind: 'wall'; id: string }
  | { kind: 'opening'; id: string }
  | { kind: 'room'; id: string }
  | { kind: 'furniture'; id: string }
  | null

const BG = '#faf9f5'
const MARGIN = 48

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

function poly(room: SceneDocument['rooms'][number]) {
  if (room.polygon?.length) return room.polygon
  const { x, y } = room.position
  const { width, height } = room.dimensions
  return [
    { x, y }, { x: x + width, y }, { x: x + width, y: y + height }, { x, y: y + height },
  ]
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
  currentUserId,
  draft,
  onPlaceAnnotation,
  onSelectAnnotation,
  onDraftChange,
  onDraftSubmit,
  onDraftCancel,
  onUpdateAnnotation,
  onDeleteAnnotation,
  onMoveAnnotation,
  guides = [],
}: {
  scene: SceneDocument
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
  currentUserId?: string
  draft?: { x: number; y: number; object_id: string | null; body: string } | null
  /** Pin position in plan meters. */
  onPlaceAnnotation?: (xM: number, yM: number, roomId: string | null) => void
  onSelectAnnotation?: (id: string | null) => void
  onDraftChange?: (body: string) => void
  onDraftSubmit?: () => void
  onDraftCancel?: () => void
  onUpdateAnnotation?: (id: string, body: string) => void
  onDeleteAnnotation?: (id: string) => void
  onMoveAnnotation?: (id: string, xM: number, yM: number) => void
  guides?: Array<{ x1: number; y1: number; x2: number; y2: number }>
}) {
  const fmt = useFormat()
  const svgRef = useRef<SVGSVGElement>(null)
  const altRef = useRef(false)
  const [spaceHeld, setSpaceHeld] = useState(false)
  const [editId, setEditId] = useState<string | null>(null)
  const [editBody, setEditBody] = useState('')
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
      e.preventDefault()
      const factor = e.deltaY > 0 ? 0.92 : 1.08
      onPanZoomRef.current(Math.min(4, Math.max(0.4, zoomRef.current * factor)), panRef.current)
    }
    el.addEventListener('wheel', onWheel, { passive: false })
    return () => el.removeEventListener('wheel', onWheel)
  }, [])

  const bounds = sceneBounds(scene)
  const baseS = Math.min((cw - MARGIN * 2) / bounds.w, (ch - MARGIN * 2) / bounds.h)
  const S = baseS * zoom
  const ox = MARGIN + pan.x - bounds.minX * S
  const oy = MARGIN + pan.y - bounds.minY * S

  const toScene = (clientX: number, clientY: number) => {
    const svg = svgRef.current
    if (!svg) return { x: 0, y: 0 }
    const ctm = svg.getScreenCTM()
    if (!ctm) return { x: 0, y: 0 }
    const p = svg.createSVGPoint()
    p.x = clientX
    p.y = clientY
    const loc = p.matrixTransform(ctm.inverse())
    return { x: (loc.x - ox) / S, y: (loc.y - oy) / S }
  }

  const snapped = (p: { x: number; y: number }, ev?: { altKey?: boolean }) => {
    if (ev?.altKey != null) altRef.current = ev.altKey
    const result = snapPoint(p, {
      grid,
      enabled: snapEnabled && !altRef.current && (editingEnabled || false),
      walls: scene.walls,
    })
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

  return (
    <div
      className="scene-plan-wrap"
      ref={wrapRef}
      style={{ width: '100%', height: '100%', position: 'relative' }}
    >
      <svg
        ref={svgRef}
        width="100%"
        height="100%"
        style={{ display: 'block', background: BG, cursor: annotationMode || tool === 'wall' ? 'crosshair' : tool === 'select' ? 'default' : 'copy' }}
        onPointerDown={e => {
          altRef.current = e.altKey
          const raw = toScene(e.clientX, e.clientY)
          const p = snapped(raw, e)
          setCursor(p)
          if (annotationMode && onPlaceAnnotation) {
            onPlaceAnnotation(p.x, p.y, roomAt(p.x, p.y))
            return
          }
          if (e.button === 1 || e.shiftKey || spaceHeld) {
            const sx = e.clientX, sy = e.clientY
            const startPan = { ...pan }
            const move = (ev: PointerEvent) => {
              onPanZoom?.(zoom, { x: startPan.x + (ev.clientX - sx), y: startPan.y + (ev.clientY - sy) })
            }
            const up = () => {
              window.removeEventListener('pointermove', move)
              window.removeEventListener('pointerup', up)
            }
            window.addEventListener('pointermove', move)
            window.addEventListener('pointerup', up)
            return
          }
          if (!editingEnabled) {
            const wall = nearestWall(p)
            const opening = scene.openings.find(o => {
              const host = scene.walls.find(w => w.id === o.wallId)
              return host ? openingContains(o, host, p) : false
            })
            const furn = (scene.furniture || []).find(f => furnitureContains(f, p))
            if (opening) onSelect({ kind: 'opening', id: opening.id })
            else if (furn) onSelect({ kind: 'furniture', id: furn.id })
            else if (wall) onSelect({ kind: 'wall', id: wall.id })
            else {
              const rid = roomAt(p.x, p.y)
              onSelect(rid ? { kind: 'room', id: rid } : null)
            }
            return
          }
          if (tool === 'wall') {
            setDrawStart(p)
            return
          }
          if (tool === 'door' || tool === 'window') {
            const wall = nearestWall(p)
            if (wall) onPlaceOpening?.(wall.id, projectT(wall, p), tool)
            return
          }
          const wall = nearestWall(p)
          const opening = scene.openings.find(o => {
            const host = scene.walls.find(w => w.id === o.wallId)
            return host ? openingContains(o, host, p) : false
          })
          const furn = (scene.furniture || []).find(f => furnitureContains(f, p))
          if (opening) onSelect({ kind: 'opening', id: opening.id })
          else if (furn) onSelect({ kind: 'furniture', id: furn.id })
          else if (wall) onSelect({ kind: 'wall', id: wall.id })
          else {
            const rid = roomAt(p.x, p.y)
            onSelect(rid ? { kind: 'room', id: rid } : null)
          }
        }}
        onPointerMove={e => {
          const p = snapped(toScene(e.clientX, e.clientY), e)
          setCursor(p)
        }}
        onPointerUp={() => {
          if (drawStart && cursor && tool === 'wall') {
            onDrawWall?.(drawStart, cursor)
          }
          setDrawStart(null)
        }}
      >
        {snapEnabled && Array.from({ length: 40 }, (_, i) => i * grid).map(g => (
          <g key={g} opacity={0.12}>
            <line x1={ox + (bounds.minX + g) * S} y1={oy + bounds.minY * S} x2={ox + (bounds.minX + g) * S} y2={oy + (bounds.minY + bounds.h) * S} stroke="#888" />
            <line x1={ox + bounds.minX * S} y1={oy + (bounds.minY + g) * S} x2={ox + (bounds.minX + bounds.w) * S} y2={oy + (bounds.minY + g) * S} stroke="#888" />
          </g>
        ))}
        {scene.rooms.map(room => {
          const pts = poly(room).map(p => `${ox + p.x * S},${oy + p.y * S}`).join(' ')
          const c = poly(room).reduce((a, p) => ({ x: a.x + p.x, y: a.y + p.y }), { x: 0, y: 0 })
          const n = poly(room).length || 1
          return (
            <g key={room.id}>
              <polygon points={pts} fill={selected?.kind === 'room' && selected.id === room.id ? '#e8eef8' : '#f4f6f8'} stroke="none" />
              <text x={ox + (c.x / n) * S} y={oy + (c.y / n) * S} textAnchor="middle" fontSize={11} fill="#444">{room.name}</text>
            </g>
          )
        })}
        {scene.walls.map((wall: Wall) => {
          const active = selected?.kind === 'wall' && selected.id === wall.id
          return (
            <g key={wall.id}>
              {wallStrokeSegments(wall, scene.openings).map((seg, i) => (
                <line
                  key={i}
                  x1={ox + seg.a.x * S} y1={oy + seg.a.y * S}
                  x2={ox + seg.b.x * S} y2={oy + seg.b.y * S}
                  stroke={active ? '#c45c26' : '#17191c'}
                  strokeWidth={active ? 5 : 3.5}
                  strokeLinecap="square"
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
                      const move = (ev: PointerEvent) => {
                        const now = snapped(toScene(ev.clientX, ev.clientY), ev)
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
              {active && (
                <text
                  x={ox + ((wall.start.x + wall.end.x) / 2) * S}
                  y={oy + ((wall.start.y + wall.end.y) / 2) * S - 8}
                  textAnchor="middle"
                  fontSize={11}
                  fill="#c45c26"
                >
                  {fmt.length(wallLength(wall))}
                </text>
              )}
            </g>
          )
        })}
        {scene.openings.map((o: Opening) => {
          const wall = scene.walls.find(w => w.id === o.wallId)
          if (!wall) return null
          const active = selected?.kind === 'opening' && selected.id === o.id
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
        {(scene.furniture || []).map(item => {
          const active = selected?.kind === 'furniture' && selected.id === item.id
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
              <FurnitureSymbol item={item} ox={ox} oy={oy} S={S} active={active} />
            </g>
          )
        })}
        {[...guides, ...liveGuides].map((g, i) => (
          <line key={i} x1={ox + g.x1 * S} y1={oy + g.y1 * S} x2={ox + g.x2 * S} y2={oy + g.y2 * S} stroke="#3d7a78" strokeDasharray="4 4" opacity={0.7} />
        ))}
        {drawStart && cursor && (
          <line x1={ox + drawStart.x * S} y1={oy + drawStart.y * S} x2={ox + cursor.x * S} y2={oy + cursor.y * S} stroke="#3d7a78" strokeDasharray="6 4" />
        )}
        {annotations.map(a => {
          const pt = a.x != null && a.y != null ? { x: a.x, y: a.y } : null
          if (!pt) return null
          const isClient = a.author_role === 'CLIENT'
          return (
            <circle
              key={a.id}
              cx={ox + pt.x * S}
              cy={oy + pt.y * S}
              r={5}
              fill={isClient ? '#17191c' : '#3d7a78'}
              stroke="#faf9f5"
              onClick={e => { e.stopPropagation(); onSelectAnnotation?.(a.id) }}
            />
          )
        })}
      </svg>
      <div className="archplan-note-overlay">
        {annotations.map(a => {
          if (a.id !== selectedAnnotationId || a.x == null || a.y == null) return null
          const px = ox + a.x * S
          const py = oy + a.y * S
          const mine = a.author_id === currentUserId
          return (
            <div key={a.id} className="plan-note-card" style={{ left: px + 10, top: Math.max(8, py - 78) }}>
              <p className="plan-note-role">{commentRoleLabel(a.author_role)}</p>
              <p className="plan-note-author">{displayNameFromEmail(a.author_email || 'client')}</p>
              {editId === a.id ? (
                <>
                  <textarea
                    className="plan-note-editor"
                    value={editBody}
                    onChange={e => setEditBody(e.target.value)}
                    aria-label="Edit comment"
                  />
                  <div className="plan-note-actions">
                    <button type="button" onClick={() => { setEditId(null); setEditBody('') }}>Cancel</button>
                    <button type="button" onClick={() => {
                      if (editBody.trim()) onUpdateAnnotation?.(a.id, editBody.trim())
                      setEditId(null)
                      setEditBody('')
                    }}>Save</button>
                  </div>
                </>
              ) : (
                <>
                  <p className="plan-note-body">{a.body}</p>
                  {a.created_at && <p className="plan-note-meta">{formatDate(a.created_at)}</p>}
                  {mine && (
                    <div className="plan-note-actions">
                      <button type="button" onClick={() => { setEditId(a.id); setEditBody(a.body) }}>Edit</button>
                      <button type="button" onClick={() => onDeleteAnnotation?.(a.id)}>Delete</button>
                    </div>
                  )}
                </>
              )}
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
    </div>
  )
}
