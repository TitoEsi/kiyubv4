import { describe, expect, it } from 'vitest'
import { historyPath, roleNavItems } from './roleNav'
import { roleHome } from './paths'

const ROLES = ['CLIENT', 'ARCHITECT', 'ADMIN']

describe('role nav', () => {
  it('keeps About and Contact out of every role nav', () => {
    for (const role of ROLES) {
      const labels = roleNavItems(role).map(item => item.label)
      expect(labels).not.toContain('About')
      expect(labels).not.toContain('Contact')
    }
  })

  it('matches the specified role links', () => {
    expect(roleNavItems('CLIENT').map(i => i.label)).toEqual(['Projects'])
    expect(roleNavItems('ARCHITECT').map(i => i.label)).toEqual(['Dashboard', 'Projects', 'Clients'])
    expect(roleNavItems('ADMIN').map(i => i.label)).toEqual(['Dashboard', 'Projects', 'Clients', 'Architects', 'Analytics', 'History'])
  })

  it('keeps every Admin link under /admin', () => {
    for (const item of roleNavItems('ADMIN')) expect(item.to.startsWith('/admin')).toBe(true)
  })

  it('gives retired roles no navigation, history, or home', () => {
    for (const role of ['IT_PERSONNEL', 'MAIN_ADMIN']) {
      expect(roleNavItems(role)).toEqual([])
      expect(historyPath(role)).toBeNull()
      expect(roleHome(role)).toBe('/login')
    }
  })

  it('exposes Studio to no role', () => {
    for (const role of ROLES) {
      const items = roleNavItems(role)
      expect(items.map(i => i.to)).not.toContain('/sandbox')
      expect(items.map(i => i.label)).not.toContain('Studio')
    }
  })

  it('has a role-prefixed history path', () => {
    expect(historyPath('CLIENT')).toBe('/client/history')
    expect(historyPath('ARCHITECT')).toBe('/architect/history')
    expect(historyPath('ADMIN')).toBe('/admin/history')
  })
})
