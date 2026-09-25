import { useEffect, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import KiyubLogo from '../components/KiyubLogo'
import { isSupabaseAuth, supabase } from '../lib/supabase'

export default function AuthCallback() {
  const nav = useNavigate()
  const [params] = useSearchParams()
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const next = params.get('next') || params.get('redirect') || '/invite'
    async function run() {
      if (isSupabaseAuth() && supabase) {
        const hash = window.location.hash.startsWith('#') ? window.location.hash.slice(1) : ''
        const bits = new URLSearchParams(hash)
        const access = bits.get('access_token')
        const refresh = bits.get('refresh_token')
        if (access && refresh) {
          const { error: sessionError } = await supabase.auth.setSession({ access_token: access, refresh_token: refresh })
          if (sessionError) {
            setError('Could not continue from this invitation link.')
            return
          }
        }
      }
      const safe = next.startsWith('/') ? next : `/${next}`
      nav(safe, { replace: true })
    }
    void run()
  }, [nav, params])

  if (error) {
    return (
      <div className="wf-login">
        <KiyubLogo variant="mark" />
        <p className="error-msg" role="alert">{error}</p>
      </div>
    )
  }

  return (
    <div className="wf-login wf-login-loading">
      <KiyubLogo variant="mark" />
      <p>Continuing…</p>
    </div>
  )
}
