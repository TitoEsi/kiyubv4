import { describe, expect, it } from 'vitest'
import { statusLabel } from './statusLabels'

describe('statusLabel', () => {
  it('shows FOR_CHECKING as Reviewing', () => {
    expect(statusLabel('FOR_CHECKING')).toBe('Reviewing')
  })

  it('keeps other statuses as spaced text', () => {
    expect(statusLabel('IN_PROGRESS')).toBe('IN PROGRESS')
    expect(statusLabel('FOR_REVISION')).toBe('FOR REVISION')
    expect(statusLabel('APPROVED')).toBe('APPROVED')
  })

  it('returns empty text for a missing status', () => {
    expect(statusLabel(undefined)).toBe('')
    expect(statusLabel(null)).toBe('')
  })
})
