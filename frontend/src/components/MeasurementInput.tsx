import { InputHTMLAttributes, useEffect, useState } from 'react'
import { useUnits } from '../units/UnitsProvider'
import {
  areaSymbol,
  displayArea,
  displayLength,
  inputStep,
  parseArea,
  parseMeasurement,
  UNITS,
} from '../units/measurement'

type BaseProps = Omit<InputHTMLAttributes<HTMLInputElement>, 'value' | 'onChange' | 'min' | 'max' | 'step' | 'type'>

interface Props extends BaseProps {
  /** Canonical value: meters (length) or square meters (area). */
  value: number
  onCommit: (canonical: number) => void
  /** Canonical bounds. Out-of-range input is clamped. */
  min?: number
  max?: number
  showUnit?: boolean
}

function clamp(v: number, min?: number, max?: number) {
  if (min != null && v < min) return min
  if (max != null && v > max) return max
  return v
}

function useCanonicalDraft(value: number, display: (v: number) => string) {
  const [draft, setDraft] = useState(() => display(value))
  const [editing, setEditing] = useState(false)
  useEffect(() => {
    if (!editing) setDraft(display(value))
  }, [value, display, editing])
  return { draft, setDraft, editing, setEditing }
}

/** Length input: shows and accepts the selected unit, commits meters. */
export function MeasurementInput({ value, onCommit, min, max, showUnit = true, className, ...rest }: Props) {
  const { unit } = useUnits()
  const { draft, setDraft, setEditing } = useCanonicalDraft(value, v => displayLength(v, unit))

  function commit() {
    setEditing(false)
    const m = parseMeasurement(draft, unit)
    if (m == null) {
      setDraft(displayLength(value, unit))
      return
    }
    const next = clamp(m, min, max)
    setDraft(displayLength(next, unit))
    if (Math.abs(next - value) > 1e-9) onCommit(next)
  }

  return (
    <span className="measurement-input">
      <input
        {...rest}
        className={className}
        type="number"
        inputMode="decimal"
        step={inputStep(unit)}
        value={draft}
        onFocus={() => setEditing(true)}
        onChange={e => setDraft(e.target.value)}
        onBlur={commit}
        onKeyDown={e => {
          if (e.key === 'Enter') (e.target as HTMLInputElement).blur()
        }}
      />
      {showUnit && <span className="measurement-input-unit">{UNITS[unit].symbol}</span>}
    </span>
  )
}

/** Area input: shows and accepts squared selected unit, commits square meters. */
export function AreaInput({ value, onCommit, min, max, showUnit = true, className, ...rest }: Props) {
  const { unit } = useUnits()
  const { draft, setDraft, setEditing } = useCanonicalDraft(value, v => displayArea(v, unit))

  function commit() {
    setEditing(false)
    const m2 = parseArea(draft, unit)
    if (m2 == null) {
      setDraft(displayArea(value, unit))
      return
    }
    const next = clamp(m2, min, max)
    setDraft(displayArea(next, unit))
    if (Math.abs(next - value) > 1e-9) onCommit(next)
  }

  return (
    <span className="measurement-input">
      <input
        {...rest}
        className={className}
        type="number"
        inputMode="decimal"
        value={draft}
        onFocus={() => setEditing(true)}
        onChange={e => setDraft(e.target.value)}
        onBlur={commit}
        onKeyDown={e => {
          if (e.key === 'Enter') (e.target as HTMLInputElement).blur()
        }}
      />
      {showUnit && <span className="measurement-input-unit">{areaSymbol(unit)}</span>}
    </span>
  )
}
