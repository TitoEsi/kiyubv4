import { describe, expect, it } from 'vitest'
import { displayNameFromEmail, formatRelative, greetingWord } from './displayName'

describe('displayNameFromEmail', () => {
  it('uses the email local-part', () => {
    expect(displayNameFromEmail('ezequiel@kiyub.local')).toBe('Ezequiel')
    expect(displayNameFromEmail('client@kiyub.local')).toBe('Client')
  })
})

describe('greetingWord', () => {
  it('is time-aware', () => {
    expect(greetingWord(new Date('2026-01-01T09:00:00'))).toBe('Good morning')
    expect(greetingWord(new Date('2026-01-01T15:00:00'))).toBe('Good afternoon')
    expect(greetingWord(new Date('2026-01-01T20:00:00'))).toBe('Good evening')
  })
})

describe('formatRelative', () => {
  it('describes recent updates', () => {
    const now = new Date('2026-01-01T12:00:00Z')
    expect(formatRelative('2026-01-01T10:00:00Z', now)).toBe('Updated 2 hours ago')
  })
})
