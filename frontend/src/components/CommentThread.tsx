import { useState } from 'react'
import type { Comment } from '../workflow/api'
import type { CommentThreadData } from '../workflow/commentThreads'
import { formatStamp, roleName } from '../workflow/commentThreads'
import { displayNameFromEmail } from '../workflow/displayName'

export interface CommentActions {
  currentUserId?: string
  /** Only the assigned Architect may resolve; the server enforces it too. */
  canResolve?: boolean
  canComment?: boolean
  onReply?: (parentId: string, body: string) => void
  onEdit?: (id: string, body: string) => void
  onResolve?: (id: string, resolved: boolean, note?: string) => void
  onAddGeneral?: (body: string) => void
}

function CommentEntry({ comment, actions, reply = false }: { comment: Comment; actions?: CommentActions; reply?: boolean }) {
  const [editing, setEditing] = useState(false)
  const [body, setBody] = useState(comment.body)
  const [showHistory, setShowHistory] = useState(false)
  const history = comment.edit_history || []
  const mine = !!actions?.currentUserId && comment.author_id === actions.currentUserId
  return (
    <div className={`comment-entry${reply ? ' comment-reply' : ''}`} data-comment-id={comment.id}>
      <p className="comment-head">
        <span className="comment-role">{roleName(comment.author_role)}</span>
        <span className="comment-author">{displayNameFromEmail(comment.author_email || 'user')}</span>
      </p>
      {editing ? (
        <form onSubmit={e => {
          e.preventDefault()
          if (body.trim() && body.trim() !== comment.body) actions?.onEdit?.(comment.id, body.trim())
          setEditing(false)
        }}>
          <textarea className="plan-note-editor" value={body} onChange={e => setBody(e.target.value)} aria-label="Edit comment" />
          <div className="plan-note-actions">
            <button type="submit">Save</button>
            <button type="button" onClick={() => { setEditing(false); setBody(comment.body) }}>Cancel</button>
          </div>
        </form>
      ) : (
        <p className="comment-body">{comment.body}</p>
      )}
      <p className="comment-meta">
        {formatStamp(comment.created_at)}
        {comment.revision_version != null && !reply && <> · Version {comment.revision_version}</>}
        {history.length > 0 && (
          <>
            {' · '}
            <button type="button" className="comment-link" aria-expanded={showHistory} onClick={() => setShowHistory(v => !v)}>
              Edited{history.length > 1 ? ` ${history.length}×` : ''}
            </button>
          </>
        )}
        {mine && !editing && actions?.onEdit && (
          <>
            {' · '}
            <button type="button" className="comment-link" onClick={() => { setBody(comment.body); setEditing(true) }}>Edit</button>
          </>
        )}
      </p>
      {showHistory && (
        <ol className="comment-history" aria-label="Edit history">
          {history.map((h, i) => (
            <li key={i}>
              <span className="comment-meta">
                {roleName(h.edited_by_role)} edited · {formatStamp(h.edited_at)}
              </span>
              <span className="comment-history-prev">“{h.previous}”</span>
            </li>
          ))}
        </ol>
      )}
    </div>
  )
}

/** One comment with its replies, reply box and the Architect's resolve control. */
export default function CommentThread({ thread, actions }: { thread: CommentThreadData; actions?: CommentActions }) {
  const [reply, setReply] = useState('')
  const [note, setNote] = useState('')
  const canReply = !!actions?.onReply && actions.canComment !== false
  return (
    <div className={`comment-thread${thread.resolved ? ' is-resolved' : ''}`}>
      <CommentEntry comment={thread} actions={actions} />
      {thread.replies.length > 0 && (
        <div className="comment-replies" aria-label="Replies">
          {thread.replies.map(r => <CommentEntry key={r.id} comment={r} actions={actions} reply />)}
        </div>
      )}
      {thread.resolved && (
        <div className="comment-resolution">
          <p className="comment-meta">
            Resolved by {roleName(thread.resolved_by_role)} · {formatStamp(thread.resolved_at)}
          </p>
          {thread.resolution_note && <p className="comment-body">Resolution: {thread.resolution_note}</p>}
          {thread.resolution_version != null && <p className="comment-meta">Related version: Version {thread.resolution_version}</p>}
        </div>
      )}
      {canReply && (
        <form className="comment-reply-form" onSubmit={e => {
          e.preventDefault()
          if (!reply.trim()) return
          actions?.onReply?.(thread.id, reply.trim())
          setReply('')
        }}>
          <textarea value={reply} onChange={e => setReply(e.target.value)} placeholder="Reply" aria-label="Reply to comment" />
          <div className="plan-note-actions"><button type="submit" disabled={!reply.trim()}>Reply</button></div>
        </form>
      )}
      {actions?.canResolve && actions.onResolve && (
        <div className="comment-resolve">
          {!thread.resolved && (
            <input
              className="comment-resolve-note"
              value={note}
              onChange={e => setNote(e.target.value)}
              placeholder="Resolution note (optional)"
              aria-label="Resolution note"
            />
          )}
          <label className="comment-resolve-toggle">
            <input
              type="checkbox"
              checked={!!thread.resolved}
              onChange={e => {
                actions.onResolve?.(thread.id, e.target.checked, e.target.checked ? note.trim() || undefined : undefined)
                setNote('')
              }}
            />
            Resolved
          </label>
        </div>
      )}
    </div>
  )
}
