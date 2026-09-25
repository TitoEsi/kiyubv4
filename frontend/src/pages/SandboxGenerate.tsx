import { useEffect, useState } from 'react'
import { FloorPlan } from '../types/floorplan'
import { generatePlansMOE, MOEResult } from '../api/client'
import { floorPlanToSceneDocument } from '../scene-graph'
import { initialQuestionnaire, QuestionnaireData } from '../types/questionnaire'
import { questionnaireToSpecification } from '../converters/questionnaire-to-specification'
import { specificationToConstraints } from '../converters/specification-to-generation'
import { validateQuestionnaire } from '../converters/validate-questionnaire'
import ConstraintForm from '../components/ConstraintForm'
import FloorPlanGallery from '../components/FloorPlanGallery'
import FloorPlanEditor from '../components/FloorPlanEditor'
import WorkflowShell from './WorkflowShell'

/** Original generate-and-edit sandbox. Workflow lives on routed pages. */
export default function SandboxGenerate() {
  const [questionnaire, setQuestionnaire] = useState<QuestionnaireData>(initialQuestionnaire)
  const [plans, setPlans] = useState<FloorPlan[]>([])
  const [selected, setSelected] = useState<FloorPlan | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [unvalidatedPreview, setUnvalidatedPreview] = useState(false)

  useEffect(() => {
    console.log('[KIYUB] loading state changed:', loading)
  }, [loading])

  useEffect(() => {
    console.log('[KIYUB] plans state changed:', plans.length, plans.map(p => p.id))
  }, [plans])

  async function handleGenerate() {
    const issues = validateQuestionnaire(questionnaire)
    if (issues.some(i => i.severity === 'error')) {
      setError(issues.filter(i => i.severity === 'error').map(i => `${i.message}\n${i.detail}`).join('\n\n'))
      return
    }

    setLoading(true)
    setError(null)
    setUnvalidatedPreview(false)
    try {
      const spec = questionnaireToSpecification(questionnaire)
      const constraints = specificationToConstraints(spec)
      console.log('[KIYUB] generate started')
      console.log('[KIYUB] generation request:', constraints)
      console.log('[KIYUB] BEFORE generatePlansMOE')
      const result: MOEResult = await generatePlansMOE(constraints)
      console.log('[KIYUB] AFTER generatePlansMOE')
      console.log('[KIYUB] generation response status:', result?.status, 'validated:', result?.validated)
      console.log('[KIYUB] plan count:', result?.plans?.length)
      if (result.generation_debug) {
        console.log('[KIYUB] generation_debug', result.generation_debug)
      }
      const status = result.status ?? (result.plans?.length ? 'valid' : 'infeasible')

      if (status === 'infeasible') {
        setPlans([])
        setSelected(null)
        const code = result.reason_code ? `[${result.reason_code}] ` : ''
        setError(
          code +
          (result.reason || 'No valid floor plan found.') +
          '\n\nModify Requirements and adjust the questionnaire — your current values are kept.',
        )
        return
      }

      if (status === 'generation_error') {
        setPlans([])
        setSelected(null)
        setError(result.reason || 'Generation failed. No validated floor plan was produced.')
        return
      }

      if (!result.plans?.length) {
        setError('No valid floor plans were generated. Adjust the project requirements and try again.')
        return
      }

      setPlans(result.plans)
      setSelected(null)
      setUnvalidatedPreview(status === 'fallback' || result.validated === false)
      console.log('[KIYUB] received plans:', result.plans.length)
      try {
        const scene = floorPlanToSceneDocument(result.plans[0], constraints, {
          projectId: 'kiyub-v4-baseline',
        })
        console.log('[KIYUB] SceneDocument site', scene.site.width, '×', scene.site.depth, 'm')
        console.log('[KIYUB] SceneDocument rooms', scene.rooms.length, 'version', scene.version)
      } catch (sceneErr) {
        console.log('[KIYUB] SceneDocument conversion failed', sceneErr)
      }
    } catch (e: unknown) {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const axiosErr = e as any
      if (axiosErr?.response?.status === 422 && axiosErr?.response?.data?.detail?.validation_errors) {
        const issues = axiosErr.response.data.detail.validation_errors as Array<{severity: string; message: string; detail: string}>
        const lines = issues.map(i =>
          `${i.severity === 'error' ? '✕' : '⚠'} ${i.message}\n${i.detail}`
        )
        setError(lines.join('\n\n'))
      } else if (
        (e instanceof Error && e.message === 'Generation request timed out.') ||
        axiosErr?.code === 'ERR_CANCELED' ||
        axiosErr?.name === 'CanceledError' ||
        axiosErr?.name === 'AbortError'
      ) {
        setError('Generation request timed out.')
        setPlans([])
        setSelected(null)
      } else if (axiosErr?.code === 'ECONNABORTED' || axiosErr?.code === 'ERR_NETWORK' || axiosErr?.response?.status === 502) {
        setError(
          'The generation API did not respond. Confirm the backend is running on port 8002, then try again.',
        )
        setPlans([])
        setSelected(null)
      } else {
        const msg = e instanceof Error ? e.message : 'Generation failed'
        setError(msg)
      }
    } finally {
      console.log('[KIYUB] setting loading false')
      setLoading(false)
    }
  }

  function handleSelect(plan: FloorPlan) {
    setSelected(plan)
  }

  function handleUpdate(updated: FloorPlan) {
    setSelected(updated)
    setPlans(prev => prev.map(p => (p.id === updated.id ? updated : p)))
  }

  return (
    <WorkflowShell scratch flush>
      <div className="wf-project">
        <aside className="wf-side">
          <ConstraintForm
            value={questionnaire}
            onChange={setQuestionnaire}
            onGenerate={handleGenerate}
            loading={loading}
          />

          {error && (
            <>
              <div className="error-msg" role="alert">{error}</div>
              <button type="button" className="back-btn" onClick={() => setError(null)}>
                Modify Requirements
              </button>
            </>
          )}

          {selected && (
            <button type="button" className="back-btn" onClick={() => setSelected(null)}>
              Back to gallery
            </button>
          )}
        </aside>

        <main className="wf-main" aria-busy={loading}>
          {unvalidatedPreview && plans.length > 0 && (
            <div className="unvalidated-banner" role="status">
              UNVALIDATED DEVELOPMENT PREVIEW — not a validated KIYUB floor plan.
            </div>
          )}
          {selected ? (
            <FloorPlanEditor plan={selected} onUpdate={handleUpdate} />
          ) : (
            <FloorPlanGallery plans={plans} loading={loading} onSelect={handleSelect} />
          )}
        </main>
      </div>
    </WorkflowShell>
  )
}
