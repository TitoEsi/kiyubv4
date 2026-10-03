import { describe, expect, it } from 'vitest'
import { historyPath, roleNavItems } from './roleNav'

describe('role nav', () => {
  it('keeps About and Contact out of every role nav', () => {
    for (const role of ['CLIENT', 'ARCHITECT', 'MAIN_ADMIN', 'IT_PERSONNEL']) {
      const labels = roleNavItems(role).map(item => item.label)
      expect(labels).not.toContain('About')
      expect(labels).not.toContain('Contact')
    }
  })

  it('matches the specified role links', () => {
    expect(roleNavItems('CLIENT').map(i => i.label)).toEqual(['Projects'])
    expect(roleNavItems('ARCHITECT').map(i => i.label)).toEqual(['Dashboard', 'Projects', 'Clients'])
    expect(roleNavItems('MAIN_ADMIN').map(i => i.label)).toEqual(['Dashboard', 'Projects', 'Clients', 'Architects'])
    expect(roleNavItems('IT_PERSONNEL').map(i => i.label)).toEqual(['Dashboard', 'Clients', 'Architects', 'Analytics', 'History'])
  })

  it('exposes Studio to no role', () => {
    for (const role of ['CLIENT', 'ARCHITECT', 'MAIN_ADMIN', 'IT_PERSONNEL']) {
      const items = roleNavItems(role)
      expect(items.map(i => i.to)).not.toContain('/sandbox')
      expect(items.map(i => i.label)).not.toContain('Studio')
    }
  })

  it('has a role-prefixed history path', () => {
    expect(historyPath('CLIENT')).toBe('/client/history')
    expect(historyPath('ARCHITECT')).toBe('/architect/history')
    expect(historyPath('MAIN_ADMIN')).toBe('/admin/history')
    expect(historyPath('IT_PERSONNEL')).toBe('/it/history')
  })
})
