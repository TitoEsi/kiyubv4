import type { Room, RoomType } from './types'

type Pt = { x: number; y: number }
export type LabelRect = { x: number; y: number; width: number; height: number }

export interface RoomLabelLayout {
  /** Screen-space centre of the text block. */
  x: number
  y: number
  fontSize: number
  lineHeight: number
  lines: string[]
}

const MAX_FONT = 12
const MIN_FONT = 7.5
const FONT_STEP = 0.5
/** Uppercase glyph advance (incl. 0.06em letter-spacing) as a fraction of font size. */
const GLYPH = 0.64
const LINE = 1.15
const FILL_W = 0.86
const FILL_H = 0.8

const ABBREV: Partial<Record<RoomType, string>> = {
  bathroom: 'BATH',
  toilet: 'WC',
  storage: 'STOR',
  laundry: 'LDRY',
  hallway: 'HALL',
  corridor: 'HALL',
  utility: 'UTIL',
  stairs: 'STAIR',
  entry: 'ENTRY',
  garage: 'GAR',
  office: 'OFF',
}

function humanize(type: string): string {
  return type.replace(/[_-]+/g, ' ').trim().toUpperCase() || 'ROOM'
}

/** Display text for a room; internal-looking names fall back to the room type. */
export function roomLabelText(room: Pick<Room, 'name' | 'type'>): string {
  const name = (room.name || '').trim().replace(/\s+/g, ' ')
  if (!name) return humanize(room.type)
  const idLike = /^[a-z0-9_-]+$/.test(name) && (/[\d_-]/.test(name) || name === room.type)
  if (idLike) return humanize(room.type)
  return name.replace(/_/g, ' ').toUpperCase()
}

export function roomPolygon(room: Room): Pt[] {
  if (room.polygon?.length) return room.polygon
  const { x, y } = room.position
  const { width, height } = room.dimensions
  return [{ x, y }, { x: x + width, y }, { x: x + width, y: y + height }, { x, y: y + height }]
}

function inside(pts: Pt[], p: Pt): boolean {
  let hit = false
  for (let i = 0, j = pts.length - 1; i < pts.length; j = i++) {
    const a = pts[i], b = pts[j]
    if ((a.y > p.y) !== (b.y > p.y) && p.x < ((b.x - a.x) * (p.y - a.y)) / (b.y - a.y + 1e-12) + a.x) hit = !hit
  }
  return hit
}

function anchor(pts: Pt[]): Pt {
  let a = 0, cx = 0, cy = 0
  for (let i = 0, j = pts.length - 1; i < pts.length; j = i++) {
    const cross = pts[j].x * pts[i].y - pts[i].x * pts[j].y
    a += cross
    cx += (pts[j].x + pts[i].x) * cross
    cy += (pts[j].y + pts[i].y) * cross
  }
  const avg = pts.reduce((s, p) => ({ x: s.x + p.x / pts.length, y: s.y + p.y / pts.length }), { x: 0, y: 0 })
  if (Math.abs(a) < 1e-9) return avg
  const c = { x: cx / (3 * a), y: cy / (3 * a) }
  if (inside(pts, c)) return c
  if (inside(pts, avg)) return avg
  return deepestPoint(pts) ?? c
}

function edgeDistance(pts: Pt[], p: Pt): number {
  let best = Infinity
  for (let i = 0, j = pts.length - 1; i < pts.length; j = i++) {
    const a = pts[j], b = pts[i]
    const dx = b.x - a.x, dy = b.y - a.y
    const len2 = dx * dx + dy * dy
    const t = len2 > 0 ? Math.max(0, Math.min(1, ((p.x - a.x) * dx + (p.y - a.y) * dy) / len2)) : 0
    best = Math.min(best, Math.hypot(p.x - (a.x + t * dx), p.y - (a.y + t * dy)))
  }
  return best
}

/** Grid-sampled interior point farthest from the outline (for concave rooms). */
function deepestPoint(pts: Pt[]): Pt | null {
  const xs = pts.map(p => p.x), ys = pts.map(p => p.y)
  const minX = Math.min(...xs), maxX = Math.max(...xs), minY = Math.min(...ys), maxY = Math.max(...ys)
  const N = 16
  let best: Pt | null = null
  let bestD = -1
  for (let i = 0; i < N; i++) {
    for (let j = 0; j < N; j++) {
      const p = { x: minX + ((i + 0.5) / N) * (maxX - minX), y: minY + ((j + 0.5) / N) * (maxY - minY) }
      if (!inside(pts, p)) continue
      const d = edgeDistance(pts, p)
      if (d > bestD) { bestD = d; best = p }
    }
  }
  return best
}

/** Interval of the polygon interior along a horizontal (axis 'x') or vertical line through p. */
function chord(pts: Pt[], p: Pt, axis: 'x' | 'y'): [number, number] | null {
  const hits: number[] = []
  const u = axis === 'x' ? 'x' : 'y'
  const v = axis === 'x' ? 'y' : 'x'
  for (let i = 0, j = pts.length - 1; i < pts.length; j = i++) {
    const a = pts[j], b = pts[i]
    if ((a[v] > p[v]) !== (b[v] > p[v])) hits.push(a[u] + ((p[v] - a[v]) * (b[u] - a[u])) / (b[v] - a[v]))
  }
  hits.sort((m, n) => m - n)
  for (let k = 0; k + 1 < hits.length; k += 2) {
    if (p[u] >= hits[k] - 1e-9 && p[u] <= hits[k + 1] + 1e-9) return [hits[k], hits[k + 1]]
  }
  return null
}

const textWidth = (s: string, fs: number) => s.length * GLYPH * fs

function wrap(words: string[], n: number): string[] {
  if (n <= 1 || words.length < n) return [words.join(' ')]
  const target = words.join(' ').length / n
  const lines: string[] = []
  let cur: string[] = []
  for (let i = 0; i < words.length; i++) {
    const remainingWords = words.length - i
    const remainingLines = n - lines.length
    const next = [...cur, words[i]].join(' ')
    if (cur.length && remainingLines > 1 && (next.length > target * 1.15 || remainingWords < remainingLines)) {
      lines.push(cur.join(' '))
      cur = [words[i]]
    } else {
      cur.push(words[i])
    }
  }
  if (cur.length) lines.push(cur.join(' '))
  return lines
}

function fit(text: string, availW: number, availH: number, maxLines: number) {
  const words = text.split(' ').filter(Boolean)
  for (let fs = MAX_FONT; fs >= MIN_FONT - 1e-9; fs -= FONT_STEP) {
    for (let n = 1; n <= Math.min(maxLines, words.length); n++) {
      const lines = wrap(words, n)
      const w = Math.max(...lines.map(l => textWidth(l, fs)))
      const h = lines.length * fs * LINE
      if (w <= availW * FILL_W && h <= availH * FILL_H) return { fontSize: fs, lines, w, h }
    }
  }
  return null
}

function overlaps(a: LabelRect, b: LabelRect) {
  return a.x < b.x + b.width && b.x < a.x + a.width && a.y < b.y + b.height && b.y < a.y + a.height
}

/** Fits one label inside the room on screen; `furniture` rects are in plan meters. */
export function layoutRoomLabel(
  room: Room,
  S: number,
  ox: number,
  oy: number,
  furniture: LabelRect[] = [],
): RoomLabelLayout | null {
  const pts = roomPolygon(room)
  if (pts.length < 3 || !(S > 0)) return null
  const c = anchor(pts)
  const hx = chord(pts, c, 'x')
  const vy = chord(pts, c, 'y')
  if (!hx || !vy) return null
  const availW = (hx[1] - hx[0]) * S
  const availH = (vy[1] - vy[0]) * S
  const text = roomLabelText(room)
  const fitted = fit(text, availW, availH, 3)
    ?? fit(ABBREV[room.type] ?? text.split(' ')[0], availW, availH, 1)
  if (!fitted) return null

  const boxAt = (p: Pt): LabelRect => {
    const w = fitted.w / S, h = fitted.h / S
    return { x: p.x - w / 2, y: p.y - h / 2, width: w, height: h }
  }
  const clear = (p: Pt) => !furniture.some(f => overlaps(boxAt(p), f))
  const horizontal = hx[1] - hx[0] >= vy[1] - vy[0]
  const [lo, hi] = horizontal ? hx : vy
  const half = (horizontal ? fitted.w : fitted.h) / S / 2
  const candidates: Pt[] = [c]
  for (const f of [0.3, 0.7]) {
    const along = lo + (hi - lo) * f
    if (along - half < lo || along + half > hi) continue
    const p = horizontal ? { x: along, y: c.y } : { x: c.x, y: along }
    const cross = chord(pts, p, horizontal ? 'y' : 'x')
    const halfCross = (horizontal ? fitted.h : fitted.w) / S / 2
    const at = horizontal ? p.y : p.x
    if (!cross || at - halfCross < cross[0] || at + halfCross > cross[1]) continue
    candidates.push(p)
  }
  const pick = candidates.find(clear) ?? c
  return {
    x: ox + pick.x * S,
    y: oy + pick.y * S,
    fontSize: fitted.fontSize,
    lineHeight: fitted.fontSize * LINE,
    lines: fitted.lines,
  }
}

const SHEET_MAX = 13
const SHEET_MIN = 8

/** Drawing-case room name for the PDF. Uses the sidebar name and does not abbreviate. */
export function sheetRoomName(name: string): string {
  const cleaned = (name || '').trim().replace(/[_-]+/g, ' ').replace(/\s+/g, ' ')
  return cleaned ? cleaned.toUpperCase() : 'ROOM'
}

/**
 * One label inside the room for the PDF sheet. Always returns a layout, even when
 * the fitted room is smaller than the minimum type size.
 */
export function sheetRoomLabel(room: Room, name: string, S: number, ox: number, oy: number): RoomLabelLayout {
  const pts = roomPolygon(room)
  const c = pts.length >= 3
    ? anchor(pts)
    : {
        x: room.position.x + room.dimensions.width / 2,
        y: room.position.y + room.dimensions.height / 2,
      }
  const text = sheetRoomName(name)
  const words = text.split(' ').filter(Boolean)
  const hx = pts.length >= 3 ? chord(pts, c, 'x') : null
  const vy = pts.length >= 3 ? chord(pts, c, 'y') : null
  const availW = hx ? (hx[1] - hx[0]) * S : Math.max(room.dimensions.width * S, 1)
  const availH = vy ? (vy[1] - vy[0]) * S : Math.max(room.dimensions.height * S, 1)
  let fontSize = SHEET_MIN
  let lines = words.length ? [words.join(' ')] : ['ROOM']
  for (let fs = SHEET_MAX; fs >= SHEET_MIN - 1e-9; fs -= FONT_STEP) {
    let fitted = false
    for (let n = 1; n <= Math.min(3, words.length || 1); n++) {
      const candidate = wrap(words.length ? words : ['ROOM'], n)
      const w = Math.max(...candidate.map(line => textWidth(line, fs)))
      const h = candidate.length * fs * LINE
      if (w <= availW * FILL_W && h <= availH * FILL_H) {
        fontSize = fs
        lines = candidate
        fitted = true
        break
      }
    }
    if (fitted) break
  }
  return {
    x: ox + c.x * S,
    y: oy + c.y * S,
    fontSize,
    lineHeight: fontSize * LINE,
    lines,
  }
}
