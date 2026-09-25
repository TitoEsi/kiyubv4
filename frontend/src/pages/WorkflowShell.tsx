import { ReactNode, useState } from 'react'
import { Link, NavLink, useNavigate } from 'react-router-dom'
import ConfirmDialog from '../components/ConfirmDialog'
import KiyubLogo from '../components/KiyubLogo'
import NotificationBell from '../components/NotificationBell'
import ThemeToggle from '../components/ThemeToggle'
import WorkflowFooter from '../components/WorkflowFooter'
import { useAuth } from '../workflow/auth'
import { roleHome } from '../workflow/paths'
import { canOpenStudio, roleNavItems } from '../workflow/roleNav'

function navClass({ isActive }: { isActive: boolean }) {
  return isActive ? 'wf-nav-link active' : 'wf-nav-link'
}

export default function WorkflowShell({
  status,
  scratch,
  flush,
  children,
}: {
  status?: string
  scratch?: boolean
  flush?: boolean
  children: ReactNode
}) {
  const { user, logout } = useAuth()
  const nav = useNavigate()
  const home = roleHome(user?.role)
  const navItems = roleNavItems(user?.role)
  const canStudio = canOpenStudio(user?.role)
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
        {navItems.length > 0 && (
          <nav className="wf-nav" aria-label="Workspace">
            {navItems.map(item => (
              <NavLink key={item.to} to={item.to} end={item.end} className={navClass}>
                {item.label}
              </NavLink>
            ))}
          </nav>
        )}
        {scratch && <span className="wf-scratch">Scratch studio</span>}
        {status && <span className="wf-status-chip">{status}</span>}
        <div className="wf-top-end">
          <ThemeToggle />
          {user && <NotificationBell />}
          {user && <span className="wf-user">{user.email}</span>}
          {canStudio && <Link className="wf-link" to="/sandbox">Studio</Link>}
          {user ? (
            <button className="wf-action" type="button" onClick={() => setConfirmSignOut(true)}>Sign out</button>
          ) : (
            <Link className="wf-link" to="/login">Sign in</Link>
          )}
        </div>
      </header>
      <div className={flush ? 'wf-body wf-body-flush' : 'wf-body'}>{children}</div>
      {!flush && <WorkflowFooter />}
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
