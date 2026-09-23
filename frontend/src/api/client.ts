import axios from 'axios'
import { Constraints, FloorPlan } from '../types/floorplan'

const BASE_URL = import.meta.env.VITE_API_URL
  ? `${import.meta.env.VITE_API_URL}/api`
  : '/api'

const api = axios.create({ baseURL: BASE_URL })

export async function generatePlans(constraints: Constraints): Promise<FloorPlan[]> {
  const { data } = await api.post('/generate', constraints)
  return data.plans
}

export async function exportDxf(plan: FloorPlan): Promise<void> {
  const response = await api.post(
    '/export/dxf',
    { floor_plan: plan },
    { responseType: 'blob' }
  )
  const url = URL.createObjectURL(response.data)
  const a = document.createElement('a')
  a.href = url
  a.download = `${plan.name.replace(/\s+/g, '_')}.dxf`
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
}

export async function exportPdf(plan: FloorPlan): Promise<void> {
  const response = await api.post(
    '/export/pdf',
    { floor_plan: plan },
    { responseType: 'blob' }
  )
  if (response.status >= 400) {
    throw new Error('PDF export failed')
  }
  const url = URL.createObjectURL(response.data)
  const a = document.createElement('a')
  a.href = url
  a.download = `${plan.name.replace(/\s+/g, '_')}.pdf`
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
}

export async function fetchCostEstimate(plan: FloorPlan, region: string): Promise<CostResult> {
  const { data } = await api.post('/cost', { floor_plan: plan, region })
  return data
}

export async function fetchDesignScore(plan: FloorPlan): Promise<ScoreResult> {
  const { data } = await api.post('/score', { floor_plan: plan })
  return data
}

export async function fetchCostRegions(): Promise<string[]> {
  const { data } = await api.get('/cost/regions')
  return data.regions
}

export async function sendChatMessage(
  plan: FloorPlan,
  messages: ChatMsg[]
): Promise<{ reply: string; updated_plan: FloorPlan | null }> {
  const { data } = await api.post('/chat', { floor_plan: plan, messages })
  return data
}

// ── types returned by API ────────────────────────────────────────────────────

export interface CostRoomRow {
  room: string
  type: string
  sqft: number
  low: number
  mid: number
  high: number
}

export interface CostResult {
  region: string
  rooms: CostRoomRow[]
  foundation: { low: number; mid: number; high: number }
  roof:       { low: number; mid: number; high: number }
  mep:        { low: number; mid: number; high: number }
  total:      { low: number; mid: number; high: number }
  per_sqft:   { low: number; mid: number; high: number }
}

export interface ScoreResult {
  scores: {
    adjacency: number
    natural_light: number
    circulation: number
    privacy: number
    efficiency: number
  }
  overall: number
  grade: string
  insights: string[]
}

export interface ChatMsg {
  role: 'user' | 'assistant'
  content: string
}

// ── MOE API ──────────────────────────────────────────────────────────────────

export interface MOEValidationError {
  type?: string
  room?: string
  message: string
  severity?: string
}

export interface MOEResult {
  plans: FloorPlan[]
  expert_weights: Record<string, number>
  confidence: number
  irc_compliant: boolean
  applied_constraints?: Constraints
  status?: 'valid' | 'infeasible' | 'generation_error' | 'fallback'
  validated?: boolean
  reason?: string
  reason_code?: string
  conflicts?: Array<Record<string, string>>
  validation_errors?: MOEValidationError[]
  quality_score?: {
    overall: number
    categories: Record<string, number>
    note: string
    residual?: Record<string, unknown>
    circulation?: Record<string, unknown>
    building_mass?: Record<string, unknown> | null
    site_open_space_area?: number
    building_residual_area?: number
    clusters?: Record<string, unknown>
    mass_occupancy_ratio?: number
    mass_fill?: Record<string, unknown>
    furniture_clearance_score?: number
    door_clearance_score?: number
    circulation_clearance_score?: number
    fixture_clearance_score?: number
    room_usability_score?: number
    usability_issues?: Array<Record<string, unknown>>
  } | null
  selected_strategy?: string | null
  strategy_evaluations?: Array<{
    strategy: string
    valid: boolean
    quality_score?: number | null
  }>
  generation_debug?: Record<string, unknown>
}

export interface ExpertWeightsResult {
  expert_weights: Record<string, number>
  expert_names: string[]
  confidence: number
}

export interface AuthResult {
  api_key: string
  tier: string
  message: string
}

export interface UsageResult {
  tier: string
  generations_today: number
  daily_limit: number | string
  total_generations: number
  total_exports: number
  total_chats: number
  variants_per_request: number
}

const GENERATE_TIMEOUT_MS = 120_000

export async function generatePlansMOE(
  constraints: Constraints,
  apiKey?: string
): Promise<MOEResult> {
  const headers: Record<string, string> = {}
  if (apiKey) headers['X-API-Key'] = apiKey
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), GENERATE_TIMEOUT_MS)
  console.log('[KIYUB API] calling /generate/moe')
  console.log('[KIYUB API] fetch start')
  try {
    const response = await api.post('/generate/moe', constraints, {
      headers,
      signal: controller.signal,
    })
    console.log('[KIYUB API] response received status=' + response.status)
    const data = response.data as MOEResult
    console.log(
      '[KIYUB API] response JSON received',
      data?.status,
      'plans',
      data?.plans?.length,
    )
    return data
  } catch (err: unknown) {
    const axiosErr = err as { code?: string; name?: string; message?: string }
    const aborted =
      axiosErr?.code === 'ERR_CANCELED' ||
      axiosErr?.name === 'CanceledError' ||
      axiosErr?.name === 'AbortError' ||
      controller.signal.aborted
    if (aborted) {
      console.log('[KIYUB API] fetch error Generation request timed out.')
      throw new Error('Generation request timed out.')
    }
    console.log('[KIYUB API] fetch error', axiosErr?.message || err)
    throw err
  } finally {
    clearTimeout(timer)
  }
}

export async function getExpertWeights(
  constraints: Constraints
): Promise<ExpertWeightsResult> {
  const { data } = await api.post('/moe/experts', constraints)
  return data
}

export async function registerApiKey(
  email: string = '',
  tier: string = 'free'
): Promise<AuthResult> {
  const { data } = await api.post('/auth/register', { email, tier })
  return data
}

export async function getUsage(apiKey: string): Promise<UsageResult> {
  const { data } = await api.get('/auth/usage', {
    headers: { 'X-API-Key': apiKey },
  })
  return data
}
