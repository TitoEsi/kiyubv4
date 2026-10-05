import { describe, expect, it } from 'vitest'
import { floorPlanToSceneDocument } from '../scene-graph/adapters/floorplan-to-scene-document'
import { FIDELITY_PLAN } from '../scene-graph/adapters/fidelity.fixture'
import type { SceneDocument } from '../scene-graph/types'
import { formatArea, formatMeasurement } from '../units/measurement'
import { sceneRoomRows } from '../components/room-rows'
import { roomSchedule } from './roomSchedule'

const scene = floorPlanToSceneDocument(FIDELITY_PLAN, { lotWidth: 15, lotDepth: 20, stories: 1 })

describe('roomSchedule', () => {
  it('uses the same rows as the room panel, including a non-rectangular area', () => {
    const first = scene.rooms[0]
    const irregular: SceneDocument = {
      ...scene,
      rooms: scene.rooms.map(room => room.id === first.id
        ? { ...room, name: 'Living', dimensions: { width: 6, height: 4 }, area: 18 }
        : room),
    }
    const rows = sceneRoomRows(irregular)
    const schedule = roomSchedule(irregular, 'm')
    expect(schedule.map(line => line.row)).toEqual(rows)
    expect(schedule[0].row.area).toBe(18)
    expect(schedule[0].row.area).not.toBe(schedule[0].row.width * schedule[0].row.depth)
    expect(schedule[0].widthLabel).toBe(formatMeasurement(rows[0].width, 'm'))
    expect(schedule[0].depthLabel).toBe(formatMeasurement(rows[0].depth, 'm'))
    expect(schedule[0].areaLabel).toBe(formatArea(rows[0].area, 'm'))
    expect(schedule[0].sizeLabel).toContain(formatArea(18, 'm'))
  })
})
