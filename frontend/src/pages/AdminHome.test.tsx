import { describe, expect, it, vi } from 'vitest'
import { renderToStaticMarkup } from 'react-dom/server'
import { MemoryRouter } from 'react-router-dom'

vi.mock('./WorkflowShell', () => ({
  default: ({ children }: { children: unknown }) => children,
}))

import AdminHome from './AdminHome'

describe('AdminHome', () => {
  const html = renderToStaticMarkup(
    <MemoryRouter>
      <AdminHome />
    </MemoryRouter>,
  )

  it('is the single admin dashboard covering every former IT and Main Admin area', () => {
    for (const to of ['/admin/projects', '/admin/clients', '/admin/architects', '/admin/analytics', '/admin/history']) {
      expect(html).toContain(`href="${to}"`)
    }
    expect(html).not.toContain('href="/it')
  })

  it('invites architects in one step without an IT approval stage', () => {
    expect(html).toContain('Invite architect')
    expect(html).toContain('Send invitation')
    expect(html).toContain('Architect requests')
    expect(html).not.toMatch(/\bIT\b/)
  })

  it('tells Admin the canvas is view-only', () => {
    expect(html).toContain('view-only for Admin')
  })
})
