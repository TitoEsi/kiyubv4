import { createContext, ReactNode, useCallback, useContext, useMemo, useState } from 'react'

export type Theme = 'light' | 'dark'

export const THEME_STORAGE_KEY = 'kiyub_theme'

export const KIYUB_LOGO_SRC = {
  light: {
    full: '/kiyub-logo-light.png',
    mark: '/kiyub-icon-light.png',
  },
  dark: {
    full: '/kiyub-logo-dark.png',
    mark: '/kiyub-icon-dark.png',
  },
} as const

export function resolveTheme(stored: string | null, systemDark: boolean): Theme {
  if (stored === 'light' || stored === 'dark') return stored
  return systemDark ? 'dark' : 'light'
}

export function logoSrc(theme: Theme, variant: 'full' | 'mark'): string {
  return KIYUB_LOGO_SRC[theme][variant]
}

export function faviconSrc(theme: Theme): string {
  return KIYUB_LOGO_SRC[theme].mark
}

export function applyTheme(theme: Theme): void {
  if (typeof document === 'undefined') return
  const root = document.documentElement
  root.dataset.theme = theme
  root.style.colorScheme = theme
  const icon = faviconSrc(theme)
  document.querySelectorAll<HTMLLinkElement>('link[rel="icon"], link[rel="apple-touch-icon"]').forEach(link => {
    if (link.media && link.media !== 'all') return
    link.href = icon
  })
  const scheme = document.querySelector<HTMLMetaElement>('meta[name="color-scheme"]')
  if (scheme) scheme.content = theme
}

export function readStoredTheme(): string | null {
  try {
    return localStorage.getItem(THEME_STORAGE_KEY)
  } catch {
    return null
  }
}

export function writeStoredTheme(theme: Theme): void {
  try {
    localStorage.setItem(THEME_STORAGE_KEY, theme)
  } catch {
    /* ignore quota / private mode */
  }
}

export function systemPrefersDark(): boolean {
  return typeof window !== 'undefined'
    && window.matchMedia('(prefers-color-scheme: dark)').matches
}

const ThemeContext = createContext<{
  theme: Theme
  toggle: () => void
} | null>(null)

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setTheme] = useState<Theme>(() => {
    const next = resolveTheme(readStoredTheme(), systemPrefersDark())
    applyTheme(next)
    return next
  })

  const toggle = useCallback(() => {
    setTheme(prev => {
      const next: Theme = prev === 'dark' ? 'light' : 'dark'
      writeStoredTheme(next)
      applyTheme(next)
      return next
    })
  }, [])

  const value = useMemo(() => ({ theme, toggle }), [theme, toggle])
  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>
}

export function useTheme() {
  const ctx = useContext(ThemeContext)
  if (!ctx) throw new Error('useTheme must be used within ThemeProvider')
  return ctx
}
