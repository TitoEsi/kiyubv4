import type { FloorPlan } from '../../types/floorplan'

/** Irregular generated plan: L-living, angled wall, doors, windows, furniture. */
export const FIDELITY_PLAN: FloorPlan = {
  id: 'fidelity-plan',
  name: 'Fidelity',
  totalWidth: 40,
  totalHeight: 28,
  ceilingHeight: 9,
  rooms: [
    {
      id: 'living',
      name: 'Living Room',
      type: 'living_room',
      x: 0,
      y: 0,
      width: 24,
      height: 18,
      color: '#a8d0bc',
      footprint: {
        type: 'l_shape',
        parts: [
          { x: 0, y: 0, width: 24, height: 10 },
          { x: 0, y: 10, width: 12, height: 8 },
        ],
        centroid: { x: 10, y: 8 },
        boundary: [
          { x1: 0, y1: 0, x2: 24, y2: 0 },
          { x1: 24, y1: 0, x2: 24, y2: 10 },
          { x1: 24, y1: 10, x2: 12, y2: 10 },
          { x1: 12, y1: 10, x2: 12, y2: 18 },
          { x1: 12, y1: 18, x2: 0, y2: 18 },
          { x1: 0, y1: 18, x2: 0, y2: 0 },
        ],
      },
    },
    {
      id: 'kitchen',
      name: 'Kitchen',
      type: 'kitchen',
      x: 12,
      y: 10,
      width: 12,
      height: 8,
      color: '#e2d9a8',
      footprint: {
        type: 'rectangle',
        parts: [{ x: 12, y: 10, width: 12, height: 8 }],
        boundary: [
          { x1: 12, y1: 10, x2: 24, y2: 10 },
          { x1: 24, y1: 10, x2: 24, y2: 18 },
          { x1: 24, y1: 18, x2: 12, y2: 18 },
          { x1: 12, y1: 18, x2: 12, y2: 10 },
        ],
      },
    },
    {
      id: 'bed1',
      name: 'Bedroom 1',
      type: 'bedroom',
      x: 24,
      y: 0,
      width: 16,
      height: 14,
      color: '#c8d4e8',
    },
  ],
  doors: [
    { id: 'd-legacy', x: 12, y: 14, isVertical: true, roomA: 'living', roomB: 'kitchen' },
  ],
  walls: [
    { id: 'w-south', x1: 0, y1: 0, x2: 24, y2: 0, kind: 'exterior', roomIds: ['living'] },
    { id: 'w-east-liv', x1: 24, y1: 0, x2: 24, y2: 10, kind: 'interior', roomIds: ['living', 'bed1'] },
    { id: 'w-jog', x1: 24, y1: 10, x2: 12, y2: 10, kind: 'interior', roomIds: ['living', 'kitchen'] },
    { id: 'w-liv-kit', x1: 12, y1: 10, x2: 12, y2: 18, kind: 'interior', roomIds: ['living', 'kitchen'] },
    { id: 'w-kit-e', x1: 24, y1: 10, x2: 24, y2: 18, kind: 'exterior', roomIds: ['kitchen'] },
    { id: 'w-north-liv', x1: 12, y1: 18, x2: 0, y2: 18, kind: 'exterior', roomIds: ['living'] },
    { id: 'w-west', x1: 0, y1: 18, x2: 0, y2: 0, kind: 'exterior', roomIds: ['living'] },
    { id: 'w-angle', x1: 24, y1: 14, x2: 40, y2: 10, kind: 'exterior', roomIds: ['bed1'] },
    { id: 'w-bed-n', x1: 40, y1: 0, x2: 40, y2: 14, kind: 'exterior', roomIds: ['bed1'] },
    { id: 'w-bed-s', x1: 24, y1: 0, x2: 40, y2: 0, kind: 'exterior', roomIds: ['bed1'] },
  ],
  openings: [
    { id: 'door-entry', wallId: 'w-south', kind: 'door', x: 8, y: 0, width: 3, isVertical: false, roomIds: ['living'] },
    { id: 'win-liv', wallId: 'w-west', kind: 'window', x: 0, y: 8, width: 4, height: 4, isVertical: true, roomIds: ['living'], sillHeight: 3 },
    { id: 'win-bed', wallId: 'w-angle', kind: 'window', x: 32, y: 12, width: 3.5, height: 4, isVertical: false, roomIds: ['bed1'], sillHeight: 3 },
  ],
  furniture: [
    { id: 'sofa-1', roomId: 'living', kind: 'sofa', x: 4, y: 3, width: 7, depth: 3, rotation: 0 },
    { id: 'bed-1', roomId: 'bed1', kind: 'bed', x: 28, y: 3, width: 7, depth: 5, rotation: 90 },
  ],
}
