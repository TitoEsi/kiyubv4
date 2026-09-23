import { ReactNode, useState } from 'react'
import { Link, NavLink, useNavigate } from 'react-router-dom'
import ConfirmDialog from '../components/ConfirmDialog'
import KiyubLogo from '../components/KiyubLogo'
import NotificationBell from '../components/NotificationBell'
import ThemeToggle from '../components/ThemeToggle'
import { useAuth } from '../workflow/auth'
import { roleHome } from '../workflow/paths'

export interface Crumb {
  label: string
  to?: string
}

export default function WorkflowShell({
  title,
  crumbs,
  status,
  scratch,
  flush,
  children,
}: {
  title: string
  crumbs?: Crumb[]
  status?: string
  scratch?: boolean
  flush?: boolean
  children: ReactNode
}) {
  const { user, logout } = useAuth()
  const nav = useNavigate()
  const home = roleHome(user?.role)
  const isClient = user?.role === 'CLIENT'
  const isArchitect = user?.role === 'ARCHITECT'
  const [confirmSignOut, setConfirmSignOut] = useState(false)

  function signOut() {
    logout()
    setConfirmSignOut(false)
    nav('/')
  }

  return (
    <div className="wf-shell">
      <header className="wf-top">
        <Link to={user ? home : '/'} className="wf-brand" aria-label="KIYUB home">
          <KiyubLogo variant="full" decorative className="kiyub-logo-nav-full" />
          <KiyubLogo variant="mark" decorative className="kiyub-logo-nav-mark" />
        </Link>
        {isClient && (
          <nav className="wf-nav" aria-label="Client">
            <NavLink to="/client" className={({ isActive }) => isActive ? 'wf-nav-link active' : 'wf-nav-link'}>Projects</NavLink>
            <NavLink to="/contact" className={({ isActive }) => isActive ? 'wf-nav-link active' : 'wf-nav-link'}>Contact</NavLink>
          </nav>
        )}
        {isArchitect && (
          <nav className="wf-nav" aria-label="Architect">
            <NavLink to="/architect" end className={({ isActive }) => isActive ? 'wf-nav-link active' : 'wf-nav-link'}>Dashboard</NavLink>
            <NavLink to="/architect/projects" className={({ isActive }) => isActive ? 'wf-nav-link active' : 'wf-nav-link'}>Projects</NavLink>
            <NavLink to="/architect/clients" className={({ isActive }) => isActive ? 'wf-nav-link active' : 'wf-nav-link'}>Clients</NavLink>
            <NavLink to="/about" className={({ isActive }) => isActive ? 'wf-nav-link active' : 'wf-nav-link'}>About</NavLink>
            <NavLink to="/contact" className={({ isActive }) => isActive ? 'wf-nav-link active' : 'wf-nav-link'}>Contact</NavLink>
          </nav>
        )}
        <nav className="wf-crumbs" aria-label="Breadcrumb">
          {crumbs?.map((c, i) => (
            <span key={`${c.label}-${i}`}>
              {i > 0 && <span aria-hidden> / </span>}
              {c.to ? <Link to={c.to}>{c.label}</Link> : <span>{c.label}</span>}
            </span>
          ))}
          {!crumbs?.length && <span className="wf-title">{title}</span>}
        </nav>
        {scratch && <span className="wf-scratch">Scratch studio</span>}
        {status && <span className="wf-status-chip">{status}</span>}
        <div className="wf-top-end">
          <ThemeToggle />
          {user && <NotificationBell />}
          {user && <span className="wf-user">{user.email}</span>}
          <Link className="wf-link" to="/sandbox">Studio</Link>
          {user ? (
            <button className="wf-action" type="button" onClick={() => setConfirmSignOut(true)}>Sign out</button>
          ) : (
            <Link className="wf-link" to="/login">Sign in</Link>
          )}
        </div>
      </header>
      <div className={flush ? 'wf-body wf-body-flush' : 'wf-body'}>{children}</div>
      {confirmSignOut && (
        <ConfirmDialog
          title="Sign out"
          body="Sign out of this KIYUB session?"
          confirmLabel="Sign out"
          onConfirm={signOut}
          onCancel={() => setConfirmSignOut(false)}
        />
      )}
    </div>
  )
}
