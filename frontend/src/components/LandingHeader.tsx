import { Link, useLocation } from 'react-router-dom'
import KiyubLogo from './KiyubLogo'
import ThemeToggle from './ThemeToggle'

export const PUBLIC_NAV = [
  { label: 'Concepts', hash: '#gallery' },
] as const

export function isPublicNavActive(pathname: string, hash: string, targetHash: string) {
  return pathname === '/' && hash === targetHash
}

export default function LandingHeader() {
  const { pathname, hash } = useLocation()

  return (
    <header className="landing-top">
      <Link to="/" className="wf-brand" aria-label="KIYUB home">
        <KiyubLogo variant="full" />
      </Link>
      <nav className="landing-public-nav" aria-label="Public">
        {PUBLIC_NAV.map(item => {
          const active = isPublicNavActive(pathname, hash, item.hash)
          const href = pathname === '/' ? item.hash : `/${item.hash}`
          return (
            <a
              key={item.hash}
              href={href}
              className={active ? 'wf-nav-link active' : 'wf-nav-link'}
            >
              {item.label}
            </a>
          )
        })}
      </nav>
      <div className="wf-top-end">
        <ThemeToggle />
        <Link className="landing-nav-signin" to="/login">Sign in</Link>
      </div>
    </header>
  )
}
