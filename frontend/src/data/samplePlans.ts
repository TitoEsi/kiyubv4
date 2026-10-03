import { FloorPlan } from '../types/floorplan'
import { normalizeFloorPlan } from '../units/legacy'

function room(
  id: string, name: string, type: string,
  x: number, y: number, width: number, height: number, color: string,
) {
  return { id, name, type, x, y, width, height, color }
}

/**
 * Conceptual sample layouts for the public gallery — not live generation output.
 * Authored in feet (no `units` key); exported normalized to meters.
 */
const SAMPLE_PLANS_FT: FloorPlan[] = [
  {
    id: 'sample-a',
    name: 'Courtyard bungalow',
    totalWidth: 48,
    totalHeight: 36,
    ceilingHeight: 9,
    doors: [],
    rooms: [
      room('living-0', 'Living', 'living_room', 2, 2, 20, 16, '#a8d0bc'),
      room('kitchen-0', 'Kitchen', 'kitchen', 22, 2, 14, 12, '#e2d9a8'),
      room('dining-0', 'Dining', 'dining_room', 22, 14, 14, 10, '#d4cfa0'),
      room('bed-0', 'Bedroom', 'bedroom', 2, 20, 14, 14, '#c8d4e8'),
      room('bath-0', 'Bath', 'bathroom', 16, 20, 8, 8, '#a8cfe8'),
      room('patio-0', 'Patio', 'patio', 36, 2, 10, 22, '#98d0a8'),
    ],
  },
  {
    id: 'sample-b',
    name: 'Linear tropical plan',
    totalWidth: 56,
    totalHeight: 28,
    ceilingHeight: 10,
    doors: [],
    rooms: [
      room('foyer-0', 'Foyer', 'foyer', 2, 8, 8, 12, '#d8e0c8'),
      room('living-0', 'Living', 'living_room', 10, 2, 18, 24, '#a8d0bc'),
      room('kitchen-0', 'Kitchen', 'kitchen', 28, 2, 12, 14, '#e2d9a8'),
      room('bed-0', 'Primary', 'master_bedroom', 40, 2, 14, 16, '#e8d4dc'),
      room('bath-0', 'Bath', 'bathroom', 40, 18, 8, 8, '#a8cfe8'),
    ],
  },
  {
    id: 'sample-c',
    name: 'Compact family layout',
    totalWidth: 40,
    totalHeight: 32,
    ceilingHeight: 9,
    doors: [],
    rooms: [
      room('living-0', 'Living', 'living_room', 2, 2, 18, 14, '#a8d0bc'),
      room('kitchen-0', 'Kitchen', 'kitchen', 20, 2, 18, 10, '#e2d9a8'),
      room('bed-0', 'Bedroom 1', 'bedroom', 2, 18, 12, 12, '#c8d4e8'),
      room('bed-1', 'Bedroom 2', 'bedroom', 14, 18, 12, 12, '#c8d4e8'),
      room('bath-0', 'Bath', 'bathroom', 26, 18, 8, 8, '#a8cfe8'),
      room('laundry-0', 'Laundry', 'laundry_room', 34, 18, 4, 8, '#b8d4e8'),
    ],
  },
]

export const SAMPLE_PLANS: FloorPlan[] = SAMPLE_PLANS_FT.map(normalizeFloorPlan)
