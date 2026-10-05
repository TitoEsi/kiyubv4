import { describe, expect, it } from 'vitest'
import { layoutRoomLabel, roomLabelText, sheetRoomLabel, sheetRoomName } from './room-labels'
import type { Room, RoomType } from './types'

function room(name: string, type: RoomType, w: number, h: number, polygon?: Room['polygon']): Room {
  return {
    id: `r-${name}`,
    floorId: 'f1',
    name,
    type,
    polygon,
    position: { x: 0, y: 0 },
    dimensions: { width: w, height: h },
  } as Room
}

function inside(pts: Array<{ x: number; y: number }>, p: { x: number; y: number }) {
  let hit = false
  for (let i = 0, j = pts.length - 1; i < pts.length; j = i++) {
    const a = pts[i], b = pts[j]
    if ((a.y > p.y) !== (b.y > p.y) && p.x < ((b.x - a.x) * (p.y - a.y)) / (b.y - a.y) + a.x) hit = !hit
  }
  return hit
}

describe('roomLabelText', () => {
  it('uppercases human names', () => {
    expect(roomLabelText({ name: 'Primary Bedroom', type: 'master_bedroom' })).toBe('PRIMARY BEDROOM')
  })

  it.each(['bed1', 'living_room', 'kitchen-2', ''])('falls back to the type for "%s"', name => {
    expect(roomLabelText({ name, type: 'living_room' })).toBe('LIVING ROOM')
  })
})

describe('layoutRoomLabel', () => {
  it('uses one line at full size in a roomy space', () => {
    const l = layoutRoomLabel(room('Kitchen', 'kitchen', 5, 4), 40, 0, 0)!
    expect(l.lines).toEqual(['KITCHEN'])
    expect(l.fontSize).toBe(12)
    expect(l.x).toBeCloseTo(100)
    expect(l.y).toBeCloseTo(80)
  })

  it('wraps a long name in a narrow room', () => {
    const l = layoutRoomLabel(room('Primary Bedroom Suite', 'master_bedroom', 2.6, 4), 40, 0, 0)!
    expect(l.lines.length).toBeGreaterThanOrEqual(2)
    expect(l.lines.join(' ')).toBe('PRIMARY BEDROOM SUITE')
  })

  it('shrinks the font in a small room but not below the minimum', () => {
    const l = layoutRoomLabel(room('Laundry', 'laundry', 1.2, 1.2), 40, 0, 0)!
    expect(l.fontSize).toBeLessThan(12)
    expect(l.fontSize).toBeGreaterThanOrEqual(7.5)
  })

  it('abbreviates or drops the label in a tiny room', () => {
    const tiny = layoutRoomLabel(room('Bathroom', 'bathroom', 0.9, 0.6), 30, 0, 0)
    expect(tiny === null || tiny.lines.join(' ') === 'BATH').toBe(true)
    expect(layoutRoomLabel(room('Bathroom', 'bathroom', 0.2, 0.2), 30, 0, 0)).toBeNull()
  })

  it('keeps the anchor inside an L-shaped room', () => {
    const L = [
      { x: 0, y: 0 }, { x: 6, y: 0 }, { x: 6, y: 1.5 }, { x: 1.5, y: 1.5 }, { x: 1.5, y: 6 }, { x: 0, y: 6 },
    ]
    const S = 40
    const l = layoutRoomLabel(room('Living', 'living_room', 6, 6, L), S, 0, 0)!
    expect(l).not.toBeNull()
    expect(inside(L, { x: l.x / S, y: l.y / S })).toBe(true)
  })

  it('moves off a centred furniture piece when there is room', () => {
    const S = 40
    const r = room('Living', 'living_room', 8, 3)
    const free = layoutRoomLabel(r, S, 0, 0)!
    const sofa = { x: 3.2, y: 1, width: 1.6, height: 1 }
    const l = layoutRoomLabel(r, S, 0, 0, [sofa])!
    expect(free.x).toBeCloseTo(160)
    expect(Math.abs(l.x - 160)).toBeGreaterThan(40)
  })
})

describe('sheetRoomLabel', () => {
  it('keeps the sidebar name, uppercased, even when the canvas would drop it', () => {
    const tiny = room('Powder Room', 'bathroom', 0.2, 0.2)
    expect(layoutRoomLabel(tiny, 30, 0, 0)).toBeNull()
    const sheet = sheetRoomLabel(tiny, 'Powder Room', 30, 0, 0)
    expect(sheet.lines.join(' ')).toBe('POWDER ROOM')
    expect(sheet.fontSize).toBeGreaterThanOrEqual(8)
    expect(sheet.fontSize).toBeLessThanOrEqual(13)
  })

  it('does not abbreviate a name the canvas shortens', () => {
    expect(sheetRoomName('Bathroom')).toBe('BATHROOM')
    const sheet = sheetRoomLabel(room('Bathroom', 'bathroom', 1.2, 1.2), 'Bathroom', 40, 0, 0)
    expect(sheet.lines.join(' ')).toBe('BATHROOM')
  })
})
