import type { Rect, Vegetation } from '../scene-graph/site/site-context'
import type { SceneDocument, Wall } from '../scene-graph/types'
import { sheetDimensions } from '../export/sheetDimensions'
import { useFormat } from '../units/UnitsProvider'

const GRASS_BASE = '#eef2e8'
const GRASS_STROKE = '#93a386'
const LOT_LINE = '#6f7a6a'
const CANOPY_FILL = 'rgba(122, 140, 110, 0.16)'
const CANOPY_LINE = '#7d8c72'
const SHRUB_FILL = 'rgba(110, 128, 98, 0.2)'
const DIM_INK = '#5f6670'
const PAPER = '#faf9f5'
/** Explicit sheet ink. svg2pdf paints a text stroke on top of the fill, so the sheet must not use a halo. */
const SHEET_INK = '#17191c'
const GRASS_TILE_M = 3
const MIN_TUFT_TILE_PX = 36

type View = { ox: number; oy: number; S: number }
type P = { x: number; y: number }

/** Deterministic 0..1 value for a (seed, index) pair. */
function hash01(seed: number, i: number): number {
  let h = (seed * 374761393 + i * 668265263) | 0
  h = Math.imul(h ^ (h >>> 13), 1274126177)
  h ^= h >>> 16
  return (h >>> 0) / 4294967295
}

/** Sparse grass tile in plan meters; translated with the plan so it pans and zooms with it. */
export function SiteDefs({ id, ox, oy, S }: View & { id: string }) {
  const p = GRASS_TILE_M * S
  const tufts = p >= MIN_TUFT_TILE_PX
  const tuft = (x: number, y: number, s: number) =>
    `M${p * x} ${p * y} q${p * s * 0.2} ${-p * s * 0.7} ${p * s * 0.55} ${-p * s} M${p * x + p * s * 0.35} ${p * y} q${-p * s * 0.05} ${-p * s * 0.55} ${-p * s * 0.35} ${-p * s * 0.8}`
  return (
    <defs>
      <pattern id={id} width={p} height={p} patternUnits="userSpaceOnUse" patternTransform={`translate(${ox} ${oy})`}>
        <rect width={p} height={p} fill={GRASS_BASE} />
        {tufts && (
          <g stroke={GRASS_STROKE} strokeWidth={0.6} strokeLinecap="round" fill="none" opacity={0.3}>
            <path d={tuft(0.14, 0.27, 0.05)} />
            <path d={tuft(0.61, 0.52, 0.04)} />
            <path d={tuft(0.33, 0.86, 0.045)} />
          </g>
        )}
      </pattern>
    </defs>
  )
}

export function LotLayer({
  lot, inferred, patternId, ox, oy, S, solid = false,
}: View & { lot: Rect; inferred: boolean; patternId?: string; solid?: boolean }) {
  return (
    <rect
      x={ox + lot.x * S}
      y={oy + lot.y * S}
      width={lot.width * S}
      height={lot.height * S}
      fill={solid || !patternId ? GRASS_BASE : `url(#${patternId})`}
      stroke={LOT_LINE}
      strokeWidth={0.75}
      strokeDasharray={inferred ? '4 3' : undefined}
    />
  )
}

/** Closed organic outline: `lobes` bulges whose radii vary deterministically by `seed`. */
export function lobedPath(cx: number, cy: number, R: number, lobes: number, phase: number, seed = 0, jitter = 0): string {
  const step = (Math.PI * 2) / lobes
  const pt = (a: number, r: number) => `${(cx + Math.cos(a) * r).toFixed(2)} ${(cy + Math.sin(a) * r).toFixed(2)}`
  const rad = (i: number) => R * (1 - jitter / 2 + jitter * hash01(seed, i % lobes))
  let d = `M${pt(phase, rad(0) * 0.86)}`
  for (let i = 0; i < lobes; i++) {
    const a0 = phase + i * step
    const r0 = rad(i), r1 = rad(i + 1)
    d += ` Q${pt(a0 + step / 2, ((r0 + r1) / 2) * 1.1)} ${pt(a0 + step, r1 * 0.86)}`
  }
  return `${d} Z`
}

const TREE_LOBES: Record<string, [number, number]> = { 'tree-lg': [7, 11], 'tree-md': [6, 9], 'tree-sm': [5, 7] }

export function TreeSymbol({ item, ox, oy, S }: View & { item: Vegetation }) {
  const cx = ox + item.x * S
  const cy = oy + item.y * S
  const R = item.r * S
  const v = item.variant
  const [lo, hi] = TREE_LOBES[item.kind] ?? [6, 9]
  const lobes = lo + Math.floor(hash01(v, 101) * (hi - lo + 1))
  const phase = hash01(v, 102) * Math.PI * 2
  const trunk = Math.max(0.8, 0.08 * S)
  const large = item.kind !== 'tree-sm'
  const arcs = large ? 2 + Math.floor(hash01(v, 103) * 2) : 0
  return (
    <g>
      <path d={lobedPath(cx, cy, R, lobes, phase, v, 0.22)} fill={CANOPY_FILL} stroke={CANOPY_LINE} strokeWidth={0.75} />
      {large && (
        <path
          d={lobedPath(cx, cy, R * 0.6, Math.max(4, lobes - 3), phase + 0.7, v + 17, 0.3)}
          fill="none"
          stroke={CANOPY_LINE}
          strokeWidth={0.45}
          opacity={0.5}
        />
      )}
      {Array.from({ length: arcs }, (_, i) => {
        const a = phase + (i / arcs) * Math.PI * 2 + hash01(v, 110 + i)
        const r = R * (0.72 + 0.12 * hash01(v, 120 + i))
        const span = 0.5 + 0.3 * hash01(v, 130 + i)
        const p0 = { x: cx + Math.cos(a) * r, y: cy + Math.sin(a) * r }
        const p1 = { x: cx + Math.cos(a + span) * r, y: cy + Math.sin(a + span) * r }
        return (
          <path
            key={i}
            d={`M${p0.x.toFixed(2)} ${p0.y.toFixed(2)} A${r.toFixed(2)} ${r.toFixed(2)} 0 0 1 ${p1.x.toFixed(2)} ${p1.y.toFixed(2)}`}
            fill="none"
            stroke={CANOPY_LINE}
            strokeWidth={0.45}
            opacity={0.45}
          />
        )
      })}
      <circle cx={cx} cy={cy} r={trunk} fill={CANOPY_LINE} opacity={0.8} />
    </g>
  )
}

export function ShrubSymbol({ item, ox, oy, S }: View & { item: Vegetation }) {
  const phase = hash01(item.variant, 201) * Math.PI * 2
  return (
    <path
      d={lobedPath(ox + item.x * S, oy + item.y * S, item.r * S, 5 + (item.variant % 2), phase, item.variant, 0.2)}
      fill={SHRUB_FILL}
      stroke={CANOPY_LINE}
      strokeWidth={0.5}
    />
  )
}

export function PlantingCluster({ item, ox, oy, S }: View & { item: Vegetation }) {
  const r = item.r * 0.5
  const turn = hash01(item.variant, 301) * Math.PI * 2
  return (
    <g>
      {[0, 1, 2].map(i => {
        const a = turn + (i * Math.PI * 2) / 3
        const ri = r * (0.85 + 0.3 * hash01(item.variant, 310 + i))
        return (
          <path
            key={i}
            d={lobedPath(ox + (item.x + Math.cos(a) * r) * S, oy + (item.y + Math.sin(a) * r) * S, ri * S, 5, a, item.variant + i, 0.2)}
            fill={SHRUB_FILL}
            stroke={CANOPY_LINE}
            strokeWidth={0.5}
          />
        )
      })}
    </g>
  )
}

export function VegetationSymbol(props: View & { item: Vegetation }) {
  if (props.item.kind === 'shrub') return <ShrubSymbol {...props} />
  if (props.item.kind === 'cluster') return <PlantingCluster {...props} />
  return <TreeSymbol {...props} />
}

/**
 * Architectural dimension between screen points `a` and `b`, offset along the unit normal `n`:
 * extension lines (with a gap at the object and overshoot past the line), 45° ticks and centred text.
 */
export function Dimension({
  a, b, n, offset, gap = 3, text, ink = DIM_INK, fontSize = 10, forceText = false,
  part = 'all', lineWidth = 0.6, halo = true,
}: {
  a: P
  b: P
  n: P
  offset: number
  gap?: number
  text: string
  ink?: string
  /** Sheet drawings pass a size that stays readable after fit-to-page. */
  fontSize?: number
  /** Overall dimensions always show their text. */
  forceText?: boolean
  /** Sheet drawings split the line and the value so names can sit above the values. */
  part?: 'line' | 'text' | 'all'
  lineWidth?: number
  /** Canvas halo. The PDF sheet turns this off because svg2pdf strokes text after the fill. */
  halo?: boolean
}) {
  const len = Math.hypot(b.x - a.x, b.y - a.y)
  if (len < 1) return null
  const d = { x: (b.x - a.x) / len, y: (b.y - a.y) / len }
  const over = 4
  const tick = 3
  const at = (p: P, k: number) => ({ x: p.x + n.x * k, y: p.y + n.y * k })
  const a1 = at(a, offset), b1 = at(b, offset)
  const t = { x: ((d.x + n.x) / Math.SQRT2) * tick, y: ((d.y + n.y) / Math.SQRT2) * tick }
  const seg = (p: P, q: P) => `M${p.x.toFixed(2)} ${p.y.toFixed(2)} L${q.x.toFixed(2)} ${q.y.toFixed(2)}`
  const mid = { x: (a1.x + b1.x) / 2, y: (a1.y + b1.y) / 2 }
  let angle = (Math.atan2(d.y, d.x) * 180) / Math.PI
  if (angle > 90) angle -= 180
  if (angle <= -90) angle += 180
  const showText = forceText || len > text.length * 5.5 + 8
  return (
    <g>
      {part !== 'text' && (
        <path
          d={[
            seg(at(a, gap), at(a, offset + over)),
            seg(at(b, gap), at(b, offset + over)),
            seg(a1, b1),
            seg({ x: a1.x - t.x, y: a1.y - t.y }, { x: a1.x + t.x, y: a1.y + t.y }),
            seg({ x: b1.x - t.x, y: b1.y - t.y }, { x: b1.x + t.x, y: b1.y + t.y }),
          ].join(' ')}
          stroke={ink}
          strokeWidth={lineWidth}
          fill="none"
        />
      )}
      {part !== 'line' && showText && (
        <text
          x={mid.x}
          y={mid.y}
          dy="0.35em"
          textAnchor="middle"
          fontSize={fontSize}
          fontWeight={halo ? undefined : 'normal'}
          fill={ink}
          stroke={halo ? PAPER : 'none'}
          strokeWidth={halo ? 3 : undefined}
          strokeLinejoin={halo ? 'round' : undefined}
          paintOrder={halo ? 'stroke' : undefined}
          transform={angle ? `rotate(${angle.toFixed(2)} ${mid.x.toFixed(2)} ${mid.y.toFixed(2)})` : undefined}
        >
          {text}
        </text>
      )}
    </g>
  )
}

/** Overall building size and exterior segment chains for the PDF sheet only. */
export function SheetDimensions({
  scene, ox, oy, S, part = 'all',
}: View & { scene: SceneDocument; part?: 'line' | 'text' | 'all' }) {
  const fmt = useFormat()
  const dims = sheetDimensions(scene)
  if (!dims.length) return null
  return (
    <g data-footprint="true" data-sheet-dimensions="true">
      {dims.map((dim, i) => (
        <Dimension
          key={`${dim.role}-${i}`}
          a={{ x: ox + dim.a.x * S, y: oy + dim.a.y * S }}
          b={{ x: ox + dim.b.x * S, y: oy + dim.b.y * S }}
          n={dim.outward}
          offset={dim.role === 'overall' ? 46 : 22}
          fontSize={dim.role === 'overall' ? 12 : 10}
          forceText={dim.role === 'overall'}
          text={fmt.length(dim.lengthM)}
          part={part}
          ink={SHEET_INK}
          halo={false}
          lineWidth={dim.role === 'overall' ? 1.1 : 0.85}
        />
      ))}
    </g>
  )
}

/** Overall width and depth of the building footprint, outside the plan on the bottom and right. */
export function FootprintDimensions({
  box, ox, oy, S,
}: View & { box: { minX: number; minY: number; width: number; depth: number } }) {
  const fmt = useFormat()
  if (box.width < 1e-6 || box.depth < 1e-6) return null
  const x0 = ox + box.minX * S
  const y0 = oy + box.minY * S
  const x1 = x0 + box.width * S
  const y1 = y0 + box.depth * S
  return (
    <g data-footprint="true">
      <Dimension a={{ x: x0, y: y1 }} b={{ x: x1, y: y1 }} n={{ x: 0, y: 1 }} offset={26} text={fmt.length(box.width)} />
      <Dimension a={{ x: x1, y: y0 }} b={{ x: x1, y: y1 }} n={{ x: 1, y: 0 }} offset={26} text={fmt.length(box.depth)} />
    </g>
  )
}

export function LotDimensions({
  lot, ox, oy, S, sheet = false, part = 'all',
}: View & { lot: Rect; sheet?: boolean; part?: 'line' | 'text' | 'all' }) {
  const fmt = useFormat()
  const x0 = ox + lot.x * S
  const y0 = oy + lot.y * S
  const x1 = x0 + lot.width * S
  const y1 = y0 + lot.height * S
  const sheetProps = sheet ? { ink: SHEET_INK, halo: false as const, lineWidth: 0.85, fontSize: 10, part } : { part }
  return (
    <g className="plan-lot-dimensions">
      <Dimension a={{ x: x0, y: y0 }} b={{ x: x1, y: y0 }} n={{ x: 0, y: -1 }} offset={22} text={fmt.length(lot.width)} {...sheetProps} />
      <Dimension a={{ x: x0, y: y1 }} b={{ x: x0, y: y0 }} n={{ x: -1, y: 0 }} offset={22} text={fmt.length(lot.height)} {...sheetProps} />
    </g>
  )
}

/** Selected-wall length, placed on the side of the wall away from `center` (plan meters). */
export function WallLengthDimension({ wall, center, ox, oy, S }: View & { wall: Wall; center: P }) {
  const fmt = useFormat()
  const dx = wall.end.x - wall.start.x, dy = wall.end.y - wall.start.y
  const len = Math.hypot(dx, dy)
  if (len < 1e-6) return null
  let n = { x: -dy / len, y: dx / len }
  const mid = { x: (wall.start.x + wall.end.x) / 2, y: (wall.start.y + wall.end.y) / 2 }
  if ((mid.x - center.x) * n.x + (mid.y - center.y) * n.y < 0) n = { x: -n.x, y: -n.y }
  const half = ((wall.thickness || 0.15) / 2) * S
  return (
    <Dimension
      a={{ x: ox + wall.start.x * S, y: oy + wall.start.y * S }}
      b={{ x: ox + wall.end.x * S, y: oy + wall.end.y * S }}
      n={n}
      gap={half + 2}
      offset={half + 16}
      text={fmt.length(len)}
      ink="#c45c26"
    />
  )
}
