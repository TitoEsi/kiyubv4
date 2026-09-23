import { describe, expect, it } from 'vitest'
import {
  canEditDesign,
  canGenerate,
  canManageAccounts,
  canOpenArchitectCanvas,
  canPublish,
  canSelectCandidate,
  canSubmitReview,
  canViewProject,
} from './permissions'

const client = { id: 'c1', role: 'CLIENT' as const }
const architect = { id: 'a1', role: 'ARCHITECT' as const, approved: true }
const admin = { id: 'm1', role: 'MAIN_ADMIN' as const }
const assigned = { id: 'p1', client_id: 'c1', architect_id: 'a1', status: 'IN_PROGRESS' }

describe('workflow permissions', () => {
  it('clients never edit design', () => {
    expect(canEditDesign(client, assigned)).toBe(false)
  })

  it('admin and IT never edit design', () => {
    expect(canEditDesign(admin, assigned)).toBe(false)
    expect(canEditDesign({ id: 'i1', role: 'IT_PERSONNEL' }, assigned)).toBe(false)
  })

  it('architect can edit assigned unpublished work', () => {
    expect(canEditDesign(architect, assigned)).toBe(true)
    expect(canEditDesign(architect, { ...assigned, status: 'PUBLISHED' })).toBe(false)
  })

  it('client can generate and select on assigned project', () => {
    expect(canGenerate(client, assigned)).toBe(true)
    expect(canSelectCandidate(client, assigned)).toBe(true)
    expect(canPublish(client, assigned)).toBe(false)
  })

  it('architect canvas stays locked until a floor plan exists', () => {
    expect(canOpenArchitectCanvas(architect, assigned)).toBe(false)
    expect(canOpenArchitectCanvas(architect, { ...assigned, has_floor_plan: false })).toBe(false)
    expect(canOpenArchitectCanvas(architect, { ...assigned, has_floor_plan: true })).toBe(true)
    expect(canGenerate(architect, { ...assigned, has_floor_plan: false })).toBe(false)
    expect(canGenerate(architect, { ...assigned, has_floor_plan: true })).toBe(true)
  })

  it('lets the assigned client send IN_PROGRESS work for checking', () => {
    expect(canSubmitReview(client, assigned)).toBe(false)
    expect(canSubmitReview(client, { ...assigned, has_floor_plan: true })).toBe(true)
    expect(canSubmitReview(client, { ...assigned, has_floor_plan: true, status: 'FOR_CHECKING' })).toBe(false)
    expect(canSubmitReview(architect, assigned)).toBe(true)
  })
})
