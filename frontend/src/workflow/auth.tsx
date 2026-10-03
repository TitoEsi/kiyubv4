import { createContext, useContext, useEffect, useMemo, useState, ReactNode } from 'react'
import { login as apiLogin, me, WorkflowUser } from './api'
import { isSupabaseAuth, supabase } from '../lib/supabase'

interface AuthState {
  user: WorkflowUser | null
  token: string | null
  ready: boolean
  login: (email: string, password: string) => Promise<WorkflowUser>
  applySession: (token: string, user: WorkflowUser) => void
  updateUser: (user: WorkflowUser) => void
  logout: () => void
}

const AuthContext = createContext<AuthState | null>(null)

function persistToken(token: string | null) {
  if (token) localStorage.setItem('kiyub_token', token)
  else localStorage.removeItem('kiyub_token')
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<WorkflowUser | null>(null)
  const [token, setToken] = useState<string | null>(localStorage.getItem('kiyub_token'))
  const [ready, setReady] = useState(false)

  useEffect(() => {
    let cancelled = false

    async function hydrate(nextToken: string | null) {
      if (!nextToken) {
        if (!cancelled) {
          setUser(null)
          setReady(true)
        }
        return
      }
      try {
        const profile = await me()
        if (!cancelled) setUser(profile)
      } catch {
        persistToken(null)
        if (!cancelled) {
          setToken(null)
          setUser(null)
        }
      } finally {
        if (!cancelled) setReady(true)
      }
    }

    if (isSupabaseAuth() && supabase) {
      supabase.auth.getSession().then(({ data }) => {
        const access = data.session?.access_token || null
        if (access) {
          persistToken(access)
          setToken(access)
        }
        return hydrate(access || token)
      })
      const { data: sub } = supabase.auth.onAuthStateChange((_event, session) => {
        const access = session?.access_token || null
        persistToken(access)
        setToken(access)
        if (access) {
          me().then(setUser).catch(() => setUser(null))
        } else {
          setUser(null)
        }
      })
      return () => {
        cancelled = true
        sub.subscription.unsubscribe()
      }
    }

    hydrate(token)
    return () => {
      cancelled = true
    }
  }, [])

  const value = useMemo<AuthState>(() => ({
    user,
    token,
    ready,
    login: async (email, password) => {
      if (isSupabaseAuth() && supabase) {
        const { data, error } = await supabase.auth.signInWithPassword({ email, password })
        if (error || !data.session) {
          throw { response: { data: { detail: error?.message || 'Login failed' } } }
        }
        persistToken(data.session.access_token)
        setToken(data.session.access_token)
        const profile = await me()
        setUser(profile)
        return profile
      }
      const data = await apiLogin(email, password)
      persistToken(data.token)
      setToken(data.token)
      setUser(data.user)
      return data.user
    },
    applySession: (nextToken, nextUser) => {
      persistToken(nextToken)
      setToken(nextToken)
      setUser(nextUser)
    },
    updateUser: nextUser => setUser(nextUser),
    logout: () => {
      if (isSupabaseAuth() && supabase) void supabase.auth.signOut()
      persistToken(null)
      setToken(null)
      setUser(null)
    },
  }), [user, token, ready])

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}
