import { describe, expect, it } from 'vitest'
import { isPublicNavActive, PUBLIC_NAV } from './LandingHeader'

describe('public nav active state', () => {
  it('keeps About and Contact out of the landing header', () => {
    const labels = PUBLIC_NAV.map(item => item.label)
    expect(labels).toEqual(['Concepts'])
    expect(labels).not.toContain('About')
    expect(labels).not.toContain('Contact')
  })

  it('highlights only the matching landing hash', () => {
    expect(isPublicNavActive('/', '#gallery', '#gallery')).toBe(true)
    expect(isPublicNavActive('/', '', '#gallery')).toBe(false)
    expect(isPublicNavActive('/login', '#gallery', '#gallery')).toBe(false)
    expect(isPublicNavActive('/terms', '', '#gallery')).toBe(false)
  })
})
