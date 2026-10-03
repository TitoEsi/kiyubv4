import { UNIT_ORDER, UNITS, isMeasurementUnit } from '../units/measurement'
import { useUnits } from '../units/UnitsProvider'

export default function UnitSelect() {
  const { unit, setUnit } = useUnits()
  return (
    <label className="unit-select">
      <span>Units</span>
      <select
        className="catalog-select"
        value={unit}
        aria-label="Measurement units"
        onChange={e => {
          if (isMeasurementUnit(e.target.value)) setUnit(e.target.value)
        }}
      >
        {UNIT_ORDER.map(id => (
          <option key={id} value={id}>{UNITS[id].label}</option>
        ))}
      </select>
    </label>
  )
}
