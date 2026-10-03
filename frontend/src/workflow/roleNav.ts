export type RoleNavItem = { to: string; label: string; end?: boolean }

export function roleNavItems(role: string | undefined): RoleNavItem[] {
  if (role === 'CLIENT') return [{ to: '/client', label: 'Projects' }]
  if (role === 'ARCHITECT') {
    return [
      { to: '/architect', label: 'Dashboard', end: true },
      { to: '/architect/projects', label: 'Projects' },
      { to: '/architect/clients', label: 'Clients' },
    ]
  }
  if (role === 'MAIN_ADMIN') {
    return [
      { to: '/admin', label: 'Dashboard', end: true },
      { to: '/admin/projects', label: 'Projects' },
      { to: '/admin/clients', label: 'Clients' },
      { to: '/admin/architects', label: 'Architects' },
    ]
  }
  if (role === 'IT_PERSONNEL') {
    return [
      { to: '/it', label: 'Dashboard', end: true },
      { to: '/it/clients', label: 'Clients' },
      { to: '/it/architects', label: 'Architects' },
      { to: '/it/analytics', label: 'Analytics' },
      { to: '/it/history', label: 'History' },
    ]
  }
  return []
}

export function historyPath(role: string | undefined): string | null {
  if (role === 'CLIENT') return '/client/history'
  if (role === 'ARCHITECT') return '/architect/history'
  if (role === 'MAIN_ADMIN') return '/admin/history'
  if (role === 'IT_PERSONNEL') return '/it/history'
  return null
}
