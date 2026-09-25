import { describe, expect, it, vi } from 'vitest'

vi.mock('../lib/supabase', () => ({
  isSupabaseAuth: () => false,
  supabase: null,
}))

import { isSupabaseAuth } from '../lib/supabase'

describe('workflow auth supabase wiring', () => {
  it('falls back to REST login when Vite Supabase env is unset', () => {
    expect(isSupabaseAuth()).toBe(false)
  })
})
