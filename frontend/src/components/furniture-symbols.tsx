import type { ReactNode } from 'react'
import type { Furniture, Wall } from '../scene-graph/types'

export type BackSide = 'top' | 'right' | 'bottom' | 'left'

const LINE = '#8a8680'
const ACTIVE = '#c45c26'
const PAPER = '#f7f4ef'
const ACTIVE_PAPER = '#efe6dc'
const MIN_DETAIL_PX = 8

const BACK_TURN: Record<BackSide, number> = { top: 0, right: 90, bottom: 180, left: 270 }

function segDist(p: { x: number; y: number }, a: { x: number; y: number }, b: { x: number; y: number }) {
  const dx = b.x - a.x, dy = b.y - a.y
  const len2 = dx * dx + dy * dy
  const t = len2 > 0 ? Math.max(0, Math.min(1, ((p.x - a.x) * dx + (p.y - a.y) * dy) / len2)) : 0
  return Math.hypot(p.x - (a.x + t * dx), p.y - (a.y + t * dy))
}

/** The item side (in its unrotated frame) that sits against the nearest wall; the engine sends no orientation. */
export function furnitureBackSide(item: Furniture, walls: Wall[]): BackSide {
  if (!walls.length) return 'top'
  const { width: w, height: h } = item.dimensions
  const cx = item.position.x + w / 2
  const cy = item.position.y + h / 2
  const ang = ((item.rotation || 0) * Math.PI) / 180
  const cos = Math.cos(ang), sin = Math.sin(ang)
  const sides: Array<[BackSide, number, number]> = [['top', 0, -h / 2], ['right', w / 2, 0], ['bottom', 0, h / 2], ['left', -w / 2, 0]]
  let best: BackSide = 'top'
  let bestD = Infinity
  for (const [side, lx, ly] of sides) {
    const p = { x: cx + lx * cos - ly * sin, y: cy + lx * sin + ly * cos }
    const d = walls.reduce((m, wall) => Math.min(m, segDist(p, wall.start, wall.end)), Infinity)
    if (d < bestD - 1e-9) { bestD = d; best = side }
  }
  return best
}

/** Symbol body in a canonical frame: back edge at y = -H/2, front at y = +H/2. */
function body(kind: string, W: number, H: number, S: number, stroke: string): ReactNode {
  const x0 = -W / 2, y0 = -H / 2
  const line = { stroke, strokeWidth: 0.7, fill: 'none' }
  const m = (meters: number) => meters * S
  switch (kind) {
    case 'bed': {
      const head = Math.min(H * 0.08, m(0.1))
      const pillows = W / S >= 1.2 ? 2 : 1
      const gap = W * 0.06
      const pw = (W - gap * (pillows + 1)) / pillows
      const ph = Math.min(H * 0.14, m(0.35))
      return (
        <g {...line}>
          <rect x={x0} y={y0} width={W} height={head} fill={stroke} fillOpacity={0.18} />
          {Array.from({ length: pillows }, (_, i) => (
            <rect key={i} x={x0 + gap + i * (pw + gap)} y={y0 + head + gap * 0.6} width={pw} height={ph} rx={ph * 0.3} />
          ))}
          <path d={`M${x0} ${y0 + H * 0.42} H${-x0}`} />
          <path d={`M${x0} ${y0 + H * 0.42} L${x0 + W * 0.18} ${y0 + H * 0.5} H${-x0}`} opacity={0.6} />
        </g>
      )
    }
    case 'sofa': {
      const back = H * 0.26
      const arm = Math.min(W * 0.12, m(0.22))
      const seats = W / S > 1.8 ? 3 : 2
      const seatW = (W - 2 * arm) / seats
      return (
        <g {...line}>
          <rect x={x0} y={y0} width={W} height={back} rx={back * 0.3} />
          <rect x={x0} y={y0 + back} width={arm} height={H - back} rx={arm * 0.4} />
          <rect x={-x0 - arm} y={y0 + back} width={arm} height={H - back} rx={arm * 0.4} />
          {Array.from({ length: seats - 1 }, (_, i) => (
            <path key={i} d={`M${x0 + arm + seatW * (i + 1)} ${y0 + back} V${-y0}`} />
          ))}
        </g>
      )
    }
    case 'coffee_table': {
      const inset = Math.min(W, H) * 0.12
      return <rect {...line} x={x0 + inset} y={y0 + inset} width={W - 2 * inset} height={H - 2 * inset} rx={inset} />
    }
    case 'dining_table': {
      const chair = m(0.42)
      const depth = Math.min(m(0.32), Math.min(W, H) * 0.22)
      const tx = x0 + depth, ty = y0 + depth
      const tw = W - 2 * depth, th = H - 2 * depth
      const longX = tw >= th
      const along = longX ? tw : th
      const n = Math.max(1, Math.floor(along / m(0.62)))
      const step = along / n
      const chairs: ReactNode[] = []
      for (let i = 0; i < n; i++) {
        const c = (longX ? tx : ty) + step * (i + 0.5)
        if (longX) {
          chairs.push(<rect key={`a${i}`} x={c - chair / 2} y={y0} width={chair} height={depth * 0.85} rx={2} />)
          chairs.push(<rect key={`b${i}`} x={c - chair / 2} y={-y0 - depth * 0.85} width={chair} height={depth * 0.85} rx={2} />)
        } else {
          chairs.push(<rect key={`a${i}`} x={x0} y={c - chair / 2} width={depth * 0.85} height={chair} rx={2} />)
          chairs.push(<rect key={`b${i}`} x={-x0 - depth * 0.85} y={c - chair / 2} width={depth * 0.85} height={chair} rx={2} />)
        }
      }
      return (
        <g {...line}>
          {chairs}
          <rect x={tx} y={ty} width={tw} height={th} fill={PAPER} />
        </g>
      )
    }
    case 'counter':
      return <path {...line} d={`M${x0} ${-y0 - H * 0.16} H${-x0}`} />
    case 'stove': {
      const r = Math.min(W, H) * 0.14
      return (
        <g {...line}>
          {[[-1, -1], [1, -1], [-1, 1], [1, 1]].map(([sx, sy], i) => (
            <circle key={i} cx={sx * W * 0.22} cy={sy * H * 0.2} r={r} />
          ))}
        </g>
      )
    }
    case 'refrigerator':
      return (
        <g {...line}>
          <path d={`M${x0} ${-y0 - H * 0.12} H${-x0}`} />
          <path d={`M${x0} ${y0} L${-x0} ${-y0 - H * 0.12}`} opacity={0.6} />
        </g>
      )
    case 'toilet': {
      const tankH = H * 0.28
      return (
        <g {...line}>
          <rect x={x0 + W * 0.1} y={y0} width={W * 0.8} height={tankH} rx={2} />
          <ellipse cx={0} cy={y0 + tankH + (H - tankH) * 0.48} rx={W * 0.36} ry={(H - tankH) * 0.46} />
        </g>
      )
    }
    case 'lavatory':
      return (
        <g {...line}>
          <ellipse cx={0} cy={H * 0.06} rx={W * 0.34} ry={H * 0.3} />
          <circle cx={0} cy={y0 + H * 0.14} r={Math.max(0.8, Math.min(W, H) * 0.04)} fill={stroke} />
        </g>
      )
    case 'shower':
      return (
        <g {...line}>
          <path d={`M${x0} ${y0} L${-x0} ${-y0} M${-x0} ${y0} L${x0} ${-y0}`} opacity={0.55} />
          <circle cx={0} cy={0} r={Math.max(1, Math.min(W, H) * 0.06)} fill={PAPER} />
        </g>
      )
    case 'wardrobe': {
      const hangers = Math.max(2, Math.floor(W / m(0.25)))
      return (
        <g {...line}>
          <path d={`M${x0 + W * 0.05} 0 H${-x0 - W * 0.05}`} />
          {Array.from({ length: hangers }, (_, i) => {
            const hx = x0 + (W / (hangers + 1)) * (i + 1)
            return <path key={i} d={`M${hx - H * 0.12} ${-H * 0.22} L${hx + H * 0.12} ${H * 0.22}`} opacity={0.6} />
          })}
        </g>
      )
    }
    case 'storage':
      return <path {...line} d={`M${x0} ${y0 + H / 3} H${-x0} M${x0} ${y0 + (2 * H) / 3} H${-x0}`} opacity={0.7} />
    default:
      return <path {...line} d={`M${x0} ${y0} L${-x0} ${-y0}`} opacity={0.5} />
  }
}

function vehicle(w: number, h: number, stroke: string): ReactNode {
  const long = Math.max(w, h), short = Math.min(w, h)
  const L = long * 0.84, Wd = short * 0.72
  const car = (
    <g stroke={stroke} strokeWidth={0.7} fill="none">
      <rect x={-L / 2} y={-Wd / 2} width={L} height={Wd} rx={Wd * 0.28} />
      <path d={`M${L * 0.16} ${-Wd * 0.4} Q${L * 0.24} 0 ${L * 0.16} ${Wd * 0.4}`} />
      <path d={`M${-L * 0.28} ${-Wd * 0.38} Q${-L * 0.34} 0 ${-L * 0.28} ${Wd * 0.38}`} opacity={0.6} />
    </g>
  )
  return w >= h ? car : <g transform="rotate(90)">{car}</g>
}

export function FurnitureSymbol({
  item, ox, oy, S, active, back = 'top',
}: {
  item: Furniture
  ox: number
  oy: number
  S: number
  active: boolean
  back?: BackSide
}) {
  const w = item.dimensions.width * S
  const h = item.dimensions.height * S
  const cx = ox + (item.position.x + item.dimensions.width / 2) * S
  const cy = oy + (item.position.y + item.dimensions.height / 2) * S
  const stroke = active ? ACTIVE : LINE
  const detailed = Math.min(w, h) >= MIN_DETAIL_PX
  const turn = BACK_TURN[back]
  const sideways = turn === 90 || turn === 270
  const outlined = item.kind !== 'vehicle'
  return (
    <g transform={`translate(${cx} ${cy}) rotate(${item.rotation || 0})`}>
      {outlined && (
        <rect
          x={-w / 2}
          y={-h / 2}
          width={w}
          height={h}
          rx={item.kind === 'coffee_table' || item.kind === 'dining_table' ? 0 : Math.min(w, h) * 0.04}
          fill={active ? ACTIVE_PAPER : PAPER}
          stroke={item.kind === 'dining_table' && detailed ? 'none' : stroke}
          strokeWidth={active ? 1.6 : 1}
        />
      )}
      {!outlined && (
        <rect x={-w / 2} y={-h / 2} width={w} height={h} fill="transparent" stroke={active ? ACTIVE : 'none'} strokeWidth={1.6} />
      )}
      {detailed && (item.kind === 'vehicle'
        ? vehicle(w, h, stroke)
        : <g transform={`rotate(${turn})`}>{body(item.kind, sideways ? h : w, sideways ? w : h, S, stroke)}</g>)}
    </g>
  )
}
