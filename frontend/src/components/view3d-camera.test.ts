import { describe, expect, it } from 'vitest'
import {
  VIEW3D_SCALE,
  buildingBounds,
  viewCameraConfig,
  walkStartPosition,
} from './view3d-camera'
import type { FloorPlan } from '../types/floorplan'

const plan: Pick<FloorPlan, 'rooms' | 'totalWidth' | 'totalHeight'> = {
  totalWidth: 34,
  totalHeight: 16,
  rooms: [
    { id: 'r1', name: 'Living', type: 'living_room', x: 0, y: 0, width: 20, height: 16, color: '#ccc' },
    { id: 'r2', name: 'Bed', type: 'bedroom', x: 20, y: 0, width: 14, height: 16, color: '#ddd' },
  ],
}

const wallH = 9 * VIEW3D_SCALE

describe('view3d-camera', () => {
  it('centers bounds on the building', () => {
    const bounds = buildingBounds(plan)
    expect(bounds.cx).toBeCloseTo(17 * VIEW3D_SCALE)
    expect(bounds.cz).toBeCloseTo(8 * VIEW3D_SCALE)
    expect(bounds.spanX).toBeCloseTo(34 * VIEW3D_SCALE)
    expect(bounds.spanZ).toBeCloseTo(16 * VIEW3D_SCALE)
  })

  it('gives each mode a different camera kind or position', () => {
    const bounds = buildingBounds(plan)
    const walk = walkStartPosition(plan.rooms, wallH)
    const top = viewCameraConfig('topview', bounds, wallH)
    const dollhouse = viewCameraConfig('dollhouse', bounds, wallH)
    const walkCfg = viewCameraConfig('walkthrough', bounds, wallH, walk)
    const exterior = viewCameraConfig('exterior', bounds, wallH)

    expect(top.kind).toBe('orthographic')
    expect(dollhouse.kind).toBe('perspective')
    expect(walkCfg.kind).toBe('perspective')
    expect(exterior.kind).toBe('perspective')

    expect(top.position).not.toEqual(dollhouse.position)
    expect(dollhouse.position).not.toEqual(walkCfg.position)
    expect(walkCfg.position).not.toEqual(top.position)
    expect(exterior.position).not.toEqual(dollhouse.position)
  })

  it('aims top and dollhouse at the building center', () => {
    const bounds = buildingBounds(plan)
    const top = viewCameraConfig('topview', bounds, wallH)
    const dollhouse = viewCameraConfig('dollhouse', bounds, wallH)
    expect(top.target).toEqual([bounds.cx, 0, bounds.cz])
    expect(dollhouse.target).toEqual([bounds.cx, 0, bounds.cz])
  })

  it('sets top-view camera.up so smaller plan-y is screen-up', () => {
    const bounds = buildingBounds(plan)
    const top = viewCameraConfig('topview', bounds, wallH)
    expect(top.up).toEqual([0, 0, -1])
    expect(top.position[1]).toBeGreaterThan(top.target[1])
  })

  it('places walk at eye height in the first room', () => {
    const walk = walkStartPosition(plan.rooms, wallH)
    expect(walk[1]).toBeCloseTo(wallH * 0.62)
    expect(walk[0]).toBeCloseTo(10 * VIEW3D_SCALE)
    expect(walk[2]).toBeCloseTo(8 * VIEW3D_SCALE)
    const cfg = viewCameraConfig('walkthrough', buildingBounds(plan), wallH, walk)
    expect(cfg.position[1]).toBeCloseTo(wallH * 0.62)
    expect(cfg.kind).toBe('perspective')
  })
})
