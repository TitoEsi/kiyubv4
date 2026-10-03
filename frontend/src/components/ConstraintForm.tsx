import { useMemo, useRef } from 'react'
import {
  Car,
  CookingPot,
  Couch,
  Desktop,
  Door,
  Plant,
  Sparkle,
  Warning,
  WashingMachine,
  X,
} from '@phosphor-icons/react'
import { LotShape } from '../types/floorplan'
import {
  CeilingHeight,
  GarageChoice,
  LaundryChoice,
  OutdoorChoice,
  QuestionnaireData,
} from '../types/questionnaire'
import { validateQuestionnaire } from '../converters/validate-questionnaire'
import { ARCHITECTURAL_STYLES } from '../data/architecturalStyles'
import { useUnits } from '../units/UnitsProvider'
import { areaSymbol, fromSquareMeters, MeasurementUnit, toSquareMeters } from '../units/measurement'
import { AreaInput, MeasurementInput } from './MeasurementInput'

const MIN_LOT_M = 1
const LIVING_AREA_MIN_M2 = 75
const LIVING_AREA_MAX_M2 = 560

/** Slider step of roughly 5 m², rounded to one significant figure in the display unit. */
function livingAreaSliderStep(unit: MeasurementUnit): number {
  const raw = fromSquareMeters(5, unit)
  const pow = Math.pow(10, Math.floor(Math.log10(raw)))
  return Math.round(raw / pow) * pow
}

interface Props {
  value: QuestionnaireData
  onChange: (data: QuestionnaireData) => void
  onGenerate: () => void
  loading: boolean
  hideGenerate?: boolean
  disabled?: boolean
  generateLabel?: string
}

function Stepper({ value, min, max, onChange, disabled }: { value: number; min: number; max: number; onChange: (v: number) => void; disabled?: boolean }) {
  return (
    <div className="catalog-stepper">
      <button
        type="button"
        className="catalog-stepper-btn"
        onClick={() => onChange(Math.max(min, value - 1))}
        disabled={disabled || value <= min}
        aria-label="Decrease"
      >−</button>
      <span className="catalog-stepper-val">{value}</span>
      <button
        type="button"
        className="catalog-stepper-btn"
        onClick={() => onChange(Math.min(max, value + 1))}
        disabled={disabled || value >= max}
        aria-label="Increase"
      >+</button>
    </div>
  )
}

function GarageRow({ value, onChange, disabled }: { value: string; onChange: (v: GarageChoice) => void; disabled?: boolean }) {
  const options: { v: GarageChoice; label: string }[] = [
    { v: 'none', label: 'None' },
    { v: '1car', label: '1-Car' },
    { v: '2car', label: '2-Car' },
    { v: '3car', label: '3-Car' },
  ]
  return (
    <div className="catalog-option-chips">
      {options.map(o => (
        <button
          type="button"
          key={o.v}
          className={`catalog-chip ${value === o.v ? 'active' : ''}`}
          aria-pressed={value === o.v}
          disabled={disabled}
          onClick={() => onChange(o.v)}
        >{o.label}</button>
      ))}
    </div>
  )
}

function LaundryRow({ value, onChange, disabled }: { value: string; onChange: (v: LaundryChoice) => void; disabled?: boolean }) {
  const options: { v: LaundryChoice; label: string }[] = [
    { v: 'none', label: 'None' },
    { v: 'closet', label: 'Closet' },
    { v: 'room', label: 'Room' },
  ]
  return (
    <div className="catalog-option-chips">
      {options.map(o => (
        <button
          type="button"
          key={o.v}
          className={`catalog-chip ${value === o.v ? 'active' : ''}`}
          aria-pressed={value === o.v}
          disabled={disabled}
          onClick={() => onChange(o.v)}
        >{o.label}</button>
      ))}
    </div>
  )
}

function OutdoorRow({ value, onChange, disabled }: { value: string; onChange: (v: OutdoorChoice) => void; disabled?: boolean }) {
  const options: { v: OutdoorChoice; label: string }[] = [
    { v: 'none', label: 'None' },
    { v: 'patio', label: 'Patio' },
    { v: 'deck', label: 'Deck' },
    { v: 'both', label: 'Both' },
  ]
  return (
    <div className="catalog-option-chips">
      {options.map(o => (
        <button
          type="button"
          key={o.v}
          className={`catalog-chip ${value === o.v ? 'active' : ''}`}
          aria-pressed={value === o.v}
          disabled={disabled}
          onClick={() => onChange(o.v)}
        >{o.label}</button>
      ))}
    </div>
  )
}

export default function ConstraintForm({ value, onChange, onGenerate, loading, hideGenerate, disabled, generateLabel }: Props) {
  const q = value
  const locked = !!disabled
  const summaryRef = useRef<HTMLDivElement>(null)

  const patchSite = (partial: Partial<QuestionnaireData['site']>) => {
    if (locked) return
    onChange({ ...q, site: { ...q.site, ...partial } })
  }
  const patchHouse = (partial: Partial<QuestionnaireData['house']>) => {
    if (locked) return
    onChange({ ...q, house: { ...q.house, ...partial } })
  }
  const patchSpaces = (partial: Partial<QuestionnaireData['spaces']>) => {
    if (locked) return
    onChange({ ...q, spaces: { ...q.spaces, ...partial } })
  }
  const patchPrefs = (partial: Partial<QuestionnaireData['preferences']>) => {
    if (locked) return
    onChange({ ...q, preferences: { ...q.preferences, ...partial } })
  }

  const { unit } = useUnits()
  const validationIssues = useMemo(() => validateQuestionnaire(q, unit), [q, unit])
  const errors = validationIssues.filter(i => i.severity === 'error')
  const hasErrors = errors.length > 0

  const areaStep = livingAreaSliderStep(unit)
  const areaMin = Math.ceil(fromSquareMeters(LIVING_AREA_MIN_M2, unit) / areaStep) * areaStep
  const areaMax = Math.floor(fromSquareMeters(LIVING_AREA_MAX_M2, unit) / areaStep) * areaStep

  return (
    <div className="room-catalog">

      <div className="catalog-header">
        <h3 className="catalog-heading">Project brief</h3>
      </div>

      {hasErrors && (
        <div className="catalog-error-summary" role="alert" tabIndex={-1} ref={summaryRef} id="brief-errors">
          <h2>There is a problem</h2>
          <ul>
            {errors.map((issue, i) => (
              <li key={`${issue.field}-${i}`}>
                <a href={`#field-${issue.field}`}>{issue.message}</a>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Site */}
      <div className="catalog-section">
        <div className="catalog-section-title">Site</div>
        <div className="catalog-row">
          <span className="catalog-row-label">Lot Shape</span>
          <div className="catalog-row-right">
            <select
              id="field-lotShape"
              className="catalog-select"
              disabled={locked}
              value={q.site.lotShape}
              onChange={e => {
                const lotShape = e.target.value as LotShape
                patchSite({
                  lotShape,
                  ...(lotShape === 'square' ? { lotDepth: q.site.lotWidth } : {}),
                })
              }}
            >
              <option value="rectangle">Rectangle</option>
              <option value="square">Square</option>
              <option value="l_shape">L-Shape</option>
              <option value="irregular">Irregular</option>
            </select>
          </div>
        </div>
        <div className="catalog-row">
          <span className="catalog-row-label">Lot Width</span>
          <div className="catalog-row-right catalog-dimension-input">
            <MeasurementInput
              id="field-lotWidth"
              min={MIN_LOT_M}
              disabled={locked}
              value={q.site.lotWidth}
              onCommit={lotWidth => patchSite({
                lotWidth,
                ...(q.site.lotShape === 'square' ? { lotDepth: lotWidth } : {}),
              })}
            />
          </div>
        </div>
        <div className="catalog-row">
          <span className="catalog-row-label">Lot Depth</span>
          <div className="catalog-row-right catalog-dimension-input">
            <MeasurementInput
              id="field-lotDepth"
              min={MIN_LOT_M}
              value={q.site.lotDepth}
              disabled={locked || q.site.lotShape === 'square'}
              onCommit={lotDepth => patchSite({ lotDepth })}
            />
          </div>
        </div>
      </div>

      {/* House */}
      <div className="catalog-section">
        <div className="catalog-section-title">House</div>
        <div className="catalog-row">
          <span className="catalog-row-label">Number of Floors</span>
          <div className="catalog-row-right">
            <select
              id="field-floors"
              className="catalog-select"
              disabled={locked}
              value={q.house.floors}
              onChange={e => patchHouse({ floors: parseInt(e.target.value, 10) })}
            >
              <option value={1}>1</option>
              <option value={2}>2</option>
            </select>
          </div>
        </div>
        <div className="catalog-row">
          <span className="catalog-row-label" id="field-bedrooms">Bedrooms</span>
          <div className="catalog-row-right">
            <Stepper value={q.house.bedrooms} min={1} max={8} disabled={locked}
              onChange={v => patchHouse({ bedrooms: v })} />
          </div>
        </div>
        <div className="catalog-row">
          <span className="catalog-row-label">Bathrooms</span>
          <div className="catalog-row-right">
            <Stepper value={q.house.bathrooms} min={1} max={6} disabled={locked}
              onChange={v => patchHouse({ bathrooms: v })} />
          </div>
        </div>
        <div className="catalog-row catalog-row-full">
          <span className="catalog-row-label">Living area</span>
          <div className="catalog-size-control" style={{ flex: 1 }}>
            <input
              type="range" min={areaMin} max={areaMax} step={areaStep}
              aria-label={`Living area (${areaSymbol(unit)})`}
              disabled={locked}
              value={fromSquareMeters(q.house.livingAreaM2, unit)}
              onChange={e => {
                const v = Number(e.target.value)
                if (Number.isFinite(v)) patchHouse({ livingAreaM2: toSquareMeters(v, unit) })
              }}
              className="catalog-sqft-slider"
            />
            <AreaInput
              id="field-livingAreaM2"
              className="catalog-size-value"
              min={LIVING_AREA_MIN_M2}
              max={LIVING_AREA_MAX_M2}
              disabled={locked}
              value={q.house.livingAreaM2}
              onCommit={livingAreaM2 => patchHouse({ livingAreaM2 })}
            />
          </div>
        </div>
      </div>

      {/* Spaces */}
      <div className="catalog-section">
        <div className="catalog-section-title">Spaces</div>
        <div className="catalog-row">
          <span className="catalog-row-icon" aria-hidden><CookingPot size={16} /></span>
          <span className="catalog-row-label">Kitchen</span>
          <span className="catalog-row-size">included</span>
        </div>
        <div className="catalog-row">
          <span className="catalog-row-icon" aria-hidden><Couch size={16} /></span>
          <span className="catalog-row-label">Living Room</span>
          <span className="catalog-row-size">included</span>
        </div>
        <div className="catalog-row">
          <span className="catalog-row-icon" aria-hidden><Door size={16} /></span>
          <span className="catalog-row-label">Foyer</span>
          <span className="catalog-row-size">included</span>
        </div>
        <div className="catalog-row">
          <span className="catalog-row-icon" aria-hidden><Desktop size={16} /></span>
          <span className="catalog-row-label">Home Office</span>
          <div className="catalog-row-right">
            <button
              type="button"
              className={`catalog-toggle ${q.spaces.homeOffice ? 'on' : ''}`}
              aria-pressed={q.spaces.homeOffice}
              disabled={locked}
              onClick={() => patchSpaces({ homeOffice: !q.spaces.homeOffice })}
            >
              {q.spaces.homeOffice ? 'on' : '–'}
            </button>
          </div>
        </div>
        <div className="catalog-row catalog-row-full">
          <span className="catalog-row-icon" aria-hidden><WashingMachine size={16} /></span>
          <span className="catalog-row-label">Laundry</span>
          <div className="catalog-row-right">
            <LaundryRow value={q.spaces.laundry} disabled={locked} onChange={v => patchSpaces({ laundry: v })} />
          </div>
        </div>
        <div className="catalog-row catalog-row-full">
          <span className="catalog-row-icon" aria-hidden><Car size={16} /></span>
          <span className="catalog-row-label">Garage</span>
          <div className="catalog-row-right">
            <GarageRow value={q.spaces.garage} disabled={locked} onChange={v => patchSpaces({ garage: v })} />
          </div>
        </div>
        <div className="catalog-row catalog-row-full">
          <span className="catalog-row-icon" aria-hidden><Plant size={16} /></span>
          <span className="catalog-row-label">Outdoor Space</span>
          <div className="catalog-row-right">
            <OutdoorRow value={q.spaces.outdoor} disabled={locked} onChange={v => patchSpaces({ outdoor: v })} />
          </div>
        </div>
      </div>

      {/* Preferences */}
      <div className="catalog-section">
        <div className="catalog-section-title">Preferences</div>
        <div className="catalog-row catalog-row-full">
          <span className="catalog-row-label">Architectural Style</span>
        </div>
        <div className="catalog-style-grid">
          {ARCHITECTURAL_STYLES.map(s => (
            <button
              type="button"
              key={s.id}
              className={`catalog-style-card ${q.preferences.style === s.id ? 'active' : ''}`}
              aria-pressed={q.preferences.style === s.id}
              disabled={locked}
              onClick={() => patchPrefs({ style: s.id })}
            >
              <span className="catalog-style-card-label">{s.label}</span>
              <span className="catalog-style-card-hint">{s.hint}</span>
            </button>
          ))}
        </div>
        <div className="catalog-row">
          <span className="catalog-row-label">Open Plan</span>
          <div className="catalog-row-right">
            <button
              type="button"
              className={`catalog-toggle ${q.preferences.openPlan ? 'on' : ''}`}
              aria-pressed={q.preferences.openPlan}
              disabled={locked}
              onClick={() => patchPrefs({ openPlan: !q.preferences.openPlan })}
            >
              {q.preferences.openPlan ? 'on' : '–'}
            </button>
          </div>
        </div>
        <div className="catalog-row">
          <span className="catalog-row-label">Primary Suite</span>
          <div className="catalog-row-right">
            <button
              type="button"
              className={`catalog-toggle ${q.preferences.primarySuite ? 'on' : ''}`}
              aria-pressed={q.preferences.primarySuite}
              disabled={locked}
              onClick={() => patchPrefs({ primarySuite: !q.preferences.primarySuite })}
            >
              {q.preferences.primarySuite ? 'on' : '–'}
            </button>
          </div>
        </div>
        <div className="catalog-row">
          <span className="catalog-row-label">Formal Dining</span>
          <div className="catalog-row-right">
            <button
              type="button"
              className={`catalog-toggle ${q.preferences.formalDining ? 'on' : ''}`}
              aria-pressed={q.preferences.formalDining}
              disabled={locked}
              onClick={() => patchPrefs({ formalDining: !q.preferences.formalDining })}
            >
              {q.preferences.formalDining ? 'on' : '–'}
            </button>
          </div>
        </div>
        <div className="catalog-row">
          <span className="catalog-row-label">Ceiling Height</span>
          <div className="catalog-row-right">
            <select
              className="catalog-select"
              disabled={locked}
              value={q.preferences.ceilingHeight}
              onChange={e => patchPrefs({ ceilingHeight: e.target.value as CeilingHeight })}
            >
              <option value="standard">Standard</option>
              <option value="high">High</option>
              <option value="vaulted">Vaulted</option>
            </select>
          </div>
        </div>
      </div>

      {validationIssues.length > 0 && (
        <div className="catalog-validation">
          {validationIssues.map((issue, i) => (
            <div key={i} className={`catalog-validation-issue catalog-validation-${issue.severity}`}>
              <div className="catalog-validation-header">
                <span className="catalog-validation-icon" aria-hidden>
                  {issue.severity === 'error' ? <X size={14} /> : <Warning size={14} />}
                </span>
                <strong>{issue.message}</strong>
              </div>
              <p className="catalog-validation-detail">{issue.detail}</p>
            </div>
          ))}
        </div>
      )}

      {!hideGenerate && (
      <div className="catalog-generate">
        <button
          className="catalog-generate-btn"
          onClick={onGenerate}
          disabled={loading || hasErrors || disabled}
          title={hasErrors ? 'Fix errors above before generating' : ''}
        >
          {loading
            ? <><span className="catalog-spinner" /> Generating…</>
            : <><Sparkle size={16} weight="fill" aria-hidden /> {generateLabel || 'Generate Floor Plan'}</>
          }
        </button>
      </div>
      )}

    </div>
  )
}
