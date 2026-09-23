import type { Furniture, Opening, Wall } from '../scene-graph/types'
import { projectT, wallDir, wallLength, wallPointAtT } from '../scene-graph/edit/geometry'
import { openingT } from '../scene-graph/edit/opening-ops'

export function openingSpan(opening: Opening, wall: Wall): { t0: number; t1: number; a: { x: number; y: number }; b: { x: number; y: number } } {
  const len = Math.max(wallLength(wall), 1e-6)
  const t = openingT(opening, wall)
  const half = (opening.width / 2) / len
  const t0 = Math.max(0, t - half)
  const t1 = Math.min(1, t + half)
  return { t0, t1, a: wallPointAtT(wall, t0), b: wallPointAtT(wall, t1) }
}

export function wallStrokeSegments(wall: Wall, openings: Opening[]): Array<{ a: { x: number; y: number }; b: { x: number; y: number } }> {
  const mine = openings.filter(o => o.wallId === wall.id).map(o => openingSpan(o, wall)).sort((x, y) => x.t0 - y.t0)
  const segs: Array<{ a: { x: number; y: number }; b: { x: number; y: number } }> = []
  let cursor = 0
  for (const span of mine) {
    if (span.t0 > cursor + 0.01) {
      segs.push({ a: wallPointAtT(wall, cursor), b: wallPointAtT(wall, span.t0) })
    }
    cursor = Math.max(cursor, span.t1)
  }
  if (cursor < 0.99) segs.push({ a: wallPointAtT(wall, cursor), b: { ...wall.end } })
  return segs.length ? segs : [{ a: { ...wall.start }, b: { ...wall.end } }]
}

export function OpeningSymbol({
  opening, wall, ox, oy, S, active,
}: {
  opening: Opening
  wall: Wall
  ox: number
  oy: number
  S: number
  active: boolean
}) {
  const sx = (p: { x: number; y: number }) => ox + p.x * S
  const sy = (p: { x: number; y: number }) => oy + p.y * S
  const span = openingSpan(opening, wall)
  const dir = wallDir(wall)
  const perp = { x: -dir.y, y: dir.x }
  const hingeRight = opening.metadata?.hinge === 'right'
  const hinge = hingeRight ? span.b : span.a
  const leaf = {
    x: hinge.x + perp.x * opening.width,
    y: hinge.y + perp.y * opening.width,
  }
  const closed = hingeRight ? span.a : span.b
  const sweep = hingeRight ? 0 : 1
  const stroke = active ? '#c45c26' : '#17191c'
  const isWindow = opening.type === 'window'
  const sliding = opening.type === 'sliding_door'

  if (isWindow) {
    const o1 = { x: span.a.x + perp.x * 0.04, y: span.a.y + perp.y * 0.04 }
    const o2 = { x: span.b.x + perp.x * 0.04, y: span.b.y + perp.y * 0.04 }
    const i1 = { x: span.a.x - perp.x * 0.04, y: span.a.y - perp.y * 0.04 }
    const i2 = { x: span.b.x - perp.x * 0.04, y: span.b.y - perp.y * 0.04 }
    const midA = { x: (span.a.x + span.b.x) / 2, y: (span.a.y + span.b.y) / 2 }
    const midO = { x: midA.x + perp.x * 0.04, y: midA.y + perp.y * 0.04 }
    const midI = { x: midA.x - perp.x * 0.04, y: midA.y - perp.y * 0.04 }
    return (
      <g>
        <line x1={sx(span.a)} y1={sy(span.a)} x2={sx(span.b)} y2={sy(span.b)} stroke={BG} strokeWidth={6} />
        <line x1={sx(o1)} y1={sy(o1)} x2={sx(o2)} y2={sy(o2)} stroke={stroke} strokeWidth={1.4} />
        <line x1={sx(i1)} y1={sy(i1)} x2={sx(i2)} y2={sy(i2)} stroke={stroke} strokeWidth={1.4} />
        <line x1={sx(midO)} y1={sy(midO)} x2={sx(midI)} y2={sy(midI)} stroke={stroke} strokeWidth={1} />
        {active && <circle cx={sx(midA)} cy={sy(midA)} r={4} fill="#faf9f5" stroke="#c45c26" strokeWidth={1.5} />}
      </g>
    )
  }

  if (sliding) {
    return (
      <g>
        <line x1={sx(span.a)} y1={sy(span.a)} x2={sx(span.b)} y2={sy(span.b)} stroke={BG} strokeWidth={6} />
        <line x1={sx(span.a)} y1={sy(span.a)} x2={sx(span.b)} y2={sy(span.b)} stroke={stroke} strokeWidth={1.6} />
        <line
          x1={sx({ x: span.a.x + perp.x * 0.06, y: span.a.y + perp.y * 0.06 })}
          y1={sy({ x: span.a.x + perp.x * 0.06, y: span.a.y + perp.y * 0.06 })}
          x2={sx({ x: span.b.x + perp.x * 0.06, y: span.b.y + perp.y * 0.06 })}
          y2={sy({ x: span.b.x + perp.x * 0.06, y: span.b.y + perp.y * 0.06 })}
          stroke={stroke}
          strokeWidth={1.2}
        />
        {active && <circle cx={sx(opening.position)} cy={sy(opening.position)} r={4} fill="#faf9f5" stroke="#c45c26" strokeWidth={1.5} />}
      </g>
    )
  }

  const r = opening.width * S
  return (
    <g>
      <line x1={sx(span.a)} y1={sy(span.a)} x2={sx(span.b)} y2={sy(span.b)} stroke={BG} strokeWidth={6} />
      <line x1={sx(hinge)} y1={sy(hinge)} x2={sx(leaf)} y2={sy(leaf)} stroke={stroke} strokeWidth={1.6} />
      <path
        d={`M ${sx(leaf)} ${sy(leaf)} A ${r} ${r} 0 0 ${sweep} ${sx(closed)} ${sy(closed)}`}
        fill="none"
        stroke="#666"
        strokeWidth={1}
        strokeDasharray="4 3"
      />
      {active && <circle cx={sx(opening.position)} cy={sy(opening.position)} r={4} fill="#faf9f5" stroke="#c45c26" strokeWidth={1.5} />}
    </g>
  )
}

const BG = '#faf9f5'

export function FurnitureSymbol({
  item, ox, oy, S, active,
}: {
  item: Furniture
  ox: number
  oy: number
  S: number
  active: boolean
}) {
  const w = item.dimensions.width * S
  const h = item.dimensions.height * S
  const cx = ox + (item.position.x + item.dimensions.width / 2) * S
  const cy = oy + (item.position.y + item.dimensions.height / 2) * S
  const rot = item.rotation || 0
  return (
    <g transform={`translate(${cx} ${cy}) rotate(${rot})`}>
      <rect
        x={-w / 2}
        y={-h / 2}
        width={w}
        height={h}
        fill={active ? '#efe6dc' : '#f7f4ef'}
        stroke={active ? '#c45c26' : '#8a8680'}
        strokeWidth={active ? 1.6 : 1}
      />
      <text textAnchor="middle" y={3} fontSize={Math.max(7, Math.min(10, w / 6))} fill="#555">{item.kind}</text>
    </g>
  )
}

export function openingContains(opening: Opening, wall: Wall, p: { x: number; y: number }): boolean {
  const span = openingSpan(opening, wall)
  const t = projectT(wall, p)
  const on = wallPointAtT(wall, t)
  const distToWall = Math.hypot(on.x - p.x, on.y - p.y)
  return t >= span.t0 - 0.02 && t <= span.t1 + 0.02 && distToWall < 0.35
}

export function furnitureContains(item: Furniture, p: { x: number; y: number }): boolean {
  const ang = -((item.rotation || 0) * Math.PI) / 180
  const cx = item.position.x + item.dimensions.width / 2
  const cy = item.position.y + item.dimensions.height / 2
  const dx = p.x - cx
  const dy = p.y - cy
  const lx = dx * Math.cos(ang) - dy * Math.sin(ang)
  const ly = dx * Math.sin(ang) + dy * Math.cos(ang)
  return Math.abs(lx) <= item.dimensions.width / 2 && Math.abs(ly) <= item.dimensions.height / 2
}
