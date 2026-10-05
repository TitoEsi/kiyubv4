import { describe, expect, it } from 'vitest'
import {
  canApprove,
  canComment,
  canEditDesign,
  canGenerate,
  canManageAccounts,
  canOpenArchitectCanvas,
  canPublish,
  canResolveComment,
  canRestoreVersion,
  canSelectCandidate,
  canSubmitReview,
  canViewAudit,
  canViewDrafts,
  canViewProject,
} from './permissions'

const client = { id: 'c1', role: 'CLIENT' as const }
const architect = { id: 'a1', role: 'ARCHITECT' as const, approved: true }
const admin = { id: 'm1', role: 'ADMIN' as const }
const assigned = { id: 'p1', client_id: 'c1', architect_id: 'a1', status: 'IN_PROGRESS' }

describe('workflow permissions', () => {
  it('clients never edit design', () => {
    expect(canEditDesign(client, assigned)).toBe(false)
  })

  it('admin views every project and its drafts but never edits, generates, comments, approves, or publishes', () => {
    const ready = { ...assigned, has_floor_plan: true }
    expect(canViewProject(admin, { id: 'p2', client_id: 'x', architect_id: 'y' })).toBe(true)
    expect(canViewDrafts(admin, ready)).toBe(true)
    expect(canEditDesign(admin, ready)).toBe(false)
    expect(canOpenArchitectCanvas(admin, ready)).toBe(false)
    expect(canGenerate(admin, ready)).toBe(false)
    expect(canComment(admin, ready)).toBe(false)
    expect(canSelectCandidate(admin, ready)).toBe(false)
    expect(canApprove(admin, { ...ready, status: 'FOR_CHECKING' })).toBe(false)
    expect(canPublish(admin, { ...ready, status: 'APPROVED' })).toBe(false)
    expect(canSubmitReview(admin, ready)).toBe(false)
    expect(canRestoreVersion(admin, ready)).toBe(false)
    expect(canResolveComment(admin, ready)).toBe(false)
  })

  it('only admin manages accounts', () => {
    expect(canManageAccounts(admin)).toBe(true)
    expect(canManageAccounts(architect)).toBe(false)
    expect(canManageAccounts(client)).toBe(false)
    expect(canViewAudit(admin)).toBe(true)
  })

  it('clients cannot see drafts; the assigned architect can', () => {
    expect(canViewDrafts(client, assigned)).toBe(false)
    expect(canViewDrafts(architect, assigned)).toBe(true)
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

  it('lets clients view their own project audit', () => {
    expect(canViewAudit(client)).toBe(true)
    expect(canViewAudit(architect)).toBe(true)
  })

  it('lets the assigned client send IN_PROGRESS work for checking', () => {
    expect(canSubmitReview(client, assigned)).toBe(false)
    expect(canSubmitReview(client, { ...assigned, has_floor_plan: true })).toBe(true)
    expect(canSubmitReview(client, { ...assigned, has_floor_plan: true, status: 'FOR_CHECKING' })).toBe(false)
    expect(canSubmitReview(architect, assigned)).toBe(true)
    expect(canSubmitReview(architect, { ...assigned, status: 'FOR_CHECKING' })).toBe(true)
  })
})
