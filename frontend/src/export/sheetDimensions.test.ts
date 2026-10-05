import { describe, expect, it } from 'vitest'
import { sheetDimensions } from './sheetDimensions'
import type { SceneDocument, Wall } from '../scene-graph/types'

function wall(id: string, type: Wall['type'], x1: number, y1: number, x2: number, y2: number): Wall {
  return {
    id,
    floorId: 'f',
    type,
    start: { x: x1, y: y1 },
    end: { x: x2, y: y2 },
    thickness: 0.2,
    height: 2.7,
    roomIds: [],
    openingIds: [],
  }
}

describe('sheetDimensions', () => {
  it('returns overall extents and outer jog segments, not one line per room', () => {
    const walls = [
      wall('south', 'exterior', 0, 0, 6, 0),
      wall('east', 'exterior', 6, 0, 6, 4),
      wall('jog', 'exterior', 6, 4, 3, 4),
      wall('stem', 'exterior', 3, 4, 3, 7),
      wall('north', 'exterior', 3, 7, 0, 7),
      wall('west', 'exterior', 0, 7, 0, 0),
      wall('angle', 'exterior', 0, 0, 1, 1),
      wall('partition', 'interior', 3, 0, 3, 4),
    ]
    const scene = {
      walls,
      rooms: [
        { id: 'a', name: 'Living' },
        { id: 'b', name: 'Kitchen' },
        { id: 'c', name: 'Hall' },
      ],
    } as SceneDocument
    const dims = sheetDimensions(scene)
    const overall = dims.filter(dim => dim.role === 'overall')
    const segments = dims.filter(dim => dim.role === 'segment')
    expect(overall.map(dim => dim.lengthM).sort((a, b) => a - b)).toEqual([6, 7])
    expect(segments.map(dim => dim.lengthM).sort((a, b) => a - b)).toEqual([3, 3, 3, 4, 6, 7])
    expect(segments.some(dim => dim.lengthM === 4 && dim.a.x === 3 && dim.b.x === 3)).toBe(false)
    expect(segments.every(dim => dim.a.x === dim.b.x || dim.a.y === dim.b.y)).toBe(true)
    expect(dims.every(dim => Number.isFinite(dim.outward.x) && Number.isFinite(dim.outward.y))).toBe(true)
    expect(dims.length).not.toBe(scene.rooms.length * 2)
  })
})
