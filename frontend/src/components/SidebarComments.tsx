import { useEffect, useState } from 'react'
import CommentThread, { type CommentActions } from './CommentThread'
import { splitThreads, formatStamp, roleName, type CommentThreadData } from '../workflow/commentThreads'
import { displayNameFromEmail } from '../workflow/displayName'

export interface SidebarCommentsProps {
  threads: CommentThreadData[]
  actions?: CommentActions
  selectedId?: string | null
  onSelect?: (id: string | null) => void
}

/** Active and resolved comment threads with details and a general (unpinned) composer. */
export default function SidebarComments({ threads, actions, selectedId, onSelect }: SidebarCommentsProps) {
  const { active, resolved } = splitThreads(threads)
  const [tab, setTab] = useState<'active' | 'resolved'>('active')
  const [draft, setDraft] = useState('')
  const list = tab === 'active' ? active : resolved
  const selectedResolved = selectedId ? threads.find(t => t.id === selectedId)?.resolved : undefined
  useEffect(() => {
    if (selectedResolved !== undefined) setTab(selectedResolved ? 'resolved' : 'active')
  }, [selectedId, selectedResolved])
  return (
    <div className="inspector-section sidebar-comments" aria-label="Comments">
      <div className="inspector-title">Comments</div>
      <div className="sidebar-comments-tabs" role="group" aria-label="Comment filter">
        <button type="button" aria-pressed={tab === 'active'} onClick={() => setTab('active')}>Active ({active.length})</button>
        <button type="button" aria-pressed={tab === 'resolved'} onClick={() => setTab('resolved')}>Resolved ({resolved.length})</button>
      </div>
      {list.length === 0 ? (
        <p className="inspector-area">{tab === 'active' ? 'No active comments.' : 'No resolved comments.'}</p>
      ) : (
        <ul className="sidebar-comment-list">
          {list.map(t => {
            const open = t.id === selectedId
            return (
              <li key={t.id}>
                <button type="button" className="sidebar-comment-row" aria-expanded={open} onClick={() => onSelect?.(open ? null : t.id)}>
                  <span className="sidebar-comment-excerpt">{t.body}</span>
                  <span className="sidebar-comment-sub">
                    {roleName(t.author_role)} · {displayNameFromEmail(t.author_email || 'user')} · {formatStamp(t.created_at)}
                    {t.replies.length > 0 && ` · ${t.replies.length} repl${t.replies.length === 1 ? 'y' : 'ies'}`}
                  </span>
                </button>
                {open && (
                  <div className="sidebar-comment-detail">
                    <CommentThread thread={t} actions={actions} />
                  </div>
                )}
              </li>
            )
          })}
        </ul>
      )}
      {actions?.onAddGeneral && actions.canComment !== false && (
        <form className="comment-composer" onSubmit={e => {
          e.preventDefault()
          if (!draft.trim()) return
          actions.onAddGeneral?.(draft.trim())
          setDraft('')
        }}>
          <textarea value={draft} onChange={e => setDraft(e.target.value)} placeholder="Add a general comment" aria-label="New comment" />
          <div className="plan-note-actions"><button type="submit" disabled={!draft.trim()}>Post</button></div>
        </form>
      )}
    </div>
  )
}
