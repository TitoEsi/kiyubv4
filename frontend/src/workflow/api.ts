import axios from 'axios'
import { FloorPlan } from '../types/floorplan'
import { QuestionnaireData } from '../types/questionnaire'

const BASE_URL = import.meta.env.VITE_API_URL
  ? `${import.meta.env.VITE_API_URL}/api`
  : '/api'

const api = axios.create({ baseURL: BASE_URL })

api.interceptors.request.use(config => {
  const token = localStorage.getItem('kiyub_token')
  if (token) {
    config.headers = config.headers || {}
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

export interface WorkflowUser {
  id: string
  email: string
  role: 'CLIENT' | 'ARCHITECT' | 'MAIN_ADMIN' | 'IT_PERSONNEL'
  approved: boolean
}

export interface Project {
  id: string
  name: string
  client_id: string | null
  architect_id: string | null
  status: string
  created_at?: string | null
  updated_at?: string | null
  client_email?: string | null
  has_floor_plan?: boolean
  generation_status?: 'idle' | 'running' | 'failed' | 'completed' | string
  client_comment_count?: number
}

export interface Candidate {
  id: string
  revision_id: string
  selected_by_client: boolean
  floor_plan: FloorPlan
  scene_document: Record<string, unknown>
  source_type: string
}

export interface Revision {
  id: string
  version: number
  source_type: string
  is_current?: boolean
  floor_plan?: FloorPlan
  scene_document?: Record<string, unknown>
}

export interface Comment {
  id: string
  body: string
  author_id: string
  author_email?: string | null
  author_role?: string | null
  created_at: string | null
  object_id?: string | null
  x?: number | null
  y?: number | null
  revision_id?: string | null
}

export interface Notification {
  id: string
  kind: string
  message: string
  project_id: string | null
  read: boolean
  created_at?: string | null
}

export interface Invitation {
  id: string
  project_id: string
  architect_id: string
  email: string
  status: 'PENDING' | 'ACCEPTED' | 'EXPIRED' | 'CANCELLED' | string
  expires_at?: string | null
  created_at?: string | null
  accepted_at?: string | null
  accepted_user_id?: string | null
  token?: string
  invite_url?: string
}

export interface ArchitectClientRow {
  email: string
  user_id: string | null
  project_id: string
  project_name: string
  invitation_status: string | null
  project_status: string
  last_activity: string | null
  created_at: string | null
  invitation_id: string | null
}

export async function login(email: string, password: string) {
  const { data } = await api.post('/auth/login', { email, password })
  return data as { token: string; user: WorkflowUser }
}

export async function signup(email: string, password: string, role: string, invitation_token?: string) {
  const { data } = await api.post('/auth/signup', { email, password, role, invitation_token })
  return data as { token?: string; user: WorkflowUser; message?: string }
}

export async function me() {
  const { data } = await api.get('/auth/me')
  return data as WorkflowUser
}

export async function listProjects() {
  const { data } = await api.get('/projects')
  return data as Project[]
}

export async function createProject(name: string, client_id?: string) {
  const { data } = await api.post('/projects', { name, client_id })
  return data as Project
}

export async function getProject(id: string) {
  const { data } = await api.get(`/projects/${id}`)
  return data as {
    project: Project
    document: {
      id: string
      stage: string
      current_revision_id: string | null
      working_scene_document?: unknown
      working_updated_at?: string | null
    }
    current_revision: Revision | null
    invitation?: Invitation | null
    permissions: Record<string, boolean>
  }
}

export async function assignProject(id: string, client_id: string) {
  const { data } = await api.put(`/projects/${id}/assign`, { client_id })
  return data as Project
}

export async function saveBrief(id: string, questionnaire: QuestionnaireData, specification: Record<string, unknown> = {}) {
  const { data } = await api.put(`/projects/${id}/brief`, { questionnaire, specification })
  return data
}

export async function getBrief(id: string) {
  const { data } = await api.get(`/projects/${id}/brief`)
  return data as { project: Project; questionnaire: QuestionnaireData; specification: Record<string, unknown> }
}

export async function generateProject(id: string) {
  const { data } = await api.post(`/projects/${id}/generate`, undefined, { timeout: 120_000 })
  return data as {
    job: { id: string; source_revision_id: string | null }
    candidates: Candidate[]
    stale_source: boolean
    generation?: { status?: string; validated?: boolean }
  }
}

export async function listCandidates(id: string) {
  const { data } = await api.get(`/projects/${id}/candidates`)
  return data as Candidate[]
}

export async function selectCandidate(projectId: string, candidateId: string) {
  const { data } = await api.post(`/projects/${projectId}/candidates/${candidateId}/select`)
  return data
}

export async function acceptCandidate(projectId: string, candidateId: string) {
  const { data } = await api.post(`/projects/${projectId}/candidates/${candidateId}/accept`)
  return data as Revision
}

export async function listRevisions(id: string) {
  const { data } = await api.get(`/projects/${id}/revisions`)
  return data as Revision[]
}

export async function getRevision(id: string) {
  const { data } = await api.get(`/revisions/${id}`)
  return data as Revision
}

export async function saveDesign(
  revisionId: string,
  floor_plan: FloorPlan,
  expected_revision_id?: string,
  scene_document?: unknown,
) {
  const { data } = await api.put(`/revisions/${revisionId}/design`, {
    floor_plan,
    expected_revision_id,
    scene_document,
  })
  return data as Revision
}

export async function saveWorkingDesign(projectId: string, scene_document: unknown) {
  const { data } = await api.put(`/projects/${projectId}/working-design`, { scene_document })
  return data as { working_updated_at: string | null }
}

export async function listComments(id: string) {
  const { data } = await api.get(`/projects/${id}/comments`)
  return data as Comment[]
}

export async function addComment(
  id: string,
  payload: string | { body: string; object_id?: string | null; x?: number | null; y?: number | null },
) {
  const body = typeof payload === 'string' ? { body: payload } : payload
  const { data } = await api.post(`/projects/${id}/comments`, body)
  return data as Comment
}

export async function patchComment(
  projectId: string,
  commentId: string,
  patch: { body?: string; object_id?: string | null; x?: number | null; y?: number | null },
) {
  const { data } = await api.patch(`/projects/${projectId}/comments/${commentId}`, patch)
  return data as Comment
}

export async function deleteComment(projectId: string, commentId: string) {
  await api.delete(`/projects/${projectId}/comments/${commentId}`)
}

export async function submitReview(id: string) {
  const { data } = await api.post(`/projects/${id}/submit-review`)
  return data as Project
}

export async function requestRevision(id: string) {
  const { data } = await api.post(`/projects/${id}/request-revision`)
  return data as Project
}

export async function resumeProject(id: string) {
  const { data } = await api.post(`/projects/${id}/resume`)
  return data as Project
}

export async function clientApprove(id: string) {
  const { data } = await api.post(`/projects/${id}/client-approve`)
  return data
}

export async function architectApprove(id: string) {
  const { data } = await api.post(`/projects/${id}/architect-approve`)
  return data as Project
}

export async function publishProject(id: string) {
  const { data } = await api.post(`/projects/${id}/publish`)
  return data as Revision
}

export async function listNotifications() {
  const { data } = await api.get('/notifications')
  return data as Notification[]
}

export async function markNotificationRead(id: string) {
  await api.post(`/notifications/${id}/read`)
}

export async function listAudit(projectId?: string) {
  const { data } = await api.get('/audit', { params: projectId ? { project_id: projectId } : undefined })
  return data as Array<{ id: string; event_type: string; created_at: string | null; metadata: Record<string, unknown> }>
}

export async function listAccounts() {
  const { data } = await api.get('/accounts')
  return data as WorkflowUser[]
}

export async function patchAccount(userId: string, patch: { approved?: boolean; role?: string }) {
  const { data } = await api.patch(`/accounts/${userId}`, patch)
  return data as WorkflowUser
}

export async function inviteClient(projectId: string, email: string, resend = false) {
  const { data } = await api.post(`/projects/${projectId}/invitations`, { email, resend })
  return data as Invitation
}

export async function listProjectInvitations(projectId: string) {
  const { data } = await api.get(`/projects/${projectId}/invitations`)
  return data as Invitation[]
}

export async function cancelInvitation(id: string) {
  const { data } = await api.post(`/invitations/${id}/cancel`)
  return data as Invitation
}

export async function getInvitationByToken(token: string) {
  const { data } = await api.get(`/invitations/by-token/${token}`)
  return data as {
    email: string
    project_name: string | null
    status: string
    expires_at: string | null
    needs_registration: boolean
  }
}

export async function acceptInvitation(token: string) {
  const { data } = await api.post(`/invitations/by-token/${token}/accept`)
  return data as { invitation: Invitation; project: Project | null }
}

export async function listArchitectClients() {
  const { data } = await api.get('/architect/clients')
  return data as ArchitectClientRow[]
}

export interface Inquiry {
  id: string
  name: string
  email: string
  message: string
  created_at: string | null
}

export async function submitInquiry(payload: { name: string; email: string; message: string }) {
  const { data } = await api.post('/inquiries', payload)
  return data as Inquiry
}

export async function listInquiries() {
  const { data } = await api.get('/inquiries')
  return data as Inquiry[]
}
