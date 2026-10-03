import axios from 'axios'
import { FloorPlan } from '../types/floorplan'
import { normalizeFloorPlan } from '../units/legacy'
import type { MeasurementUnit } from '../units/measurement'

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

export async function exportDxf(plan: FloorPlan, unit: MeasurementUnit = 'm'): Promise<void> {
  const response = await api.post(
    '/export/dxf',
    { floor_plan: plan, unit },
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

export async function exportPdf(plan: FloorPlan, unit: MeasurementUnit = 'm'): Promise<void> {
  const response = await api.post(
    '/export/pdf',
    { floor_plan: plan, unit },
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

export async function fetchDesignScore(plan: FloorPlan): Promise<ScoreResult> {
  const { data } = await api.post('/score', { floor_plan: plan })
  return data
}

export async function sendChatMessage(
  plan: FloorPlan,
  messages: ChatMsg[]
): Promise<{ reply: string; updated_plan: FloorPlan | null }> {
  const { data } = await api.post('/chat', { floor_plan: plan, messages })
  return { ...data, updated_plan: normalizeFloorPlan(data.updated_plan ?? null) }
}

// ── types returned by API ────────────────────────────────────────────────────

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
