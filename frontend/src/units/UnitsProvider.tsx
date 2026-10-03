import { createContext, ReactNode, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import { useAuth } from '../workflow/auth'
import { updatePreferences } from '../workflow/api'
import {
  DEFAULT_UNIT,
  formatArea,
  formatDimensions,
  formatMeasurement,
  isMeasurementUnit,
  MeasurementUnit,
} from './measurement'

interface UnitsState {
  unit: MeasurementUnit
  setUnit: (unit: MeasurementUnit) => void
}

const UnitsContext = createContext<UnitsState | null>(null)

export function resolveUnit(value: unknown): MeasurementUnit {
  return isMeasurementUnit(value) ? value : DEFAULT_UNIT
}

/** The single source of truth for the display/input unit. Persisted on the user profile. */
export function UnitsProvider({ children }: { children: ReactNode }) {
  const { user, updateUser } = useAuth()
  const [unit, setLocal] = useState<MeasurementUnit>(() => resolveUnit(user?.measurement_unit))

  useEffect(() => {
    setLocal(resolveUnit(user?.measurement_unit))
  }, [user?.id, user?.measurement_unit])

  const setUnit = useCallback(
    (next: MeasurementUnit) => {
      setLocal(next)
      if (!user) return
      updatePreferences(next)
        .then(updateUser)
        .catch(() => setLocal(resolveUnit(user.measurement_unit)))
    },
    [user, updateUser],
  )

  const value = useMemo(() => ({ unit, setUnit }), [unit, setUnit])
  return <UnitsContext.Provider value={value}>{children}</UnitsContext.Provider>
}

const FALLBACK: UnitsState = { unit: DEFAULT_UNIT, setUnit: () => {} }

export function useUnits(): UnitsState {
  return useContext(UnitsContext) ?? FALLBACK
}

/** Formatters bound to the selected unit. Inputs are always meters / square meters. */
export function useFormat() {
  const { unit } = useUnits()
  return useMemo(
    () => ({
      unit,
      length: (m: number) => formatMeasurement(m, unit),
      area: (m2: number) => formatArea(m2, unit),
      dims: (widthM: number, depthM: number) => formatDimensions(widthM, depthM, unit),
    }),
    [unit],
  )
}
