import type { Furniture, Opening, Wall } from '../scene-graph/types'
import { projectT, wallDir, wallPointAtT } from '../scene-graph/edit/geometry'
import { doorGeometry, openingEnds } from '../scene-graph/edit/door-geometry'

export const openingSpan = openingEnds

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

  if (opening.type === 'garage_door') {
    const depth = 0.25
    const pa = { x: span.a.x + perp.x * depth, y: span.a.y + perp.y * depth }
    const pb = { x: span.b.x + perp.x * depth, y: span.b.y + perp.y * depth }
    const na = { x: span.a.x - perp.x * depth, y: span.a.y - perp.y * depth }
    const nb = { x: span.b.x - perp.x * depth, y: span.b.y - perp.y * depth }
    return (
      <g>
        <line x1={sx(span.a)} y1={sy(span.a)} x2={sx(span.b)} y2={sy(span.b)} stroke={BG} strokeWidth={6} />
        <line x1={sx(span.a)} y1={sy(span.a)} x2={sx(span.b)} y2={sy(span.b)} stroke={stroke} strokeWidth={1.6} />
        <polygon
          points={[pa, pb, nb, na].map(p => `${sx(p)},${sy(p)}`).join(' ')}
          fill="none"
          stroke="#666"
          strokeWidth={1}
          strokeDasharray="4 3"
        />
        {active && <circle cx={sx(opening.position)} cy={sy(opening.position)} r={4} fill="#faf9f5" stroke="#c45c26" strokeWidth={1.5} />}
      </g>
    )
  }

  const g = doorGeometry(opening, wall)
  const r = g.radius * S
  return (
    <g>
      <line x1={sx(span.a)} y1={sy(span.a)} x2={sx(span.b)} y2={sy(span.b)} stroke={BG} strokeWidth={6} />
      <line className="door-leaf" x1={sx(g.hinge)} y1={sy(g.hinge)} x2={sx(g.openEnd)} y2={sy(g.openEnd)} stroke={stroke} strokeWidth={1.6} />
      <path
        className="door-swing"
        d={`M ${sx(g.latch)} ${sy(g.latch)} A ${r} ${r} 0 0 ${g.sweep} ${sx(g.openEnd)} ${sy(g.openEnd)}`}
        fill="none"
        stroke="#666"
        strokeWidth={1}
        strokeDasharray="4 3"
      />
      <circle className="door-hinge" cx={sx(g.hinge)} cy={sy(g.hinge)} r={1.6} fill={stroke} />
      {active && <circle cx={sx(opening.position)} cy={sy(opening.position)} r={4} fill="#faf9f5" stroke="#c45c26" strokeWidth={1.5} />}
    </g>
  )
}

const BG = '#faf9f5'

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
