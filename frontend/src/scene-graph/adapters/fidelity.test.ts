import { describe, expect, it } from 'vitest'
import { FEET_TO_METERS, floorPlanToSceneDocument } from './floorplan-to-scene-document'
import { sceneDocumentToFloorPlan } from './scene-document-to-floorplan'
import { FIDELITY_PLAN } from './fidelity.fixture'
import { fidelityReport, sceneRenderIds } from './scene-entities'
import { loadLiveScene } from '../edit/load-scene'
import { shapeXY, toWorld, validateSceneDocumentGeometry, wallYaw } from './scene-to-world'

const LOT = { lotWidth: 20, lotDepth: 14 }

describe('fidelity conversion', () => {
  it('preserves rooms, walls, openings, furniture, and L-polygon', () => {
    const scene = floorPlanToSceneDocument(FIDELITY_PLAN, LOT)
    expect(scene.rooms).toHaveLength(FIDELITY_PLAN.rooms.length)
    expect(scene.walls).toHaveLength(FIDELITY_PLAN.walls!.length)
    expect(scene.openings.map(o => o.id).sort()).toEqual(
      [...FIDELITY_PLAN.openings!.map(o => o.id), 'd-legacy'].sort(),
    )
    expect(scene.furniture).toHaveLength(FIDELITY_PLAN.furniture!.length)
    expect(scene.rooms.map(r => r.id).sort()).toEqual(FIDELITY_PLAN.rooms.map(r => r.id).sort())
    expect(scene.walls.map(w => w.id).sort()).toEqual(FIDELITY_PLAN.walls!.map(w => w.id).sort())
    expect(scene.furniture.map(f => f.id).sort()).toEqual(FIDELITY_PLAN.furniture!.map(f => f.id).sort())

    const living = scene.rooms.find(r => r.id === 'living')!
    expect(living.polygon.length).toBeGreaterThan(4)
    expect(living.metadata?.parts).toHaveLength(2)
    expect(scene.openings.find(o => o.id === 'door-entry')?.wallId).toBe('w-south')
    expect(scene.openings.find(o => o.id === 'win-bed')?.wallId).toBe('w-angle')
    expect(scene.openings.find(o => o.id === 'd-legacy')?.wallId).toBe('w-liv-kit')
    expect(scene.furniture.find(f => f.id === 'sofa-1')?.roomId).toBe('living')
    expect(scene.furniture.find(f => f.id === 'sofa-1')?.position.x).toBeCloseTo(4 * FEET_TO_METERS, 5)
    expect(scene.furniture.find(f => f.id === 'sofa-1')?.position.y).toBeCloseTo(3 * FEET_TO_METERS, 5)
    expect(living.polygon.some(p => Math.abs(p.x - 12 * FEET_TO_METERS) < 0.02 && Math.abs(p.y - 10 * FEET_TO_METERS) < 0.02)).toBe(true)

    const report = fidelityReport(FIDELITY_PLAN, scene)
    expect(report.every(row => row.inPlan && row.inScene)).toBe(true)
  })

  it('round-trips furniture and footprint parts', () => {
    const scene = floorPlanToSceneDocument(FIDELITY_PLAN, LOT)
    const back = sceneDocumentToFloorPlan(scene)
    expect(back.furniture).toHaveLength(2)
    expect(back.rooms.find(r => r.id === 'living')?.footprint?.parts.length).toBe(2)
    expect(back.rooms.find(r => r.id === 'living')?.footprint?.boundary?.length).toBeGreaterThan(4)
    expect(back.openings?.find(o => o.id === 'door-entry')?.wallId).toBe('w-south')
  })

  it('2D and 3D consume the same SceneDocument entity ids', () => {
    const scene = loadLiveScene(FIDELITY_PLAN, LOT)
    const ids = sceneRenderIds(scene)
    expect(ids.rooms).toEqual(scene.rooms.map(r => r.id).sort())
    expect(ids.walls).toEqual(scene.walls.map(w => w.id).sort())
    expect(ids.openings).toEqual(scene.openings.map(o => o.id).sort())
    expect(ids.furniture).toEqual(scene.furniture.map(f => f.id).sort())
    expect(ids.rooms).toContain('kitchen')
    expect(ids.rooms).toContain('living')
    expect(ids.rooms).toContain('bed1')
    expect(ids.furniture).toContain('sofa-1')
    expect(ids.openings).toContain('door-entry')
  })

  it('maps SceneDocument into one Three.js frame: yaw, floor Z, and bounds', () => {
    const scene = floorPlanToSceneDocument(FIDELITY_PLAN, LOT)
    const south = scene.walls.find(w => w.id === 'w-south')!
    const west = scene.walls.find(w => w.id === 'w-west')!
    expect(wallYaw(south)).toBeCloseTo(0, 5)
    expect(Math.abs(wallYaw(west))).toBeCloseTo(Math.PI / 2, 5)

    const kitchen = scene.rooms.find(r => r.id === 'kitchen')!
    const kitWall = scene.walls.find(w => w.id === 'w-liv-kit')!
    const wallZ = [toWorld(kitWall.start.x, kitWall.start.y).z, toWorld(kitWall.end.x, kitWall.end.y).z]
    for (const p of kitchen.polygon) {
      const xy = shapeXY(p.x, p.y)
      const afterRx = { x: xy.x, z: -xy.y }
      const world = toWorld(p.x, p.y)
      expect(afterRx.x).toBeCloseTo(world.x, 8)
      expect(afterRx.z).toBeCloseTo(world.z, 8)
      expect(Math.min(...wallZ) - 0.05).toBeLessThanOrEqual(afterRx.z)
      expect(afterRx.z).toBeLessThanOrEqual(Math.max(...wallZ) + 1.2)
    }

    const living = scene.rooms.find(r => r.id === 'living')!
    const parts = living.metadata?.parts as Array<{ x: number; y: number; width: number; height: number }>
    const livingWalls = scene.walls.filter(w => w.roomIds.includes('living'))
    let pMinX = Infinity, pMaxX = -Infinity, pMinZ = Infinity, pMaxZ = -Infinity
    for (const part of parts) {
      const a = toWorld(part.x, part.y)
      const b = toWorld(part.x + part.width, part.y + part.height)
      pMinX = Math.min(pMinX, a.x, b.x)
      pMaxX = Math.max(pMaxX, a.x, b.x)
      pMinZ = Math.min(pMinZ, a.z, b.z)
      pMaxZ = Math.max(pMaxZ, a.z, b.z)
    }
    let wMinX = Infinity, wMaxX = -Infinity, wMinZ = Infinity, wMaxZ = -Infinity
    for (const wall of livingWalls) {
      const a = toWorld(wall.start.x, wall.start.y)
      const b = toWorld(wall.end.x, wall.end.y)
      wMinX = Math.min(wMinX, a.x, b.x)
      wMaxX = Math.max(wMaxX, a.x, b.x)
      wMinZ = Math.min(wMinZ, a.z, b.z)
      wMaxZ = Math.max(wMaxZ, a.z, b.z)
    }
    expect(pMinX).toBeCloseTo(wMinX, 2)
    expect(pMaxX).toBeCloseTo(wMaxX, 2)
    expect(pMinZ).toBeCloseTo(wMinZ, 2)
    expect(pMaxZ).toBeCloseTo(wMaxZ, 2)

    const report = validateSceneDocumentGeometry(scene)
    expect(report.valid).toBe(true)
    expect(report.counts.rooms).toBe(scene.rooms.length)
    expect(report.counts.walls).toBe(scene.walls.length)
    expect(report.counts.openings).toBe(scene.openings.length)
    expect(report.counts.furniture).toBe(scene.furniture.length)
    expect(report.bounds.minZ).toBeGreaterThanOrEqual(-1e-6)
  })
})
