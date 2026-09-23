import { describe, expect, it } from 'vitest'
import { KIYUB_LOGO_SRC, logoSrc, resolveTheme } from '../theme/theme'

describe('KiyubLogo assets', () => {
  it('maps light theme to the official light lockup and icon', () => {
    expect(logoSrc('light', 'full')).toBe('/kiyub-logo-light.png')
    expect(logoSrc('light', 'mark')).toBe('/kiyub-icon-light.png')
  })

  it('maps dark theme to the official dark lockup and icon', () => {
    expect(logoSrc('dark', 'full')).toBe('/kiyub-logo-dark.png')
    expect(logoSrc('dark', 'mark')).toBe('/kiyub-icon-dark.png')
    expect(KIYUB_LOGO_SRC.dark.mark).toBe('/kiyub-icon-dark.png')
  })
})

describe('resolveTheme', () => {
  it('uses a stored preference over the system setting', () => {
    expect(resolveTheme('light', true)).toBe('light')
    expect(resolveTheme('dark', false)).toBe('dark')
  })

  it('follows the system preference when nothing is stored', () => {
    expect(resolveTheme(null, true)).toBe('dark')
    expect(resolveTheme(null, false)).toBe('light')
    expect(resolveTheme('nope', true)).toBe('dark')
  })
})
