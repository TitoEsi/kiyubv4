import { sceneRoomRows, sceneSummary, type RoomRow, type SidebarSummary } from '../components/room-rows'
import type { SceneDocument } from '../scene-graph/types'
import { formatArea, formatDimensions, formatMeasurement, type MeasurementUnit } from '../units/measurement'

/** One schedule line. Numbers come from `sceneRoomRows`; labels use the display unit. */
export interface ScheduleLine {
  row: RoomRow
  widthLabel: string
  depthLabel: string
  areaLabel: string
  sizeLabel: string
}

export function roomSchedule(scene: SceneDocument, unit: MeasurementUnit): ScheduleLine[] {
  return sceneRoomRows(scene).map(row => ({
    row,
    widthLabel: formatMeasurement(row.width, unit),
    depthLabel: formatMeasurement(row.depth, unit),
    areaLabel: formatArea(row.area, unit),
    sizeLabel: `${formatDimensions(row.width, row.depth, unit)} · ${formatArea(row.area, unit)}`,
  }))
}

export function scheduleSummary(scene: SceneDocument, unit: MeasurementUnit): {
  summary: SidebarSummary
  rooms: string
  livingArea: string
  footprint: string
  ceiling: string
} {
  const summary = sceneSummary(scene)
  return {
    summary,
    rooms: String(summary.roomCount),
    livingArea: formatArea(summary.livingAreaM2, unit),
    footprint: formatDimensions(summary.footprintW, summary.footprintD, unit),
    ceiling: formatMeasurement(summary.ceilingM, unit),
  }
}
