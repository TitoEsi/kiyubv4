import { createClient, SupabaseClient } from '@supabase/supabase-js'

const url = import.meta.env.VITE_SUPABASE_URL as string | undefined
const anon = import.meta.env.VITE_SUPABASE_ANON_KEY as string | undefined

export const isSupabaseAuth = () => Boolean(url && anon)

export const supabase: SupabaseClient | null = isSupabaseAuth()
  ? createClient(url!, anon!)
  : null
