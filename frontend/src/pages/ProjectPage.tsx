import { useEffect, useMemo, useRef, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import ConstraintForm from '../components/ConstraintForm'
import FloorPlanEditor from '../components/FloorPlanEditor'
import FloorPlanGallery from '../components/FloorPlanGallery'
import ArchitectCanvas from '../components/ArchitectCanvas'
import { questionnaireToSpecification } from '../converters/questionnaire-to-specification'
import { validateQuestionnaire } from '../converters/validate-questionnaire'
import { FloorPlan } from '../types/floorplan'
import { initialQuestionnaire, QuestionnaireData } from '../types/questionnaire'
import type { SceneDocument } from '../scene-graph/types'
import { loadLiveScene } from '../scene-graph/edit/load-scene'
import { sceneDocumentToFloorPlan } from '../scene-graph/adapters/scene-document-to-floorplan'
import { useAuth } from '../workflow/auth'
import { useUnits } from '../units/UnitsProvider'
import { roleHome } from '../workflow/paths'
import {
  acceptCandidate,
  addComment,
  architectApprove,
  Candidate,
  clientApprove,
  Comment,
  deleteComment,
  generateProject,
  getBrief,
  getProject,
  getRevision,
  Invitation,
  listCandidates,
  listComments,
  listRevisions,
  patchComment,
  Project,
  publishProject,
  resumeProject,
  Revision,
  saveBrief,
  saveDesign,
  saveWorkingDesign,
  selectCandidate,
  submitReview,
} from '../workflow/api'
import { canEditDesign, canOpenArchitectCanvas, canSubmitReview } from '../workflow/permissions'
import { clientVisibleScene } from '../workflow/reviewScene'
import { displayNameFromEmail } from '../workflow/displayName'
import { clientCommentCountLabel, commentRoleLabel } from '../components/planAnnotations'
import ConfirmDialog from '../components/ConfirmDialog'
import WorkflowShell from './WorkflowShell'

function generationError(err: unknown): string {
  const ax = err as { code?: string; name?: string; response?: { status?: number; data?: { detail?: unknown } } }
  if (ax.code === 'ECONNABORTED' || ax.name === 'CanceledError' || ax.name === 'AbortError') {
    return 'Generation request timed out.'
  }
  if (ax.response?.status === 422 && ax.response.data?.detail && typeof ax.response.data.detail === 'object') {
    const detail = ax.response.data.detail as { validation_errors?: Array<{ message: string; detail: string }> }
    if (detail.validation_errors) {
      return detail.validation_errors.map(i => `${i.message}\n${i.detail}`).join('\n\n')
    }
  }
  if (typeof ax.response?.data?.detail === 'string') return ax.response.data.detail
  return 'Generation failed'
}

export default function ProjectPage() {
  const { projectId } = useParams()
  const { user } = useAuth()
  const { unit } = useUnits()
  const [project, setProject] = useState<Project | null>(null)
  const [questionnaire, setQuestionnaire] = useState<QuestionnaireData>(initialQuestionnaire)
  const [candidates, setCandidates] = useState<Candidate[]>([])
  const [comments, setComments] = useState<Comment[]>([])
  const [revisions, setRevisions] = useState<Revision[]>([])
  const [currentPlan, setCurrentPlan] = useState<FloorPlan | null>(null)
  const [currentRevisionId, setCurrentRevisionId] = useState<string | null>(null)
  const [selectedGallery, setSelectedGallery] = useState<FloorPlan | null>(null)
  const [scene, setScene] = useState<SceneDocument | null>(null)
  const [submittedScene, setSubmittedScene] = useState<SceneDocument | null>(null)
  const [submittedRevisionId, setSubmittedRevisionId] = useState<string | null>(null)
  const [workingSaved, setWorkingSaved] = useState(false)
  const [formalVersion, setFormalVersion] = useState<number | null>(null)
  const workingCopyRef = useRef<unknown>(null)
  const [invitation, setInvitation] = useState<Invitation | null>(null)
  const [canvasOpen, setCanvasOpen] = useState(false)
  const [selectedAnnotationId, setSelectedAnnotationId] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [commentBody, setCommentBody] = useState('')
  const [stage, setStage] = useState('CLIENT_BRIEF')
  const [dirty, setDirty] = useState(false)
  const [unvalidatedPreview, setUnvalidatedPreview] = useState(false)
  const [pendingDeleteId, setPendingDeleteId] = useState<string | null>(null)
  const [confirmReview, setConfirmReview] = useState(false)
  const [reviewSent, setReviewSent] = useState(false)
  const errorRef = useRef<HTMLDivElement>(null)
  const autosaveTimer = useRef<number | null>(null)
  const acceptingRef = useRef(false)
  const sceneSourceRef = useRef<string | null>(null)

  const actor = user ? { id: user.id, role: user.role, approved: user.approved } : null
  const editable = !!(actor && project && canEditDesign(actor, project))
  const isClient = user?.role === 'CLIENT'
  const isArchitect = user?.role === 'ARCHITECT'
  const isStaff = user?.role === 'MAIN_ADMIN' || user?.role === 'IT_PERSONNEL'
  const home = isArchitect ? '/architect/projects' : roleHome(user?.role)
  const floorPlanReady = project?.has_floor_plan === true
  const generating = project?.generation_status === 'running'
  const architectCanOpen = !!(actor && project && canOpenArchitectCanvas(actor, project))
  const clientCommentCount = project?.client_comment_count ?? comments.filter(c => c.author_role === 'CLIENT').length

  async function refresh() {
    if (!projectId) return
    const detail = await getProject(projectId)
    setProject(detail.project)
    setStage(detail.document.stage)
    setCurrentRevisionId(detail.document.current_revision_id)
    const visible = clientVisibleScene(detail)
    setSubmittedScene(visible.scene)
    setSubmittedRevisionId(visible.revisionId)
    if (visible.floorPlan) {
      setCurrentPlan(visible.floorPlan)
    } else if (detail.current_revision?.floor_plan) {
      setCurrentPlan(detail.current_revision.floor_plan)
    }
    if (detail.current_revision?.version != null) {
      setFormalVersion(detail.current_revision.version)
    }
    if (isArchitect) {
      workingCopyRef.current = detail.document.working_scene_document ?? null
    } else {
      workingCopyRef.current = null
    }
    const brief = await getBrief(projectId)
    if (brief.questionnaire && Object.keys(brief.questionnaire).length) {
      setQuestionnaire({
        ...brief.questionnaire,
        house: { ...initialQuestionnaire.house, ...brief.questionnaire.house },
      })
    }
    setCandidates(await listCandidates(projectId))
    setComments(await listComments(projectId))
    setRevisions(await listRevisions(projectId))
    setInvitation(detail.invitation || null)
  }

  useEffect(() => {
    setCanvasOpen(false)
    setSelectedAnnotationId(null)
    setScene(null)
    setSubmittedScene(null)
    setSubmittedRevisionId(null)
    sceneSourceRef.current = null
    workingCopyRef.current = null
    setWorkingSaved(false)
    refresh().catch(e => setError(String(e)))
  }, [projectId])

  useEffect(() => {
    if (isArchitect && architectCanOpen && floorPlanReady) setCanvasOpen(true)
  }, [isArchitect, architectCanOpen, floorPlanReady])

  useEffect(() => {
    if (error) errorRef.current?.focus()
  }, [error])

  const galleryPlans = useMemo(
    () => candidates.map(c => ({ ...c.floor_plan, id: c.id, name: c.floor_plan?.name || 'Candidate' })),
    [candidates],
  )

  async function persistBrief() {
    if (!projectId) return
    const spec = questionnaireToSpecification(questionnaire)
    await saveBrief(projectId, questionnaire, spec as unknown as Record<string, unknown>)
  }

  async function onGenerate() {
    if (!projectId) return
    const issues = validateQuestionnaire(questionnaire, unit)
    if (issues.some(i => i.severity === 'error')) {
      setError(issues.filter(i => i.severity === 'error').map(i => `${i.message}\n${i.detail}`).join('\n\n'))
      return
    }
    setLoading(true)
    setError(null)
    setUnvalidatedPreview(false)
    try {
      await persistBrief()
      const result = await generateProject(projectId)
      const gen = result.generation as { status?: string; validated?: boolean } | undefined
      setUnvalidatedPreview(gen?.status === 'fallback' || gen?.validated === false)
      setSelectedGallery(null)
      await refresh()
    } catch (err: unknown) {
      setError(generationError(err))
    } finally {
      setLoading(false)
    }
  }

  async function onSelectCandidate(plan: FloorPlan) {
    if (!projectId) return
    setSelectedGallery(plan)
    if (isClient) {
      await selectCandidate(projectId, plan.id)
      await refresh()
    }
  }

  async function onAccept(candidateId: string) {
    if (!projectId) return
    const rev = await acceptCandidate(projectId, candidateId)
    setCurrentPlan(rev.floor_plan || null)
    setCurrentRevisionId(rev.id)
    setFormalVersion(rev.version)
    setDirty(false)
    await refresh()
  }

  function scheduleAutosave(next: SceneDocument) {
    setScene(next)
    setDirty(true)
    setWorkingSaved(false)
    if (!projectId || !editable) return
    if (autosaveTimer.current) window.clearTimeout(autosaveTimer.current)
    autosaveTimer.current = window.setTimeout(() => {
      saveWorkingDesign(projectId, next)
        .then(() => {
          setDirty(false)
          setWorkingSaved(true)
        })
        .catch(() => setError('Could not autosave working copy.'))
    }, 800)
  }

  async function onSaveRevision() {
    if (!currentRevisionId || !scene) return
    const floorPlan = sceneDocumentToFloorPlan(scene)
    const rev = await saveDesign(currentRevisionId, floorPlan, currentRevisionId, scene)
    setCurrentPlan(rev.floor_plan || floorPlan)
    setCurrentRevisionId(rev.id)
    setFormalVersion(rev.version)
    setDirty(false)
    setWorkingSaved(false)
    await refresh()
  }

  async function onSaveDesign() {
    await onSaveRevision()
  }

  async function onArchitectSubmitReview() {
    if (!projectId) return
    if (autosaveTimer.current) {
      window.clearTimeout(autosaveTimer.current)
      autosaveTimer.current = null
    }
    if (!scene) {
      setError('A current SceneDocument is required to submit for review.')
      return
    }
    await saveWorkingDesign(projectId, scene)
    await submitReview(projectId, {
      scene_document: scene,
      floor_plan: sceneDocumentToFloorPlan(scene),
    })
    await refresh()
  }

  async function onAddComment() {
    if (!projectId || !commentBody.trim()) return
    await addComment(projectId, commentBody.trim())
    setCommentBody('')
    await refresh()
  }

  const annotationHandlers = !isStaff && projectId ? {
    comments,
    currentUserId: user?.id,
    allowAnnotations: true,
    selectedAnnotationId,
    onSelectAnnotation: setSelectedAnnotationId,
    onAddAnnotation: async (payload: { body: string; x: number; y: number; object_id: string | null }) => {
      await addComment(projectId, payload)
      await refresh()
    },
    onUpdateAnnotation: async (id: string, body: string) => {
      await patchComment(projectId, id, { body })
      await refresh()
    },
    onDeleteAnnotation: (id: string) => {
      setPendingDeleteId(id)
    },
    onMoveAnnotation: async (id: string, x: number, y: number) => {
      await patchComment(projectId, id, { x, y })
      await refresh()
    },
  } : {}

  const viewPlan = selectedGallery || currentPlan
  const readOnly = !editable || isStaff
  const canSendReview = !!(actor && project && canSubmitReview(actor, project))

  useEffect(() => {
    const plan = currentPlan || selectedGallery
    if (!plan) return
    const key = `${currentPlan?.id || selectedGallery?.id || ''}:${currentRevisionId || 'gallery'}:${submittedRevisionId || ''}`
    if (sceneSourceRef.current === key && scene) return
    sceneSourceRef.current = key
    const loaded = loadLiveScene(plan, undefined, {
      projectId,
      existing: (isArchitect && workingCopyRef.current) || submittedScene,
    })
    setScene(loaded)
    setWorkingSaved(!!(isArchitect && currentPlan && workingCopyRef.current))
  }, [currentPlan, selectedGallery, currentRevisionId, submittedRevisionId, submittedScene, isArchitect, projectId, scene])

  useEffect(() => {
    if (!isArchitect || !canvasOpen || currentPlan || !candidates.length || acceptingRef.current) return
    const pick = candidates.find(c => c.selected_by_client) || candidates[0]
    acceptingRef.current = true
    onAccept(pick.id).finally(() => { acceptingRef.current = false })
  }, [isArchitect, canvasOpen, currentPlan, candidates])

  useEffect(() => () => {
    if (autosaveTimer.current) window.clearTimeout(autosaveTimer.current)
  }, [])

  function galleryPlanFromCandidate(c: Candidate): FloorPlan {
    return { ...c.floor_plan, id: c.id, name: c.floor_plan?.name || 'Candidate' }
  }

  function openArchitectCanvas() {
    if (!architectCanOpen) return
    if (!currentPlan && !selectedGallery && candidates.length) {
      const pick = candidates.find(c => c.selected_by_client) || candidates[0]
      setSelectedGallery(galleryPlanFromCandidate(pick))
    }
    setCanvasOpen(true)
  }

  return (
    <WorkflowShell status={project?.status} flush>
      {error && (
        <div className="error-msg" role="alert" tabIndex={-1} ref={errorRef}>{error}</div>
      )}
      <div className="wf-project">
        <aside className="wf-side">
          {isArchitect && project && (
            <section className="studio-status-strip">
              <p className="studio-meta">Project status</p>
              <h2 className="studio-tile-name">{project.name}</h2>
              <p className="studio-tile-meta">
                Client: {project.client_email ? displayNameFromEmail(project.client_email) : invitation?.email || 'Not assigned'}
              </p>
              <ul className="studio-status-list">
                <li>
                  <span>Client</span>
                  <span>{project.client_id || invitation?.status === 'ACCEPTED' ? 'Invitation accepted' : invitation?.status === 'PENDING' ? 'Invitation pending' : 'Not invited'}</span>
                </li>
                <li>
                  <span>Floor plan</span>
                  <span>{generating ? 'Generating' : floorPlanReady ? 'Generated' : 'Not generated'}</span>
                </li>
                <li>
                  <span>Architect review</span>
                  <span>{floorPlanReady ? project.status.replace(/_/g, ' ') : 'Waiting for client'}</span>
                </li>
              </ul>
              <button
                type="button"
                className="catalog-generate-btn"
                disabled={!architectCanOpen || generating || canvasOpen}
                onClick={openArchitectCanvas}
              >
                {canvasOpen ? 'Canvas open' : 'Open canvas'}
              </button>
              {!architectCanOpen && (
                <p className="wf-hint">
                  {generating
                    ? 'The client is generating a floor plan. Canvas stays locked until it is ready.'
                    : 'Open canvas stays disabled until the client generates a floor plan.'}
                </p>
              )}
            </section>
          )}
          {!isStaff && !isArchitect && (
            <ConstraintForm
              value={questionnaire}
              onChange={setQuestionnaire}
              onGenerate={onGenerate}
              loading={loading}
              disabled={!isClient}
              hideGenerate={!isClient}
              generateLabel="Generate AI candidates"
            />
          )}
          {isStaff && <p className="wf-hint">Staff can inspect status and comments, not the canvas.</p>}

          <div className="wf-actions">
            {isArchitect && candidates[0] && (
              <button type="button" className="back-btn" onClick={() => onAccept(candidates.find(c => c.selected_by_client)?.id || candidates[0].id)}>
                Accept candidate
              </button>
            )}
            {isArchitect && canSendReview && (
              <button type="button" className="back-btn" onClick={() => { onArchitectSubmitReview().catch(e => setError(String(e))) }}>Submit for checking</button>
            )}
            {isClient && canSendReview && !reviewSent && (
              <button type="button" className="catalog-generate-btn" onClick={() => setConfirmReview(true)}>Send to Review</button>
            )}
            {isClient && (project?.status === 'FOR_CHECKING' || reviewSent) && (
              <button type="button" className="back-btn" disabled>Sent for Review</button>
            )}
            {editable && project?.status === 'FOR_REVISION' && (
              <button type="button" className="back-btn" onClick={async () => { await resumeProject(projectId!); await refresh() }}>Resume design</button>
            )}
            {isClient && project?.status === 'FOR_CHECKING' && (
              <button type="button" className="catalog-generate-btn" onClick={async () => { await clientApprove(projectId!); await refresh() }}>Approve design</button>
            )}
            {isArchitect && project?.status === 'FOR_CHECKING' && (
              <button type="button" className="catalog-generate-btn" onClick={async () => { await architectApprove(projectId!); await refresh() }}>Architect approve</button>
            )}
            {isArchitect && project?.status === 'APPROVED' && (
              <button type="button" className="catalog-generate-btn" onClick={async () => { await publishProject(projectId!); await refresh() }}>Publish</button>
            )}
            <Link className="back-btn" to={home}>Back to projects</Link>
          </div>

          {isArchitect && canvasOpen && architectCanOpen && (
            <div>
              <h3>Revisions</h3>
              <ul className="wf-list">
                {revisions.map(r => (
                  <li key={r.id}>
                    <button type="button" className="wf-link" onClick={async () => {
                      const full = await getRevision(r.id)
                      if (full.floor_plan) {
                        setCurrentPlan(full.floor_plan)
                        setCurrentRevisionId(full.id)
                        setFormalVersion(full.version)
                        setSelectedGallery(null)
                        setDirty(false)
                        workingCopyRef.current = full.scene_document ?? null
                        sceneSourceRef.current = null
                      }
                    }}>
                      v{r.version} {r.source_type}{r.is_current ? ' (current)' : ''}
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          )}

          <div>
            <h3>Comments</h3>
            <ul className="wf-list">
              {comments.map(c => (
                <li key={c.id}>
                  <button
                    type="button"
                    className={`wf-link ${selectedAnnotationId === c.id ? 'active' : ''}`}
                    onClick={() => {
                      setSelectedAnnotationId(c.id)
                      if (isArchitect && architectCanOpen) openArchitectCanvas()
                    }}
                  >
                    <span className="studio-meta">{commentRoleLabel(c.author_role)}</span>
                    {' '}
                    {displayNameFromEmail(c.author_email || 'client')}: {c.body}
                    {c.x != null && c.y != null ? <span className="wf-hint"> · pin</span> : null}
                  </button>
                </li>
              ))}
            </ul>
            {!isStaff && (
              <div className="wf-inline wf-comment-composer">
                <label htmlFor="project-comment" className="sr-only">Comment</label>
                <input id="project-comment" value={commentBody} onChange={e => setCommentBody(e.target.value)} placeholder="Comment" />
                <button type="button" className="back-btn" onClick={onAddComment}>Post</button>
              </div>
            )}
            {!isStaff && <p className="wf-hint">Use Note on the 2D plan to pin a sticky comment.</p>}
          </div>
        </aside>
        <main className="wf-main" aria-busy={loading}>
          {unvalidatedPreview && galleryPlans.length > 0 && (
            <div className="unvalidated-banner" role="status">
              UNVALIDATED DEVELOPMENT PREVIEW — not a validated KIYUB floor plan.
            </div>
          )}
          {isStaff ? (
            <div className="wf-empty">No canvas for admin or IT roles.</div>
          ) : isArchitect && (!architectCanOpen || !canvasOpen) ? (
            <div className="studio-waiting">
              {generating ? (
                <>
                  <h2>Generating floor plan</h2>
                  <p>The client has started generation. Canvas access stays locked until a floor plan is stored on this project.</p>
                </>
              ) : floorPlanReady ? (
                <>
                  <h2>Floor plan ready</h2>
                  <p>The client has generated a floor plan and it is ready for architectural review.</p>
                  <p className="studio-tile-meta">
                    {clientCommentCountLabel(clientCommentCount, true)}
                  </p>
                  <button type="button" className="catalog-generate-btn" onClick={openArchitectCanvas}>
                    Open canvas
                  </button>
                </>
              ) : (
                <>
                  <h2>Waiting for client</h2>
                  <p>
                    The client has been invited to this project but has not generated a floor plan yet.
                    Once they complete generation, you can open the canvas and review the design.
                  </p>
                  <button type="button" className="catalog-generate-btn" disabled>
                    Open canvas
                  </button>
                </>
              )}
            </div>
          ) : isArchitect && canvasOpen && scene ? (
            <ArchitectCanvas
              scene={scene}
              onSceneChange={setScene}
              onCommit={scheduleAutosave}
              onSaveRevision={() => { onSaveRevision().catch(e => setError(String(e))) }}
              workingSaved={workingSaved}
              dirty={dirty}
              formalLabel={formalVersion != null ? `Formal v${formalVersion}` : undefined}
              editingEnabled={editable}
              {...annotationHandlers}
            />
          ) : isArchitect && canvasOpen ? (
            <div className="wf-empty">Loading canvas…</div>
          ) : selectedGallery && !currentPlan ? (
            <FloorPlanEditor
              plan={selectedGallery}
              onUpdate={() => undefined}
              readOnly
              projectId={projectId}
              revisionId={candidates.find(c => c.id === selectedGallery.id)?.revision_id}
              role={user?.role}
              {...annotationHandlers}
            />
          ) : viewPlan && (currentPlan || selectedGallery) && !isStaff ? (
            <FloorPlanEditor
              plan={currentPlan && editable ? currentPlan : viewPlan}
              onUpdate={plan => { if (editable) { setCurrentPlan(plan); setDirty(true) } }}
              readOnly={readOnly || !currentPlan || !editable}
              projectId={projectId}
              revisionId={submittedRevisionId || currentRevisionId || undefined}
              role={user?.role}
              dirty={dirty}
              onSave={onSaveDesign}
              existingScene={submittedScene}
              {...annotationHandlers}
            />
          ) : (
            <FloorPlanGallery
              plans={galleryPlans}
              loading={loading}
              onSelect={onSelectCandidate}
              selectedId={selectedGallery?.id}
            />
          )}
        </main>
      </div>
      {pendingDeleteId && (
        <ConfirmDialog
          title="Delete comment"
          body="Remove this pinned comment from the drawing?"
          confirmLabel="Delete"
          danger
          onCancel={() => setPendingDeleteId(null)}
          onConfirm={async () => {
            if (!projectId || !pendingDeleteId) return
            const id = pendingDeleteId
            setPendingDeleteId(null)
            try {
              await deleteComment(projectId, id)
              setSelectedAnnotationId(cur => cur === id ? null : cur)
              await refresh()
            } catch (err: unknown) {
              const ax = err as { response?: { status?: number; data?: { detail?: string } } }
              const detail = ax.response?.data?.detail
              if (ax.response?.status === 403) setError(detail || 'You cannot delete this comment.')
              else if (ax.response?.status === 404) setError(detail || 'Comment not found.')
              else setError(detail || 'Could not delete comment.')
            }
          }}
        />
      )}
      {confirmReview && (
        <ConfirmDialog
          title="Send to Review"
          body="Send this floor plan to your architect for checking?"
          confirmLabel="Send to Review"
          onCancel={() => setConfirmReview(false)}
          onConfirm={async () => {
            if (!projectId) return
            setConfirmReview(false)
            try {
              await submitReview(projectId)
              setReviewSent(true)
              await refresh()
            } catch (err: unknown) {
              const ax = err as { response?: { status?: number; data?: { detail?: string } } }
              if (ax.response?.status === 409) {
                setError(ax.response.data?.detail || 'Already submitted for checking')
                await refresh()
              } else {
                setError(ax.response?.data?.detail || 'Could not send for review.')
              }
            }
          }}
        />
      )}
    </WorkflowShell>
  )
}
