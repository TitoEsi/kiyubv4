import { describe, expect, it } from 'vitest'
import rawCss from '../App.css?raw'

const css = rawCss.replace(/\/\*[\s\S]*?\*\//g, '')

const rules = [...css.matchAll(/([^{}]+)\{([^{}]*)\}/g)].map(m => ({ selector: m[1].trim(), body: m[2] }))

function declarations(body: string): Record<string, string> {
  const out: Record<string, string> = {}
  for (const m of body.matchAll(/(--[\w-]+)\s*:\s*([^;]+);/g)) out[m[1]] = m[2].trim()
  return out
}

function block(selector: string): Record<string, string> {
  const rule = rules.find(r => r.selector.replace(/\s+/g, ' ') === selector)
  if (!rule) throw new Error(`missing theme block ${selector}`)
  return declarations(rule.body)
}

const root = block(':root')
const themes = {
  dark: { ...root, ...block('html:not([data-theme]), html[data-theme="dark"]') },
  light: { ...root, ...block('html[data-theme="light"]') },
}

function resolve(vars: Record<string, string>, name: string, depth = 0): string {
  const value = vars[name]
  if (value === undefined) throw new Error(`${name} is not defined`)
  const ref = value.match(/^var\((--[\w-]+)\)$/)
  if (ref && depth < 10) return resolve(vars, ref[1], depth + 1)
  return value
}

function luminance(hex: string): number {
  const h = hex.replace('#', '')
  const full = h.length === 3 ? h.split('').map(c => c + c).join('') : h
  const [r, g, b] = [0, 2, 4].map(i => {
    const c = parseInt(full.slice(i, i + 2), 16) / 255
    return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4
  })
  return 0.2126 * r + 0.7152 * g + 0.0722 * b
}

function contrast(a: string, b: string): number {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x)
  return (hi + 0.05) / (lo + 0.05)
}

const PAIRS: [string, string][] = [
  ['--text', '--bg'],
  ['--text', '--surface'],
  ['--text2', '--bg'],
  ['--text2', '--surface'],
  ['--text2', '--sidebar'],
  ['--accent-text', '--bg'],
  ['--accent-text', '--surface'],
  ['--action-fg', '--action-bg'],
  ['--ink-muted', '--paper'],
]

describe('theme contrast', () => {
  for (const [theme, vars] of Object.entries(themes)) {
    for (const [fg, bg] of PAIRS) {
      it(`${theme}: ${fg} on ${bg} meets WCAG AA`, () => {
        const ratio = contrast(resolve(vars, fg), resolve(vars, bg))
        expect(ratio, `${fg} on ${bg} = ${ratio.toFixed(2)}:1`).toBeGreaterThanOrEqual(4.5)
      })
    }
  }

  it('every var() without a fallback refers to a defined custom property', () => {
    const defined = new Set([...css.matchAll(/(--[\w-]+)\s*:/g)].map(m => m[1]))
    const missing = [...css.matchAll(/var\((--[\w-]+)\)/g)].map(m => m[1]).filter(n => !defined.has(n))
    expect([...new Set(missing)]).toEqual([])
  })

  it('canvas chrome stays on theme surfaces instead of the fixed paper colour', () => {
    const chrome = /\.(architect-toolbar|architect-context|architect-zoom|plan-sub-controls)\b/
    const offenders = rules.filter(r => chrome.test(r.selector) && /var\(--paper\b/.test(r.body)).map(r => r.selector)
    expect(offenders).toEqual([])
  })
})
