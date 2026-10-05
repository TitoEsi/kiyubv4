import type { Comment } from './api'

export type CommentThreadData = Comment & { replies: Comment[] }

/** Top-level comments (oldest first) with their replies (oldest first). Orphaned replies are dropped. */
export function buildThreads(comments: Comment[]): CommentThreadData[] {
  const byTime = (a: Comment, b: Comment) => (a.created_at || '').localeCompare(b.created_at || '')
  const roots = comments.filter(c => !c.parent_id).sort(byTime)
  const replies = new Map<string, Comment[]>()
  for (const c of comments) {
    if (!c.parent_id) continue
    const list = replies.get(c.parent_id) || []
    list.push(c)
    replies.set(c.parent_id, list)
  }
  return roots.map(root => ({ ...root, replies: (replies.get(root.id) || []).sort(byTime) }))
}

export function splitThreads(threads: CommentThreadData[]) {
  return {
    active: threads.filter(t => !t.resolved),
    resolved: threads.filter(t => t.resolved),
  }
}

const DATE = new Intl.DateTimeFormat('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
const TIME = new Intl.DateTimeFormat('en-US', { hour: 'numeric', minute: '2-digit' })

/** "Oct 5, 2026 • 2:15 AM" */
export function formatStamp(iso: string | null | undefined): string {
  if (!iso) return ''
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return ''
  return `${DATE.format(d)} • ${TIME.format(d)}`
}

export function roleName(role: string | null | undefined): string {
  if (role === 'ARCHITECT') return 'Architect'
  if (role === 'CLIENT') return 'Client'
  if (role === 'ADMIN') return 'Admin'
  // Retired role values that only appear on historical audit records.
  if (role === 'MAIN_ADMIN') return 'Admin'
  if (role === 'IT_PERSONNEL') return 'IT Personnel (former role)'
  return 'User'
}

export function actorRoleLabel(role: string | null | undefined, deleted?: boolean): string {
  return deleted ? `${roleName(role)}, deleted account` : roleName(role)
}
