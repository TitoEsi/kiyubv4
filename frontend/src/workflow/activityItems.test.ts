import { describe, expect, it } from 'vitest'
import type { ActivityEntry } from './api'
import { activityItem } from './activityItems'
import { versionSourceLabel } from './versionLabels'

const entry = (event_type: string, extra: Partial<ActivityEntry> = {}): ActivityEntry => ({
  id: event_type,
  event_type,
  created_at: new Date(2026, 9, 5, 2, 15).toISOString(),
  actor_email: 'jane.doe@example.com',
  actor_role: 'ARCHITECT',
  metadata: {},
  ...extra,
})

describe('activityItem', () => {
  it('titles a submitted version with its number and lists the change summary', () => {
    const item = activityItem(entry('VERSION_SUBMITTED', {
      revision_id: 'r5', version: 5, version_viewable: true,
      metadata: { version: 5, changes: ['Bedroom 2 area increased by 1.2 m²', 'Kitchen window added'] },
    }))
    expect(item.title).toBe('Version 5 — Sent for Review')
    expect(item.changes).toEqual(['Bedroom 2 area increased by 1.2 m²', 'Kitchen window added'])
    expect(item.version).toEqual({ number: 5, revisionId: 'r5', viewable: true })
    expect(item.when).toBe('Oct 5, 2026 • 2:15 AM')
    expect(item.actor).toContain('(Architect)')
  })

  it('describes a restore as "Version 4 restored as Version 8"', () => {
    const item = activityItem(entry('VERSION_RESTORED', {
      revision_id: 'r8', version: 8, version_viewable: true,
      metadata: { from_version: 4, to_version: 8 },
    }))
    expect(item.title).toBe('Version 4 restored as Version 8')
    expect(item.version?.number).toBe(8)
  })

  it('quotes resolved comments with their resolution and implemented version', () => {
    const item = activityItem(entry('COMMENT_RESOLVED', {
      target: 'c1',
      metadata: { body: 'Make the kitchen bigger', note: 'Extended by 1 m' },
      comment: { id: 'c1', body: 'Make the kitchen bigger', resolved: true, resolution_version: 6 },
    }))
    expect(item.title).toBe('Comment Resolved')
    expect(item.quote).toBe('Make the kitchen bigger')
    expect(item.resolution).toBe('Extended by 1 m')
    expect(item.implementedIn).toBe(6)
    expect(item.version).toBeUndefined()
  })

  it('shows the parent for replies and the previous text for edits', () => {
    const reply = activityItem(entry('COMMENT_REPLIED', { actor_role: 'CLIENT', metadata: { body: 'Thanks', parent_body: 'Done' } }))
    expect(reply.title).toBe('Reply Added')
    expect(reply.context).toEqual({ label: 'In reply to', text: 'Done' })
    const edit = activityItem(entry('COMMENT_EDITED', { metadata: { body: 'new', previous: 'old' } }))
    expect(edit.title).toBe('Comment Edited')
    expect(edit.quote).toBe('new')
    expect(edit.context).toEqual({ label: 'Previously', text: 'old' })
  })

  it('labels status changes with display labels', () => {
    expect(activityItem(entry('STATUS_CHANGED', { metadata: { from: 'IN_PROGRESS', to: 'FOR_CHECKING' } })).title)
      .toBe('Status changed to Reviewing')
    expect(activityItem(entry('STATUS_CHANGED', { metadata: { to: 'IN_PROGRESS' } })).title)
      .toBe('Status changed to In Progress')
  })

  it('does not link versions the reader may not open', () => {
    const item = activityItem(entry('VERSION_RESTORED', { revision_id: 'r8', version: 8, version_viewable: false, metadata: { from_version: 4, to_version: 8 } }))
    expect(item.version?.viewable).toBe(false)
  })

  it('labels current Admin actions as Admin', () => {
    expect(activityItem(entry('PROJECT_PUBLISHED', { actor_role: 'ADMIN' })).actor).toContain('(Admin)')
  })

  it('keeps historical IT Personnel actions identifiable after the account is deleted', () => {
    const item = activityItem(entry('ARCHITECT_APPLICATION_APPROVED', {
      actor_email: 'it.ops@example.com', actor_role: 'IT_PERSONNEL', actor_deleted: true,
    }))
    expect(item.actor).toContain('IT Personnel (former role), deleted account')
  })
})

describe('versionSourceLabel', () => {
  it('describes restored versions by their source', () => {
    const v4 = { id: 'r4', version: 4, source_type: 'REVIEW' }
    const v8 = { id: 'r8', version: 8, source_type: 'RESTORED', source_revision_id: 'r4' }
    expect(versionSourceLabel(v8, [v4, v8])).toBe('Restored from Version 4 · draft')
    expect(versionSourceLabel({ ...v8, submitted_at: '2026-10-05T00:00:00Z' }, [v4, v8])).toBe('Restored from Version 4 · sent for review')
    expect(versionSourceLabel(v4)).toBe('Sent for review')
  })
})
