import { describe, expect, it } from 'vitest'
import { ROOM_FILL, roomFill } from './room-colors'

describe('room colors', () => {
  it('maps every room type to a hex fill', () => {
    for (const [type, color] of Object.entries(ROOM_FILL)) {
      expect(color, type).toMatch(/^#[0-9a-f]{6}$/)
      expect(roomFill(type)).toBe(color)
    }
  })

  it('falls back to the neutral "other" fill for unknown types', () => {
    expect(roomFill('sauna')).toBe(ROOM_FILL.other)
    expect(roomFill(undefined)).toBe(ROOM_FILL.other)
  })
})
