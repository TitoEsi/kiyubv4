import { FloorPlan } from '../types/floorplan'

function room(
  id: string, name: string, type: string,
  x: number, y: number, width: number, height: number, color: string,
) {
  return { id, name, type, x, y, width, height, color }
}

function door(x: number, y: number, isVertical: boolean, roomA: string, roomB: string) {
  return { x, y, isVertical, roomA, roomB }
}

export type LandingConcept = {
  id: string
  title: string
  style: string
  description: string
  plan: FloorPlan
  renderImage: string
  floorPlanImage?: string
  isExample: true
}

export const LANDING_CONCEPTS: LandingConcept[] = [
  {
    id: 'modern',
    title: 'Modern Residence',
    style: 'Modern',
    description: 'A linear living wing with a private bedroom suite and a clear garden edge.',
    renderImage: '/landing/concepts/modern-residence.png',
    isExample: true,
    plan: {
      id: 'concept-modern',
      name: 'Modern Residence',
      totalWidth: 52,
      totalHeight: 34,
      ceilingHeight: 10,
      doors: [
        door(12, 18, true, 'living-0', 'hall-0'),
        door(21, 10, false, 'living-0', 'kitchen-0'),
        door(30, 14, true, 'kitchen-0', 'dining-0'),
        door(38, 8, false, 'kitchen-0', 'office-0'),
        door(16, 22, false, 'hall-0', 'bed-0'),
        door(22, 26, true, 'bed-0', 'bath-0'),
        door(26, 24, false, 'bath-0', 'closet-0'),
        door(36, 22, false, 'hall-0', 'powder-0'),
        door(42, 18, true, 'office-0', 'laundry-0'),
      ],
      rooms: [
        room('living-0', 'Living', 'living_room', 2, 2, 20, 16, '#a8d0bc'),
        room('kitchen-0', 'Kitchen', 'kitchen', 22, 2, 16, 12, '#e2d9a8'),
        room('dining-0', 'Dining', 'dining_room', 22, 14, 16, 8, '#d4cfa0'),
        room('office-0', 'Study', 'home_office', 38, 2, 12, 12, '#c4c8e8'),
        room('hall-0', 'Hall', 'hallway', 2, 18, 36, 4, '#d8dce4'),
        room('bed-0', 'Primary', 'master_bedroom', 2, 22, 16, 10, '#e8d4dc'),
        room('bath-0', 'Ensuite', 'ensuite_bathroom', 18, 22, 8, 10, '#a8cfe8'),
        room('closet-0', 'WIC', 'walk_in_closet', 26, 22, 8, 6, '#d8dce8'),
        room('powder-0', 'Powder', 'half_bath', 34, 22, 6, 6, '#b8e0e4'),
        room('laundry-0', 'Laundry', 'laundry_room', 40, 22, 10, 8, '#b8d4e8'),
      ],
    },
  },
  {
    id: 'japandi',
    title: 'Japandi Residence',
    style: 'Japandi',
    description: 'Calm rooms arranged around a south-facing living hall and a compact service core.',
    renderImage: '/landing/concepts/japandi-residence.png',
    isExample: true,
    plan: {
      id: 'concept-japandi',
      name: 'Japandi Residence',
      totalWidth: 46,
      totalHeight: 32,
      ceilingHeight: 9,
      doors: [
        door(10, 15, false, 'foyer-0', 'living-0'),
        door(18, 9, false, 'living-0', 'kitchen-0'),
        door(26, 12, true, 'kitchen-0', 'nook-0'),
        door(10, 20, true, 'living-0', 'hall-0'),
        door(9, 24, false, 'hall-0', 'bed-0'),
        door(16, 24, false, 'hall-0', 'bath-0'),
        door(24, 24, false, 'hall-0', 'closet-0'),
      ],
      rooms: [
        room('foyer-0', 'Foyer', 'foyer', 2, 10, 8, 10, '#d8e0c8'),
        room('living-0', 'Living', 'living_room', 10, 2, 16, 18, '#a8d0bc'),
        room('kitchen-0', 'Kitchen', 'kitchen', 26, 2, 12, 10, '#e2d9a8'),
        room('nook-0', 'Nook', 'nook', 26, 12, 12, 8, '#d0d8c0'),
        room('pantry-0', 'Pantry', 'pantry', 38, 2, 6, 8, '#e0dcc8'),
        room('hall-0', 'Hall', 'hallway', 2, 20, 36, 4, '#d8dce4'),
        room('bed-0', 'Bedroom', 'bedroom', 2, 24, 14, 6, '#c8d4e8'),
        room('bath-0', 'Bath', 'bathroom', 16, 24, 8, 6, '#a8cfe8'),
        room('closet-0', 'Closet', 'closet', 24, 24, 8, 6, '#d8dce8'),
        room('laundry-0', 'Laundry', 'laundry_room', 32, 24, 6, 6, '#b8d4e8'),
      ],
    },
  },
  {
    id: 'contemporary',
    title: 'Open-Plan Contemporary',
    style: 'Contemporary',
    description: 'One shared living volume with bedrooms held to the quieter side of the lot.',
    renderImage: '/landing/concepts/open-plan-contemporary.png',
    isExample: true,
    plan: {
      id: 'concept-contemporary',
      name: 'Open-Plan Contemporary',
      totalWidth: 50,
      totalHeight: 30,
      ceilingHeight: 10,
      doors: [
        door(26, 8, false, 'living-0', 'kitchen-0'),
        door(14, 16, true, 'living-0', 'dining-0'),
        door(28, 14, true, 'living-0', 'hall-0'),
        door(34, 8, false, 'hall-0', 'bed-0'),
        door(42, 8, false, 'bed-0', 'bath-0'),
        door(34, 20, false, 'hall-0', 'bed-1'),
        door(42, 22, false, 'bed-1', 'bath-1'),
      ],
      rooms: [
        room('living-0', 'Great Room', 'great_room', 2, 2, 26, 14, '#a8d0bc'),
        room('kitchen-0', 'Kitchen', 'kitchen', 2, 2, 12, 8, '#e2d9a8'),
        room('dining-0', 'Dining', 'dining_room', 2, 16, 14, 12, '#d4cfa0'),
        room('mud-0', 'Mudroom', 'mudroom', 16, 16, 8, 6, '#d0d4cc'),
        room('laundry-0', 'Laundry', 'laundry_room', 16, 22, 8, 6, '#b8d4e8'),
        room('hall-0', 'Hall', 'hallway', 28, 2, 4, 26, '#d8dce4'),
        room('bed-0', 'Bedroom 1', 'bedroom', 32, 2, 10, 12, '#c8d4e8'),
        room('bath-0', 'Bath', 'bathroom', 42, 2, 6, 8, '#a8cfe8'),
        room('closet-0', 'Closet', 'closet', 42, 10, 6, 4, '#d8dce8'),
        room('bed-1', 'Bedroom 2', 'bedroom', 32, 16, 10, 12, '#c8d4e8'),
        room('bath-1', 'Bath 2', 'bathroom', 42, 16, 6, 8, '#a8cfe8'),
      ],
    },
  },
  {
    id: 'minimalist',
    title: 'Minimalist Residence',
    style: 'Minimalist',
    description: 'A reduced program: living, one bedroom, and a service bar along a single axis.',
    renderImage: '/landing/concepts/minimalist-residence.png',
    isExample: true,
    plan: {
      id: 'concept-minimalist',
      name: 'Minimalist Residence',
      totalWidth: 40,
      totalHeight: 28,
      ceilingHeight: 9,
      doors: [
        door(10, 12, true, 'living-0', 'kitchen-0'),
        door(20, 12, false, 'living-0', 'hall-0'),
        door(26, 8, false, 'hall-0', 'bed-0'),
        door(26, 18, false, 'hall-0', 'bath-0'),
        door(32, 20, false, 'bath-0', 'closet-0'),
      ],
      rooms: [
        room('living-0', 'Living', 'living_room', 2, 2, 18, 24, '#a8d0bc'),
        room('kitchen-0', 'Kitchen', 'kitchen', 2, 2, 8, 10, '#e2d9a8'),
        room('hall-0', 'Hall', 'hallway', 20, 2, 4, 24, '#d8dce4'),
        room('bed-0', 'Bedroom', 'bedroom', 24, 2, 14, 14, '#c8d4e8'),
        room('bath-0', 'Bath', 'bathroom', 24, 16, 8, 10, '#a8cfe8'),
        room('closet-0', 'Closet', 'closet', 32, 16, 6, 6, '#d8dce8'),
        room('laundry-0', 'Laundry', 'laundry_room', 32, 22, 6, 4, '#b8d4e8'),
      ],
    },
  },
  {
    id: 'courtyard',
    title: 'Courtyard Residence',
    style: 'Courtyard',
    description: 'Rooms wrap a planted court so living and sleeping share the same outdoor room.',
    renderImage: '/landing/concepts/courtyard-residence.png',
    isExample: true,
    plan: {
      id: 'concept-courtyard',
      name: 'Courtyard Residence',
      totalWidth: 48,
      totalHeight: 36,
      ceilingHeight: 9,
      doors: [
        door(12, 18, true, 'living-0', 'hall-0'),
        door(21, 10, false, 'living-0', 'kitchen-0'),
        door(29, 14, true, 'kitchen-0', 'dining-0'),
        door(36, 12, false, 'dining-0', 'patio-0'),
        door(9, 22, false, 'hall-0', 'bed-0'),
        door(16, 24, false, 'hall-0', 'bath-0'),
        door(24, 22, false, 'hall-0', 'bed-1'),
      ],
      rooms: [
        room('living-0', 'Living', 'living_room', 2, 2, 20, 16, '#a8d0bc'),
        room('kitchen-0', 'Kitchen', 'kitchen', 22, 2, 14, 12, '#e2d9a8'),
        room('dining-0', 'Dining', 'dining_room', 22, 14, 14, 8, '#d4cfa0'),
        room('patio-0', 'Court', 'patio', 36, 2, 10, 22, '#98d0a8'),
        room('hall-0', 'Hall', 'hallway', 2, 18, 34, 4, '#d8dce4'),
        room('bed-0', 'Bedroom', 'bedroom', 2, 22, 14, 12, '#c8d4e8'),
        room('bath-0', 'Bath', 'bathroom', 16, 22, 8, 8, '#a8cfe8'),
        room('closet-0', 'Closet', 'closet', 16, 30, 8, 4, '#d8dce8'),
        room('bed-1', 'Guest', 'bedroom', 24, 22, 12, 12, '#c8d4e8'),
        room('laundry-0', 'Laundry', 'laundry_room', 36, 24, 10, 6, '#b8d4e8'),
      ],
    },
  },
  {
    id: 'tropical',
    title: 'Tropical Modern Residence',
    style: 'Tropical Modern',
    description: 'A shaded living hall opens to a terrace, with sleeping rooms set behind the service wall.',
    renderImage: '/landing/concepts/tropical-modern.png',
    isExample: true,
    plan: {
      id: 'concept-tropical',
      name: 'Tropical Modern Residence',
      totalWidth: 56,
      totalHeight: 28,
      ceilingHeight: 10,
      doors: [
        door(10, 14, false, 'foyer-0', 'living-0'),
        door(20, 20, true, 'living-0', 'terrace-0'),
        door(28, 8, false, 'living-0', 'kitchen-0'),
        door(36, 14, true, 'kitchen-0', 'hall-0'),
        door(42, 8, false, 'hall-0', 'bed-0'),
        door(44, 18, true, 'bed-0', 'bath-0'),
        door(50, 18, false, 'bath-0', 'closet-0'),
      ],
      rooms: [
        room('foyer-0', 'Foyer', 'foyer', 2, 8, 8, 12, '#d8e0c8'),
        room('living-0', 'Living', 'living_room', 10, 2, 18, 16, '#a8d0bc'),
        room('terrace-0', 'Terrace', 'outdoor_living', 10, 18, 18, 8, '#98d0a8'),
        room('kitchen-0', 'Kitchen', 'kitchen', 28, 2, 10, 16, '#e2d9a8'),
        room('pantry-0', 'Pantry', 'pantry', 28, 18, 6, 8, '#e0dcc8'),
        room('laundry-0', 'Laundry', 'laundry_room', 34, 18, 6, 8, '#b8d4e8'),
        room('hall-0', 'Hall', 'hallway', 38, 2, 4, 24, '#d8dce4'),
        room('bed-0', 'Primary', 'master_bedroom', 42, 2, 12, 14, '#e8d4dc'),
        room('bath-0', 'Bath', 'bathroom', 42, 16, 8, 10, '#a8cfe8'),
        room('closet-0', 'WIC', 'walk_in_closet', 50, 16, 4, 10, '#d8dce8'),
      ],
    },
  },
]
