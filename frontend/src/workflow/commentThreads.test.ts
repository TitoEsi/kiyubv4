import { describe, expect, it } from 'vitest'
import type { Comment } from './api'
import { buildThreads, formatStamp, roleName, splitThreads } from './commentThreads'

const c = (id: string, created_at: string, extra: Partial<Comment> = {}): Comment => ({
  id, body: id, author_id: 'u', created_at, ...extra,
})

describe('buildThreads', () => {
  it('nests replies under their top-level comment, both oldest first', () => {
    const threads = buildThreads([
      c('b', '2026-10-05T02:00:00Z'),
      c('r2', '2026-10-05T04:00:00Z', { parent_id: 'a' }),
      c('a', '2026-10-05T01:00:00Z'),
      c('r1', '2026-10-05T03:00:00Z', { parent_id: 'a' }),
    ])
    expect(threads.map(t => t.id)).toEqual(['a', 'b'])
    expect(threads[0].replies.map(r => r.id)).toEqual(['r1', 'r2'])
    expect(threads[1].replies).toEqual([])
  })

  it('never shows a reply as its own thread, even when its parent is missing', () => {
    const threads = buildThreads([c('r', '2026-10-05T01:00:00Z', { parent_id: 'gone' })])
    expect(threads).toEqual([])
  })

  it('splits active and resolved threads', () => {
    const { active, resolved } = splitThreads(buildThreads([
      c('a', '2026-10-05T01:00:00Z'),
      c('b', '2026-10-05T02:00:00Z', { resolved: true }),
    ]))
    expect(active.map(t => t.id)).toEqual(['a'])
    expect(resolved.map(t => t.id)).toEqual(['b'])
  })
})

describe('formatStamp', () => {
  it('formats as "Oct 5, 2026 • 2:15 AM"', () => {
    expect(formatStamp(new Date(2026, 9, 5, 2, 15).toISOString())).toBe('Oct 5, 2026 • 2:15 AM')
  })

  it('is empty for missing or invalid input', () => {
    expect(formatStamp(null)).toBe('')
    expect(formatStamp('nope')).toBe('')
  })
})

describe('roleName', () => {
  it('maps roles to display names', () => {
    expect(roleName('ARCHITECT')).toBe('Architect')
    expect(roleName('CLIENT')).toBe('Client')
    expect(roleName(undefined)).toBe('User')
  })
})
