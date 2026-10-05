import type { RoomType } from './types'

/** Muted presentation fills by room type, tuned for the light plan paper (#faf9f5) used in both themes. */
export const ROOM_FILL: Record<RoomType, string> = {
  living_room: '#eee5d5',
  dining_room: '#f0e0cb',
  kitchen: '#f2d9c0',
  bedroom: '#e2ead6',
  master_bedroom: '#d9e4cc',
  bathroom: '#d6e4ec',
  toilet: '#dde8ee',
  garage: '#dcdddf',
  laundry: '#e3e5e8',
  storage: '#e6e3dd',
  hallway: '#efede8',
  corridor: '#efede8',
  stairs: '#e6e2ea',
  balcony: '#dfe9dc',
  office: '#e3e0ed',
  utility: '#e1e2e4',
  porch: '#e5e9d6',
  entry: '#ebe4d8',
  other: '#ebe9e4',
}

export function roomFill(type: string | undefined): string {
  return (type && ROOM_FILL[type as RoomType]) || ROOM_FILL.other
}
