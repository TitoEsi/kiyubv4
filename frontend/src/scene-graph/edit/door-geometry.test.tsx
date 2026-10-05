import { describe, expect, it } from 'vitest'
import { renderToStaticMarkup } from 'react-dom/server'
import type { FloorPlan } from '../../types/floorplan'
import type { Opening, Point2D, Room, RoomType, SceneDocument, Wall } from '../types'
import { deriveDoorSwing, doorGeometry, doorSwing, normalizeDoorSwings, type DoorHinge, type DoorSwingSide } from './door-geometry'
import { createOpening, flipDoorHinge, flipDoorSwing, moveOpening, rotateOpening, syncOpeningsToWalls } from './opening-ops'
import { moveEndpoint, moveWall } from './wall-ops'
import { floorPlanToSceneDocument } from '../adapters/floorplan-to-scene-document'
import { sceneDocumentToFloorPlan } from '../adapters/scene-document-to-floorplan'
import { loadLiveScene } from './load-scene'
import { OpeningSymbol } from '../../components/opening-symbols'

const close = (a: Point2D, b: Point2D, eps = 1e-6) => Math.hypot(a.x - b.x, a.y - b.y) < eps

/** Centre of the SVG arc `M p1 A r r 0 large sweep p2` (SVG 1.1 F.6.5, rx = ry, no rotation). */
function svgArcCentre(p1: Point2D, p2: Point2D, r: number, large: 0 | 1, sweep: 0 | 1): Point2D {
  const x1 = (p1.x - p2.x) / 2, y1 = (p1.y - p2.y) / 2
  const k = Math.sqrt(Math.max(0, (r * r - x1 * x1 - y1 * y1) / (x1 * x1 + y1 * y1)))
  const sign = large === sweep ? -1 : 1
  return { x: sign * k * y1 + (p1.x + p2.x) / 2, y: -sign * k * x1 + (p1.y + p2.y) / 2 }
}

function wall(id: string, start: Point2D, end: Point2D, roomIds: string[] = []): Wall {
  return { id, floorId: 'f1', type: 'interior', start, end, thickness: 0.15, height: 2.7, roomIds, openingIds: [] } as Wall
}

function door(w: Wall, t: number, hinge?: DoorHinge | 'left' | 'right', swingSide?: DoorSwingSide, width = 0.9): Opening {
  const metadata: Record<string, unknown> = { t }
  if (hinge) metadata.hinge = hinge
  if (swingSide) metadata.swingSide = swingSide
  return {
    id: 'd1', floorId: 'f1', wallId: w.id, type: 'door',
    position: { x: w.start.x + (w.end.x - w.start.x) * t, y: w.start.y + (w.end.y - w.start.y) * t },
    width, height: 2.1, sillHeight: 0, metadata,
  }
}

function room(id: string, type: RoomType, x: number, y: number, w: number, h: number): Room {
  return {
    id, floorId: 'f1', name: id, type,
    polygon: [{ x, y }, { x: x + w, y }, { x: x + w, y: y + h }, { x, y: y + h }],
    position: { x, y }, dimensions: { width: w, height: h }, area: w * h,
    wallIds: [], openingIds: [],
  } as unknown as Room
}

const WALLS: Array<[string, Wall]> = [
  ['horizontal', wall('h', { x: 0, y: 0 }, { x: 4, y: 0 })],
  ['reversed horizontal', wall('hr', { x: 4, y: 0 }, { x: 0, y: 0 })],
  ['vertical', wall('v', { x: 0, y: 0 }, { x: 0, y: 4 })],
  ['reversed vertical', wall('vr', { x: 0, y: 4 }, { x: 0, y: 0 })],
  ['angled', wall('a', { x: 0, y: 0 }, { x: 3, y: 2 })],
]

describe('doorGeometry', () => {
  for (const [label, w] of WALLS) {
    for (const hinge of ['start', 'end'] as const) {
      for (const side of [1, -1] as const) {
        it(`arc is a quarter circle on the hinge (${label}, ${hinge}, ${side})`, () => {
          const g = doorGeometry(door(w, 0.5, hinge, side), w)
          expect(g.radius).toBeCloseTo(0.9, 6)
          expect(Math.hypot(g.openEnd.x - g.hinge.x, g.openEnd.y - g.hinge.y)).toBeCloseTo(0.9, 6)
          const c = { x: g.latch.x - g.hinge.x, y: g.latch.y - g.hinge.y }
          const o = { x: g.openEnd.x - g.hinge.x, y: g.openEnd.y - g.hinge.y }
          expect(c.x * o.x + c.y * o.y).toBeCloseTo(0, 6)
          expect(close(svgArcCentre(g.latch, g.openEnd, g.radius, 0, g.sweep), g.hinge)).toBe(true)
        })
      }
    }
  }

  it('documents the old renderer bug: inverted sweep centres the arc on the far corner', () => {
    expect(close(svgArcCentre({ x: 0, y: 1 }, { x: 1, y: 0 }, 1, 0, 1), { x: 1, y: 1 })).toBe(true)
  })

  it('reads legacy left/right hinges', () => {
    const w = WALLS[0][1]
    expect(doorSwing(door(w, 0.5, 'left')).hinge).toBe('start')
    expect(doorSwing(door(w, 0.5, 'right')).hinge).toBe('end')
  })

  it('opens to the configured side of the wall', () => {
    const w = WALLS[0][1]
    expect(doorGeometry(door(w, 0.5, 'start', 1), w).openEnd.y).toBeGreaterThan(0)
    expect(doorGeometry(door(w, 0.5, 'start', -1), w).openEnd.y).toBeLessThan(0)
  })
})

describe('deriveDoorSwing', () => {
  const shared = wall('s', { x: 0, y: 3 }, { x: 6, y: 3 })
  const hall = room('hall', 'hallway', 0, 3, 6, 1.2)
  const bed = room('bed', 'bedroom', 0, 0, 6, 3)

  it.each([0.2, 0.8])('interior door opens into the bedroom, not the hallway (t=%s)', t => {
    const d = door(shared, t)
    const s = deriveDoorSwing(d, shared, [hall, bed])
    expect(doorGeometry({ ...d, metadata: { ...d.metadata, ...s } }, shared).openEnd.y).toBeLessThan(3)
    expect(s.hinge).toBe(t < 0.5 ? 'start' : 'end')
  })

  it('between two rooms opens into the smaller one', () => {
    const big = room('living', 'living_room', 0, 3, 6, 5)
    const bath = room('bath', 'bathroom', 0, 1, 6, 2)
    const d = door(shared, 0.5)
    const s = deriveDoorSwing(d, shared, [big, bath])
    expect(doorGeometry({ ...d, metadata: { ...d.metadata, ...s } }, shared).openEnd.y).toBeLessThan(3)
  })

  it('exterior door opens inward, and flipping swings it outward on either hinge', () => {
    const ext = wall('e', { x: 0, y: 0 }, { x: 6, y: 0 })
    const living = room('living', 'living_room', 0, 0, 6, 4)
    let scene = {
      ...floorPlanToSceneDocument({ id: 'p', name: 'p', totalWidth: 6, totalHeight: 4, ceilingHeight: 2.7, rooms: [], doors: [], units: 'metric' } as unknown as FloorPlan, { lotWidth: 10, lotDepth: 10 }),
      walls: [ext], rooms: [living], openings: [],
    } as SceneDocument
    scene = createOpening(scene, 'e', 'door', 0.3)
    const id = scene.openings[0].id
    const geo = (s: SceneDocument) => doorGeometry(s.openings[0], s.walls[0])
    expect(geo(scene).openEnd.y).toBeGreaterThan(0)
    const out = flipDoorSwing(scene, id)
    expect(geo(out).openEnd.y).toBeLessThan(0)
    const outOther = flipDoorHinge(out, id)
    expect(geo(outOther).openEnd.y).toBeLessThan(0)
    expect(close(geo(outOther).hinge, geo(out).latch)).toBe(true)
  })
})

describe('door edits keep the symbol attached', () => {
  function sceneWithDoor() {
    const plan = {
      id: 'p', name: 'p', totalWidth: 20, totalHeight: 15, ceilingHeight: 9,
      rooms: [{ id: 'living', name: 'Living', type: 'living_room', x: 2, y: 2, width: 16, height: 10, color: '#ccc' }],
      doors: [],
    } as FloorPlan
    let s = loadLiveScene(plan, { lotWidth: 20, lotDepth: 20 })
    s = createOpening(s, s.walls[0].id, 'door', 0.5)
    return s
  }
  const geo = (s: SceneDocument) => {
    const o = s.openings[0]
    return doorGeometry(o, s.walls.find(w => w.id === o.wallId)!)
  }
  const onWall = (s: SceneDocument, p: Point2D) => {
    const o = s.openings[0]
    const w = s.walls.find(x => x.id === o.wallId)!
    const dx = w.end.x - w.start.x, dy = w.end.y - w.start.y
    return Math.abs((p.x - w.start.x) * dy - (p.y - w.start.y) * dx) / Math.hypot(dx, dy) < 1e-6
  }

  it('rotate cycles all four quadrants and returns', () => {
    let s = sceneWithDoor()
    const id = s.openings[0].id
    const seen = new Set<string>()
    for (let i = 0; i < 4; i++) {
      const { hinge, swingSide } = doorSwing(s.openings[0])
      seen.add(`${hinge}${swingSide}`)
      s = rotateOpening(s, id)
    }
    expect(seen.size).toBe(4)
  })

  it('stays on the wall when moved along it, or when the wall or its end moves', () => {
    let s = sceneWithDoor()
    const id = s.openings[0].id
    s = moveOpening(s, id, 0.3)
    expect(onWall(s, geo(s).hinge)).toBe(true)
    expect(onWall(s, geo(s).latch)).toBe(true)
    const w = s.walls.find(x => x.id === s.openings[0].wallId)!
    s = moveWall(s, w.id, { x: 0, y: 0.4 })
    expect(onWall(s, geo(s).hinge)).toBe(true)
    s = moveEndpoint(s, w.id, 'end', { x: w.end.x + 1, y: w.end.y + 0.4 })
    expect(onWall(s, geo(s).hinge)).toBe(true)
    expect(geo(s).radius).toBeCloseTo(s.openings[0].width, 6)
  })

  it('keeps its world opening direction when re-hosted on a reversed wall', () => {
    const a = wall('a', { x: 0, y: 0 }, { x: 4, y: 0 })
    const b = wall('b', { x: 4, y: 0.01 }, { x: 0, y: 0.01 })
    const shortA = { ...a, end: { x: 0.01, y: 0 } }
    const base = {
      ...floorPlanToSceneDocument({ id: 'p', name: 'p', totalWidth: 6, totalHeight: 4, ceilingHeight: 2.7, rooms: [], doors: [], units: 'metric' } as unknown as FloorPlan, { lotWidth: 10, lotDepth: 10 }),
      walls: [a, b], rooms: [],
    } as SceneDocument
    const d = { ...door(a, 0.25, 'start', 1) }
    const before = doorGeometry(d, a)
    const after = syncOpeningsToWalls({ ...base, walls: [shortA, b], openings: [d] })
    const g = doorGeometry(after.openings[0], b)
    expect(after.openings[0].wallId).toBe('b')
    expect(Math.sign(g.openEnd.y - g.hinge.y)).toBe(Math.sign(before.openEnd.y - before.hinge.y))
    expect(g.hinge.x).toBeLessThan(g.latch.x)
  })
})

describe('door data compatibility', () => {
  const ORTOOLS: FloorPlan = {
    id: 'o', name: 'o', totalWidth: 6, totalHeight: 6, ceilingHeight: 2.7, units: 'metric',
    generator: 'ortools',
    rooms: [
      { id: 'bed', name: 'Bedroom', type: 'bedroom', x: 0, y: 0, width: 6, height: 3, color: '#ccc' },
      { id: 'hall', name: 'Hall', type: 'hallway', x: 0, y: 3, width: 6, height: 1.2, color: '#ccc' },
    ],
    doors: [{ id: 'd0', x: 2, y: 3, isVertical: false, roomA: 'bed', roomB: 'hall' }],
    walls: [{ id: 'w', x1: 0, y1: 3, x2: 6, y2: 3, kind: 'interior', roomIds: ['bed', 'hall'] }],
    openings: [{ id: 'd0', wallId: 'w', kind: 'door', x: 2, y: 3, width: 0.9, isVertical: false, roomIds: ['bed', 'hall'] }],
  } as unknown as FloorPlan

  it('centres OR-tools openings on their true span and derives a swing', () => {
    const s = floorPlanToSceneDocument(ORTOOLS, { lotWidth: 10, lotDepth: 10 })
    const o = s.openings[0]
    expect(o.position.x).toBeCloseTo(2.45, 6)
    expect(o.metadata?.swingSide === 1 || o.metadata?.swingSide === -1).toBe(true)
    expect(doorGeometry(o, s.walls[0]).openEnd.y).toBeLessThan(3)
  })

  it('leaves midpoint-anchored (MOE) doors where they are', () => {
    const { generator: _g, openings: _o, ...rest } = ORTOOLS as FloorPlan & { generator?: string }
    const s = floorPlanToSceneDocument({ ...rest, doors: [{ id: 'd0', x: 2, y: 3, isVertical: false, roomA: 'bed', roomB: 'hall', wallId: 'w' }] } as FloorPlan, { lotWidth: 10, lotDepth: 10 })
    expect(s.openings[0].position.x).toBeCloseTo(2, 6)
  })

  it('normalises a saved pre-fix scene deterministically and re-centres only untouched engine doors', () => {
    const fresh = floorPlanToSceneDocument(ORTOOLS, { lotWidth: 10, lotDepth: 10 })
    const legacy = (x: number): SceneDocument => ({
      ...fresh,
      openings: fresh.openings.map(o => ({ ...o, position: { x, y: 3 }, metadata: { ...o.metadata, t: x / 6, hinge: 'left', swingSide: undefined } })),
    })
    const untouched = loadLiveScene(ORTOOLS, { lotWidth: 10, lotDepth: 10 }, { existing: legacy(2) })
    expect(untouched.openings[0].position.x).toBeCloseTo(2.45, 6)
    const again = loadLiveScene(ORTOOLS, { lotWidth: 10, lotDepth: 10 }, { existing: untouched })
    expect(again.openings[0].metadata).toEqual(untouched.openings[0].metadata)
    const moved = loadLiveScene(ORTOOLS, { lotWidth: 10, lotDepth: 10 }, { existing: legacy(4) })
    expect(moved.openings[0].position.x).toBeCloseTo(4, 6)
    expect(moved.openings[0].metadata?.swingSide === 1 || moved.openings[0].metadata?.swingSide === -1).toBe(true)
  })

  it('keeps a user-flipped legacy right hinge', () => {
    const fresh = floorPlanToSceneDocument(ORTOOLS, { lotWidth: 10, lotDepth: 10 })
    const s = normalizeDoorSwings({ ...fresh, openings: fresh.openings.map(o => ({ ...o, metadata: { ...o.metadata, hinge: 'right', swingSide: undefined } })) })
    expect(s.openings[0].metadata?.hinge).toBe('end')
  })

  it('round-trips hinge, swing and position through the saved floor plan', () => {
    let s = floorPlanToSceneDocument(ORTOOLS, { lotWidth: 10, lotDepth: 10 })
    s = flipDoorSwing(flipDoorHinge(s, 'd0'), 'd0')
    const back = floorPlanToSceneDocument(sceneDocumentToFloorPlan(s), { lotWidth: 10, lotDepth: 10 })
    const a = s.openings[0], b = back.openings[0]
    expect(b.metadata?.hinge).toBe(a.metadata?.hinge)
    expect(b.metadata?.swingSide).toBe(a.metadata?.swingSide)
    expect(b.position.x).toBeCloseTo(a.position.x, 6)
  })
})

describe('OpeningSymbol door', () => {
  it('draws the arc from the latch to the open end, centred on the hinge', () => {
    const w = WALLS[0][1]
    const d = door(w, 0.5, 'end', -1)
    const g = doorGeometry(d, w)
    const S = 50
    const html = renderToStaticMarkup(<svg><OpeningSymbol opening={d} wall={w} ox={0} oy={0} S={S} active={false} /></svg>)
    const m = html.match(/class="door-swing" d="M ([-\d.]+) ([-\d.]+) A ([\d.]+) [\d.]+ 0 0 ([01]) ([-\d.]+) ([-\d.]+)"/)!
    expect(m).not.toBeNull()
    const [p1, p2] = [{ x: +m[1], y: +m[2] }, { x: +m[5], y: +m[6] }]
    expect(close(p1, { x: g.latch.x * S, y: g.latch.y * S }, 1e-3)).toBe(true)
    expect(close(p2, { x: g.openEnd.x * S, y: g.openEnd.y * S }, 1e-3)).toBe(true)
    const c = svgArcCentre(p1, p2, +m[3], 0, +m[4] as 0 | 1)
    expect(close(c, { x: g.hinge.x * S, y: g.hinge.y * S }, 1e-3)).toBe(true)
    expect(html).toMatch(/class="door-hinge" cx="[-\d.]+" cy="[-\d.]+"/)
  })
})
