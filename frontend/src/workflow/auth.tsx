import { createContext, useContext, useEffect, useMemo, useState, ReactNode } from 'react'
import { login as apiLogin, me, WorkflowUser } from './api'

interface AuthState {
  user: WorkflowUser | null
  token: string | null
  ready: boolean
  login: (email: string, password: string) => Promise<WorkflowUser>
  applySession: (token: string, user: WorkflowUser) => void
  logout: () => void
}

const AuthContext = createContext<AuthState | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<WorkflowUser | null>(null)
  const [token, setToken] = useState<string | null>(localStorage.getItem('kiyub_token'))
  const [ready, setReady] = useState(false)

  useEffect(() => {
    if (!token) {
      setReady(true)
      return
    }
    me()
      .then(setUser)
      .catch(() => {
        localStorage.removeItem('kiyub_token')
        setToken(null)
        setUser(null)
      })
      .finally(() => setReady(true))
  }, [token])

  const value = useMemo<AuthState>(() => ({
    user,
    token,
    ready,
    login: async (email, password) => {
      const data = await apiLogin(email, password)
      localStorage.setItem('kiyub_token', data.token)
      setToken(data.token)
      setUser(data.user)
      return data.user
    },
    applySession: (nextToken, nextUser) => {
      localStorage.setItem('kiyub_token', nextToken)
      setToken(nextToken)
      setUser(nextUser)
    },
    logout: () => {
      localStorage.removeItem('kiyub_token')
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
