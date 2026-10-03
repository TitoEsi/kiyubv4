import { FloorPlan } from '../types/floorplan'
import FloorPlanPreview from './FloorPlanPreview'
import { useFormat } from '../units/UnitsProvider'

interface Props {
  plans: FloorPlan[]
  loading: boolean
  onSelect: (plan: FloorPlan) => void
  selectedId?: string | null
}

const CARD_LABELS = ['A', 'B', 'C', 'D', 'E', 'F']

const STEPS = [
  { n: '1', text: 'Set the project site, rooms, and living area' },
  { n: '2', text: 'AI generates multiple plan variants for you' },
  { n: '3', text: 'Pick a starting point and explore in 2D & 3D' },
  { n: '4', text: 'Refine rooms, view walkthrough, export CAD' },
]

function bedroomCount(plan: FloorPlan) {
  return plan.rooms.filter(r =>
    r.type === 'bedroom' || r.type === 'master_bedroom' ||
    r.type === 'primary_bedroom' || r.name.toLowerCase().includes('bed')
  ).length
}
function bathroomCount(plan: FloorPlan) {
  return plan.rooms.filter(r =>
    r.type === 'bathroom' || r.type === 'ensuite_bathroom' ||
    r.type === 'half_bath' || r.name.toLowerCase().includes('bath')
  ).length
}
const _UNCONDITIONED = new Set(['garage', 'patio', 'deck', 'rear_patio', 'outdoor_living', 'front_porch'])
function livingAreaM2(plan: FloorPlan) {
  return plan.rooms.filter(r => !_UNCONDITIONED.has(r.type)).reduce((s, r) => s + r.width * r.height, 0)
}

export default function FloorPlanGallery({ plans, loading, onSelect, selectedId }: Props) {
  const fmt = useFormat()
  if (loading) {
    return (
      <div className="charrette-loading" aria-busy="true" aria-live="polite">
        <div className="charrette-loading-icon">
          <span className="charrette-spinner" />
        </div>
        <p className="charrette-loading-title">Generating candidates…</p>
      </div>
    )
  }

  if (plans.length === 0) {
    return (
      <div className="charrette-empty">
        <div className="studio-login-plate charrette-empty-plate" aria-hidden>
          <svg viewBox="0 0 320 220" fill="none">
            <rect x="1" y="1" width="318" height="218" stroke="currentColor" strokeOpacity="0.2" />
            <rect x="28" y="36" width="168" height="148" stroke="currentColor" strokeWidth="1.2" />
            <rect x="196" y="36" width="96" height="72" stroke="currentColor" strokeWidth="1.2" />
            <rect x="196" y="108" width="96" height="76" stroke="currentColor" strokeWidth="1.2" />
          </svg>
        </div>
        <h2 className="charrette-empty-title">Choose a starting point</h2>
        <p className="charrette-empty-sub">Set the project site, rooms, and living area, then generate candidates.</p>
        <ol className="charrette-legend">
          {STEPS.map(s => (
            <li key={s.n} className="charrette-legend-item">
              <span className="studio-index">{s.n.padStart(2, '0')}</span>
              <span>{s.text}</span>
            </li>
          ))}
        </ol>
      </div>
    )
  }

  return (
    <div className="charrette-board">
      <div className="charrette-header">
        <h2 className="charrette-title">Choose a Starting Point</h2>
        <p className="charrette-subtitle">Select one of these floor plan variations to begin evolving your design</p>
      </div>

      <div className="charrette-grid">
        {plans.map((plan, idx) => {
          const beds = bedroomCount(plan)
          const baths = bathroomCount(plan)
          const area = fmt.area(livingAreaM2(plan))
          const label = CARD_LABELS[idx] ?? String(idx + 1)
          const fp = fmt.dims(plan.totalWidth, plan.totalHeight)
          const pressed = selectedId === plan.id

          return (
            <button
              type="button"
              key={plan.id}
              className="charrette-card"
              aria-pressed={pressed}
              onClick={() => onSelect(plan)}
            >
              <div className="charrette-card-label">{label}</div>
              <div className="charrette-card-preview">
                <FloorPlanPreview plan={plan} width={280} height={200} />
              </div>
              <div className="charrette-card-footer">
                <div className="charrette-card-stats">
                  <span className="studio-meta">Scheme {label}</span>
                  <span className="charrette-stat">{area}</span>
                  <span className="charrette-stat-sep">·</span>
                  {beds > 0 && <span className="charrette-stat">{beds} bed</span>}
                  {beds > 0 && baths > 0 && <span className="charrette-stat-sep">·</span>}
                  {baths > 0 && <span className="charrette-stat">{baths} bath</span>}
                </div>
                <div className="charrette-card-dims">{fp} · {plan.rooms.length} rooms</div>
              </div>
            </button>
          )
        })}
      </div>
    </div>
  )
}
