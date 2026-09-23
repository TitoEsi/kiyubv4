import { Bell } from '@phosphor-icons/react'
import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { listNotifications, markNotificationRead, Notification } from '../workflow/api'

function kindLabel(kind: string) {
  return kind.replace(/_/g, ' ')
}

export default function NotificationBell() {
  const [notes, setNotes] = useState<Notification[]>([])
  const [open, setOpen] = useState(false)
  const wrapRef = useRef<HTMLDivElement>(null)

  async function refresh() {
    try {
      setNotes(await listNotifications())
    } catch {
      setNotes([])
    }
  }

  useEffect(() => {
    refresh()
  }, [])

  useEffect(() => {
    function onDoc(e: MouseEvent) {
      if (!wrapRef.current?.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', onDoc)
    return () => document.removeEventListener('mousedown', onDoc)
  }, [])

  const unread = notes.filter(n => !n.read).length

  async function onOpen() {
    const next = !open
    setOpen(next)
    if (next) await refresh()
  }

  async function onRead(n: Notification) {
    if (!n.read) {
      try {
        await markNotificationRead(n.id)
        setNotes(prev => prev.map(x => x.id === n.id ? { ...x, read: true } : x))
      } catch {
        /* keep local list */
      }
    }
  }

  return (
    <div className="wf-bell-wrap" ref={wrapRef}>
      <button
        type="button"
        className="wf-bell"
        aria-label={unread ? `${unread} unread notifications` : 'Notifications'}
        aria-expanded={open}
        onClick={onOpen}
      >
        <Bell size={18} weight={unread ? 'fill' : 'regular'} aria-hidden />
        {unread > 0 && <span className="wf-bell-badge">{unread > 9 ? '9+' : unread}</span>}
      </button>
      {open && (
        <div className="wf-notify-pop" role="dialog" aria-label="Notifications">
          {notes.length === 0 ? (
            <p className="wf-hint">No notifications.</p>
          ) : (
            <ul className="wf-notify-list">
              {notes.map(n => (
                <li key={n.id} className={n.read ? '' : 'unread'}>
                  {n.project_id ? (
                    <Link to={`/projects/${n.project_id}`} onClick={() => { onRead(n); setOpen(false) }}>
                      <span className="studio-meta">{kindLabel(n.kind)}</span>
                      <span>{n.message}</span>
                    </Link>
                  ) : (
                    <button type="button" className="wf-notify-plain" onClick={() => onRead(n)}>
                      <span className="studio-meta">{kindLabel(n.kind)}</span>
                      <span>{n.message}</span>
                    </button>
                  )}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  )
}
