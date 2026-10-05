import { useEffect, useMemo, useRef, useState } from 'react'
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom'
import ConstraintForm from '../components/ConstraintForm'
import FloorPlanEditor from '../components/FloorPlanEditor'
import FloorPlanGallery from '../components/FloorPlanGallery'
import ArchitectCanvas from '../components/ArchitectCanvas'
import { questionnaireToSpecification } from '../converters/questionnaire-to-specification'
import { validateQuestionnaire } from '../converters/validate-questionnaire'
import { FloorPlan } from '../types/floorplan'
import { initialQuestionnaire, QuestionnaireData } from '../types/questionnaire'
import type { SceneDocument } from '../scene-graph/types'
import { isSceneDocument, loadLiveScene } from '../scene-graph/edit/load-scene'
import type { SiteLot } from '../scene-graph/site/site-context'
import { sceneDocumentToFloorPlan } from '../scene-graph/adapters/scene-document-to-floorplan'
import { useAuth } from '../workflow/auth'
import { useUnits } from '../units/UnitsProvider'
import { roleHome } from '../workflow/paths'
import {
  addComment,
  architectApprove,
  Candidate,
  clientApprove,
  Comment,
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
  replyToComment,
  resolveComment,
  restoreRevision,
  resumeProject,
  Revision,
  saveBrief,
  saveWorkingDesign,
  selectCandidate,
  submitReview,
} from '../workflow/api'
import {
  canEditDesign,
  canOpenArchitectCanvas,
  canResolveComment,
  canRestoreVersion,
  canSubmitReview,
} from '../workflow/permissions'
import { clientVisibleScene } from '../workflow/reviewScene'
import { buildPublishedExport } from '../workflow/publishedExport'
import { statusLabel } from '../workflow/statusLabels'
import { displayNameFromEmail } from '../workflow/displayName'
import { buildThreads, formatStamp } from '../workflow/commentThreads'
import { versionSourceLabel } from '../workflow/versionLabels'
import { clientCommentCountLabel } from '../components/planAnnotations'
import type { CommentActions } from '../components/CommentThread'
import SidebarComments from '../components/SidebarComments'
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

/** The lot only counts when the saved brief has one; questionnaire defaults are not a lot. */
function lotFromBrief(questionnaire: Partial<QuestionnaireData> | null | undefined): SiteLot | null {
  const site = questionnaire?.site
  const width = Number(site?.lotWidth)
  const depth = Number(site?.lotDepth)
  if (!(width > 0) || !(depth > 0)) return null
  return { width, depth, shape: site?.lotShape }
}

export default function ProjectPage() {
  const { projectId } = useParams()
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()
  const versionParam = searchParams.get('version')
  const { user } = useAuth()
  const { unit } = useUnits()
  const [project, setProject] = useState<Project | null>(null)
  const [questionnaire, setQuestionnaire] = useState<QuestionnaireData>(initialQuestionnaire)
  const [briefLot, setBriefLot] = useState<SiteLot | null>(null)
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
  const [adminDraft, setAdminDraft] = useState<SceneDocument | null>(null)
  const [invitation, setInvitation] = useState<Invitation | null>(null)
  const [canvasOpen, setCanvasOpen] = useState(false)
  const [selectedAnnotationId, setSelectedAnnotationId] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [stage, setStage] = useState('CLIENT_BRIEF')
  const [dirty, setDirty] = useState(false)
  const [unvalidatedPreview, setUnvalidatedPreview] = useState(false)
  const [viewingRevision, setViewingRevision] = useState<Revision | null>(null)
  const [pendingRestore, setPendingRestore] = useState<Revision | null>(null)
  const [restoring, setRestoring] = useState(false)
  const [confirmReview, setConfirmReview] = useState(false)
  const [reviewSent, setReviewSent] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [submitNotice, setSubmitNotice] = useState<string | null>(null)
  const errorRef = useRef<HTMLDivElement>(null)
  const autosaveTimer = useRef<number | null>(null)
  const sceneSourceRef = useRef<string | null>(null)

  const actor = user ? { id: user.id, role: user.role, approved: user.approved } : null
  const editable = !!(actor && project && canEditDesign(actor, project))
  const isClient = user?.role === 'CLIENT'
  const isArchitect = user?.role === 'ARCHITECT'
  const isAdmin = user?.role === 'ADMIN'
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
    if (detail.project.status === 'PUBLISHED' && !buildPublishedExport({
      status: detail.project.status,
      projectId: detail.project.id,
      projectName: detail.project.name,
      clientEmail: detail.project.client_email,
      scene: visible.scene,
      revisionId: visible.revisionId,
      version: detail.current_revision?.version ?? null,
      publishedAt: detail.current_revision?.created_at ?? null,
      lot: null,
      questionnaire: initialQuestionnaire,
    })) {
      console.error('Published floor plan is unavailable.', {
        projectId,
        revisionId: detail.document.current_revision_id,
      })
    }
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
    const draft = isAdmin ? detail.document.working_scene_document : null
    setAdminDraft(isSceneDocument(draft) ? draft : null)
    const brief = await getBrief(projectId)
    if (brief.questionnaire && Object.keys(brief.questionnaire).length) {
      setQuestionnaire({
        ...brief.questionnaire,
        house: { ...initialQuestionnaire.house, ...brief.questionnaire.house },
      })
    }
    setBriefLot(lotFromBrief(brief.questionnaire))
    setCandidates(await listCandidates(projectId))
    setComments(await listComments(projectId))
    setRevisions(await listRevisions(projectId))
    setInvitation(detail.invitation || null)
  }

  useEffect(() => {
    setCanvasOpen(false)
    setSelectedAnnotationId(null)
    setViewingRevision(null)
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

  function scheduleAutosave(next: SceneDocument) {
    setScene(next)
    setDirty(true)
    setWorkingSaved(false)
    setSubmitNotice(null)
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

  async function onArchitectSubmitReview() {
    if (!projectId || submitting) return
    if (autosaveTimer.current) {
      window.clearTimeout(autosaveTimer.current)
      autosaveTimer.current = null
    }
    if (!scene) {
      setError('A current SceneDocument is required to submit for review.')
      return
    }
    setSubmitting(true)
    setSubmitNotice(null)
    try {
      await saveWorkingDesign(projectId, scene)
      setDirty(false)
      setWorkingSaved(true)
      const result = await submitReview(projectId, {
        scene_document: scene,
        floor_plan: sceneDocumentToFloorPlan(scene),
      })
      await refresh()
      const v = result.version != null ? `v${result.version}` : 'the last version'
      setSubmitNotice(result.created ? `Sent ${v} for review.` : `No changes since ${v}; nothing new sent.`)
    } finally {
      setSubmitting(false)
    }
  }

  /** Runs a comment mutation, then reloads only the comment list. */
  function commentOp(op: () => Promise<unknown>, failure: string) {
    if (!projectId) return
    op()
      .then(async () => setComments(await listComments(projectId)))
      .catch((err: unknown) => {
        const ax = err as { response?: { data?: { detail?: unknown } } }
        const detail = ax.response?.data?.detail
        setError(typeof detail === 'string' ? detail : failure)
      })
  }

  const commentActions: CommentActions | undefined = !isAdmin && projectId ? {
    currentUserId: user?.id,
    canResolve: !!(actor && project && canResolveComment(actor, project)),
    canComment: true,
    onReply: (parentId, body) => commentOp(() => replyToComment(projectId, parentId, body), 'Could not post reply.'),
    onEdit: (id, body) => commentOp(() => patchComment(projectId, id, { body }), 'Could not edit comment.'),
    onResolve: (id, resolved, note) => commentOp(() => resolveComment(projectId, id, resolved, note), 'Could not update comment.'),
    onAddGeneral: body => commentOp(() => addComment(projectId, body), 'Could not post comment.'),
  } : undefined

  const annotationHandlers = commentActions && projectId ? {
    comments,
    commentActions,
    allowAnnotations: true,
    selectedAnnotationId,
    onSelectAnnotation: setSelectedAnnotationId,
    onAddAnnotation: (payload: { body: string; x: number; y: number; object_id: string | null }) => {
      commentOp(() => addComment(projectId, payload), 'Could not post comment.')
    },
  } : {}

  useEffect(() => {
    if (!versionParam) return
    openVersion({ id: versionParam } as Revision)
    setSearchParams(p => { p.delete('version'); return p }, { replace: true })
  }, [versionParam])

  async function openVersion(rev: Pick<Revision, 'id'>) {
    try {
      const full = await getRevision(rev.id)
      setViewingRevision(full)
      setSelectedAnnotationId(null)
    } catch {
      setError('Could not open this version.')
    }
  }

  async function onRestoreVersion(rev: Revision) {
    if (restoring) return
    if (autosaveTimer.current) {
      window.clearTimeout(autosaveTimer.current)
      autosaveTimer.current = null
    }
    setRestoring(true)
    try {
      const restored = await restoreRevision(rev.id)
      setViewingRevision(null)
      setSelectedGallery(null)
      setDirty(false)
      workingCopyRef.current = restored.scene_document ?? null
      sceneSourceRef.current = null
      await refresh()
      setSubmitNotice(`Version ${rev.version} restored as Version ${restored.version}. Send to review when ready.`)
    } catch (err: unknown) {
      const ax = err as { response?: { data?: { detail?: unknown } } }
      const detail = ax.response?.data?.detail
      setError(typeof detail === 'string' ? detail : 'Could not restore this version.')
    } finally {
      setRestoring(false)
    }
  }

  const canRestore = !!(actor && project && canRestoreVersion(actor, project))
  const latestVersion = revisions.reduce((m, r) => Math.max(m, r.version), 0)

  const viewPlan = selectedGallery || currentPlan
  const readOnly = !editable || isAdmin
  const adminPlan = useMemo(
    () => (isAdmin ? (adminDraft ? sceneDocumentToFloorPlan(adminDraft) : viewPlan) : null),
    [isAdmin, adminDraft, viewPlan],
  )
  const canSendReview = !!(actor && project && canSubmitReview(actor, project))
  const publishedExport = useMemo(() => buildPublishedExport({
    status: project?.status,
    projectId: project?.id || projectId || '',
    projectName: project?.name || 'Project',
    clientEmail: project?.client_email,
    invitationEmail: invitation?.email,
    scene: submittedScene,
    revisionId: submittedRevisionId,
    version: formalVersion,
    publishedAt: revisions.find(r => r.id === submittedRevisionId)?.created_at ?? null,
    lot: briefLot,
    questionnaire,
  }), [
    project?.status,
    project?.id,
    project?.name,
    project?.client_email,
    projectId,
    invitation?.email,
    submittedScene,
    submittedRevisionId,
    formalVersion,
    revisions,
    briefLot,
    questionnaire,
  ])

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
    if (!isArchitect || !canvasOpen || currentPlan || selectedGallery || !candidates.length) return
    const pick = candidates.find(c => c.selected_by_client) || candidates[0]
    setSelectedGallery(galleryPlanFromCandidate(pick))
  }, [isArchitect, canvasOpen, currentPlan, selectedGallery, candidates])

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
    <WorkflowShell status={statusLabel(project?.status) || undefined} flush>
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
                  <span>Status</span>
                  <span>{floorPlanReady ? statusLabel(project.status) : 'Waiting for client'}</span>
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
          {!isAdmin && !isArchitect && (
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
          {isAdmin && <p className="wf-hint">Admin view: inspect status, comments, versions, and the canvas. Editing is disabled.</p>}

          <div className="wf-actions">
            {isArchitect && canSendReview && (
              <button
                type="button"
                className="back-btn"
                disabled={submitting || !scene}
                onClick={() => { onArchitectSubmitReview().catch(e => setError(String(e))) }}
              >
                {submitting ? 'Sending…' : 'Send to review'}
              </button>
            )}
            {isArchitect && submitNotice && <p className="wf-hint" role="status">{submitNotice}</p>}
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
            {!(isArchitect && canvasOpen && scene) && <Link className="back-btn" to={home}>Back to projects</Link>}
          </div>

          {projectId && (
            <Link className="wf-link project-activity-link" to={`/projects/${projectId}/activity`}>Project Activity</Link>
          )}

          {revisions.length > 0 && (
            <section className="wf-versions" aria-label="Version history">
              <h3>Versions</h3>
              <ul className="wf-list">
                {[...revisions].sort((a, b) => b.version - a.version).map(r => (
                  <li key={r.id}>
                    <button
                      type="button"
                      className={`wf-link wf-version ${viewingRevision?.id === r.id ? 'active' : ''}`}
                      aria-current={viewingRevision?.id === r.id ? 'true' : undefined}
                      onClick={() => { openVersion(r) }}
                    >
                      <span>Version {r.version}{r.is_current ? ' (current)' : ''}</span>
                      <span className="wf-hint">{versionSourceLabel(r, revisions)}{r.created_at ? ` · ${formatStamp(r.created_at)}` : ''}</span>
                    </button>
                  </li>
                ))}
              </ul>
            </section>
          )}

          {isAdmin && (
            <SidebarComments threads={buildThreads(comments)} selectedId={selectedAnnotationId} onSelect={setSelectedAnnotationId} />
          )}
          {!isAdmin && <p className="wf-hint">Use Note on the 2D plan to pin a sticky comment. All comments are in the right sidebar.</p>}
        </aside>
        <main className="wf-main" aria-busy={loading}>
          {unvalidatedPreview && galleryPlans.length > 0 && (
            <div className="unvalidated-banner" role="status">
              UNVALIDATED DEVELOPMENT PREVIEW — not a validated KIYUB floor plan.
            </div>
          )}
          {viewingRevision?.floor_plan ? (
            <FloorPlanEditor
              key={viewingRevision.id}
              plan={viewingRevision.floor_plan}
              lot={briefLot}
              onUpdate={() => undefined}
              readOnly
              projectId={projectId}
              revisionId={viewingRevision.id}
              role={user?.role}
              publishedExport={publishedExport}
              existingScene={(viewingRevision.scene_document as unknown as SceneDocument | undefined) ?? null}
              readOnlyBanner={
                <span className="version-banner">
                  <span>Viewing Version {viewingRevision.version} (read-only)</span>
                  {viewingRevision.version !== latestVersion && <span className="wf-hint"> · Latest is Version {latestVersion}</span>}
                  <button type="button" className="back-btn" onClick={() => setViewingRevision(null)}>Back to current</button>
                  {isArchitect && canRestore && (
                    <button type="button" className="catalog-generate-btn" disabled={restoring} onClick={() => setPendingRestore(viewingRevision)}>
                      {restoring ? 'Restoring…' : 'Restore as new version'}
                    </button>
                  )}
                </span>
              }
            />
          ) : isAdmin ? (
            adminPlan ? (
              <FloorPlanEditor
                key={`admin:${currentRevisionId || adminPlan.id || 'plan'}:${adminDraft ? 'draft' : 'current'}`}
                plan={adminPlan}
                lot={briefLot}
                onUpdate={() => undefined}
                readOnly
                projectId={projectId}
                revisionId={submittedRevisionId || currentRevisionId || undefined}
                role={user?.role}
              publishedExport={publishedExport}
                existingScene={adminDraft ?? submittedScene}
                readOnlyBanner={
                  <span className="version-banner">
                    <span>
                      {adminDraft ? "Viewing the architect's working draft" : 'Viewing the current design'} (view only, Admin)
                    </span>
                  </span>
                }
              />
            ) : galleryPlans.length > 0 ? (
              <FloorPlanGallery plans={galleryPlans} loading={false} onSelect={onSelectCandidate} selectedId={selectedGallery?.id} />
            ) : (
              <div className="wf-empty">No floor plan has been generated for this project yet.</div>
            )
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
              lot={briefLot}
              onSceneChange={setScene}
              onCommit={scheduleAutosave}
              onBack={() => navigate(home)}
              workingSaved={workingSaved}
              dirty={dirty}
              formalLabel={formalVersion != null ? `Formal v${formalVersion}` : undefined}
              editingEnabled={editable}
              publishedExport={publishedExport}
              {...annotationHandlers}
            />
          ) : isArchitect && canvasOpen ? (
            <div className="wf-empty">Loading canvas…</div>
          ) : selectedGallery && !currentPlan ? (
            <FloorPlanEditor
              plan={selectedGallery}
              lot={briefLot}
              onUpdate={() => undefined}
              readOnly
              projectId={projectId}
              revisionId={candidates.find(c => c.id === selectedGallery.id)?.revision_id}
              role={user?.role}
              publishedExport={publishedExport}
              {...annotationHandlers}
            />
          ) : viewPlan && (currentPlan || selectedGallery) ? (
            <FloorPlanEditor
              plan={currentPlan && editable ? currentPlan : viewPlan}
              lot={briefLot}
              onUpdate={plan => { if (editable) { setCurrentPlan(plan); setDirty(true) } }}
              readOnly={readOnly || !currentPlan || !editable}
              projectId={projectId}
              revisionId={submittedRevisionId || currentRevisionId || undefined}
              role={user?.role}
              publishedExport={publishedExport}
              dirty={dirty}
              existingScene={submittedScene}
              {...annotationHandlers}
            />
          ) : (
            <FloorPlanGallery
              plans={galleryPlans}
              loading={loading}
              onSelect={onSelectCandidate}
            />
          )}
        </main>
      </div>
      {pendingRestore && (
        <ConfirmDialog
          title={`Restore Version ${pendingRestore.version}`}
          body={`This creates Version ${latestVersion + 1} from Version ${pendingRestore.version} and loads it into your working draft. Version ${pendingRestore.version} is kept unchanged. Nothing is sent to the client until you choose Send to review.`}
          confirmLabel="Restore as new version"
          onCancel={() => setPendingRestore(null)}
          onConfirm={() => {
            const rev = pendingRestore
            setPendingRestore(null)
            onRestoreVersion(rev)
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
