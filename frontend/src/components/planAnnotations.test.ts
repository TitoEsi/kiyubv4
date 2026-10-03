import { describe, expect, it } from 'vitest'
import { FloorPlan } from '../types/floorplan'
import {
  annotationPoint,
  clientCommentCountLabel,
  commentRoleLabel,
  pinTargetLabel,
} from './planAnnotations'

const plan = {
  id: 'p1',
  name: 'House',
  rooms: [
    { id: 'living', name: 'Bedroom 2', type: 'bedroom', x: 0, y: 0, width: 12, height: 10, color: '#fff' },
  ],
  walls: [],
  doors: [],
  ceilingHeight: 9,
  totalWidth: 12,
  totalHeight: 10,
} as FloorPlan

describe('planAnnotations', () => {
  it('uses stored plan-meter coordinates', () => {
    expect(annotationPoint({ id: '1', body: 'Move door', author_id: 'c1', created_at: null, x: 4, y: 6, object_id: 'living' }, plan))
      .toEqual({ x: 4, y: 6 })
  })

  it('falls back to room centroid when only object_id is set', () => {
    expect(annotationPoint({ id: '1', body: 'Note', author_id: 'c1', created_at: null, object_id: 'living' }, plan))
      .toEqual({ x: 6, y: 5 })
  })

  it('labels author role from persisted role, not viewer', () => {
    expect(commentRoleLabel('CLIENT')).toBe('Client comment')
    expect(commentRoleLabel('ARCHITECT')).toBe('Architect comment')
  })

  it('names the pinned room', () => {
    expect(pinTargetLabel(plan, 'living')).toBe('Bedroom 2')
  })

  it('formats a quiet client-comment count', () => {
    expect(clientCommentCountLabel(3, true)).toBe('3 client comments')
    expect(clientCommentCountLabel(0, true)).toBe('No client comments')
    expect(clientCommentCountLabel(0, false)).toBeNull()
  })
})
