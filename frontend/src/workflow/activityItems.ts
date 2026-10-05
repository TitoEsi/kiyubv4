import type { ActivityEntry } from './api'
import { actorRoleLabel, formatStamp } from './commentThreads'
import { displayNameFromEmail } from './displayName'
import { statusLabel } from './statusLabels'

export interface ActivityItem {
  id: string
  title: string
  actor: string
  when: string
  /** The comment text the entry is about (current body, or the edited-to body). */
  quote?: string
  /** Previous body for edits, or the parent comment for replies. */
  context?: { label: 'Previously' | 'In reply to'; text: string }
  resolution?: string
  changes: string[]
  /** Version the entry belongs to; viewable means the reader may open it. */
  version?: { number: number; revisionId: string; viewable: boolean }
  /** Version a resolved comment was implemented in. */
  implementedIn?: number
}

const str = (v: unknown): string | undefined => (typeof v === 'string' && v.trim() ? v : undefined)
const titleCase = (s: string) => s.toLowerCase().replace(/\b\w/g, c => c.toUpperCase())
const num = (v: unknown): number | undefined => (typeof v === 'number' && Number.isFinite(v) ? v : undefined)

function title(e: ActivityEntry): string {
  const m = e.metadata || {}
  const v = num(m.version) ?? e.version ?? undefined
  switch (e.event_type) {
    case 'COMMENT_CREATED':
      return 'Comment Added'
    case 'COMMENT_EDITED':
      return 'Comment Edited'
    case 'COMMENT_REPLIED':
      return 'Reply Added'
    case 'COMMENT_RESOLVED':
      return 'Comment Resolved'
    case 'COMMENT_REOPENED':
      return 'Comment Reopened'
    case 'VERSION_SUBMITTED': {
      const from = num(m.restored_from_version)
      const base = v != null ? `Version ${v} — Sent for Review` : 'Sent for Review'
      return from != null ? `${base} (restored from Version ${from})` : base
    }
    case 'VERSION_RESTORED': {
      const from = num(m.from_version)
      const to = num(m.to_version)
      return from != null && to != null ? `Version ${from} restored as Version ${to}` : 'Version Restored'
    }
    case 'STATUS_CHANGED': {
      const to = str(m.to)
      return to ? `Status changed to ${titleCase(statusLabel(to))}` : 'Status Changed'
    }
    case 'CLIENT_APPROVED':
      return 'Client Approved'
    case 'ARCHITECT_APPROVED':
      return 'Architect Approved'
    case 'PROJECT_PUBLISHED':
      return 'Project Published'
    case 'AI_GENERATION_COMPLETED':
      return 'AI Floor Plans Generated'
    case 'CANDIDATE_SELECTED':
      return 'Floor Plan Candidate Selected'
    default:
      return e.event_type.replace(/_/g, ' ').toLowerCase().replace(/^\w/, c => c.toUpperCase())
  }
}

export function activityItem(e: ActivityEntry): ActivityItem {
  const m = e.metadata || {}
  const who = e.actor_email ? displayNameFromEmail(e.actor_email) : 'System'
  const item: ActivityItem = {
    id: e.id,
    title: title(e),
    actor: e.actor_role ? `${who} (${actorRoleLabel(e.actor_role, e.actor_deleted)})` : who,
    when: formatStamp(e.created_at),
    changes: Array.isArray(m.changes) ? (m.changes as unknown[]).filter((c): c is string => typeof c === 'string') : [],
  }
  if (e.event_type.startsWith('COMMENT_')) {
    item.quote = str(m.body) ?? e.comment?.body
    const previous = str(m.previous)
    const parent = str(m.parent_body)
    if (e.event_type === 'COMMENT_EDITED' && previous) item.context = { label: 'Previously', text: previous }
    if (e.event_type === 'COMMENT_REPLIED' && parent) item.context = { label: 'In reply to', text: parent }
    if (e.event_type === 'COMMENT_RESOLVED') {
      item.resolution = str(m.note)
      if (e.comment?.resolution_version != null) item.implementedIn = e.comment.resolution_version
    }
  }
  const versionNumber = e.event_type === 'VERSION_RESTORED' ? num(m.to_version) ?? e.version ?? undefined : e.version ?? undefined
  if (versionNumber != null && e.revision_id && !e.event_type.startsWith('COMMENT_')) {
    item.version = { number: versionNumber, revisionId: e.revision_id, viewable: !!e.version_viewable }
  }
  return item
}

export function activityItems(entries: ActivityEntry[]): ActivityItem[] {
  return entries.map(activityItem)
}
