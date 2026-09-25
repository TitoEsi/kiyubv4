import { describe, expect, it } from 'vitest'
import { PRIVACY_SECTIONS } from './legalPrivacy'
import { LEGAL_DRAFT_NOTICE, LEGAL_PLACEHOLDERS, TERMS_SECTIONS } from './legalTerms'

describe('legal draft copy', () => {
  it('keeps required terms disclaimers and placeholders', () => {
    const arch = TERMS_SECTIONS.find(s => s.id === 'disclaimer-arch')?.paragraphs.join(' ') ?? ''
    expect(arch).toMatch(/does not replace licensed/i)
    expect(arch).toMatch(/construction-ready/i)
    expect(arch).toMatch(/building codes/i)
    expect(LEGAL_DRAFT_NOTICE).toMatch(/not legal advice/i)
    expect(TERMS_SECTIONS.some(s => s.paragraphs.join(' ').includes(LEGAL_PLACEHOLDERS.entity))).toBe(true)
    expect(TERMS_SECTIONS.some(s => s.paragraphs.join(' ').includes(LEGAL_PLACEHOLDERS.jurisdiction))).toBe(true)
  })

  it('avoids unimplemented privacy claims', () => {
    const text = PRIVACY_SECTIONS.flatMap(s => s.paragraphs).join(' ')
    expect(text).not.toMatch(/GDPR|HIPAA|AES-256|we encrypt/i)
    expect(text).toMatch(LEGAL_PLACEHOLDERS.email)
    expect(text).toMatch(LEGAL_PLACEHOLDERS.dpo)
  })
})
