import type { Point2D, SceneDocument, Wall } from '../types'
import { cloneScene, touchScene } from './clone'
import { NODE_EPS, dist, nodeIdOf, quantize, wallLength } from './geometry'

export function assignJunctions(scene: SceneDocument, eps = NODE_EPS): SceneDocument {
  const next = cloneScene(scene)
  const nodes = new Map<string, string>()
  let n = 0
  function idFor(p: Point2D): string {
    const key = quantize(p, eps)
    let id = nodes.get(key)
    if (!id) {
      id = `j${n++}`
      nodes.set(key, id)
    }
    return id
  }
  for (const wall of next.walls) {
    wall.metadata = {
      ...(wall.metadata || {}),
      startNodeId: idFor(wall.start),
      endNodeId: idFor(wall.end),
    }
  }
  return touchScene(next)
}

export function bootstrapWallsFromRooms(scene: SceneDocument): SceneDocument {
  if (scene.walls.length > 0) return scene
  const next = cloneScene(scene)
  const floorId = next.floorData[0]?.id || 'floor-1'
  const height = next.floorData[0]?.height || 2.74
  const segs = new Map<string, { wall: Wall }>()

  function keyFor(a: Point2D, b: Point2D): string {
    const k1 = quantize(a)
    const k2 = quantize(b)
    return k1 < k2 ? `${k1}|${k2}` : `${k2}|${k1}`
  }

  let i = 0
  for (const room of next.rooms) {
    const poly = room.polygon
    if (!poly || poly.length < 3) continue
    for (let p = 0; p < poly.length; p++) {
      const a = poly[p]
      const b = poly[(p + 1) % poly.length]
      if (dist(a, b) < NODE_EPS) continue
      const key = keyFor(a, b)
      const existing = segs.get(key)
      if (existing) {
        if (!existing.wall.roomIds.includes(room.id)) existing.wall.roomIds.push(room.id)
        existing.wall.type = existing.wall.roomIds.length > 1 ? 'interior' : 'exterior'
        continue
      }
      const wall: Wall = {
        id: `boot-w${i++}`,
        floorId,
        type: 'exterior',
        start: { ...a },
        end: { ...b },
        thickness: 0.15,
        height,
        roomIds: [room.id],
        openingIds: [],
        metadata: { source: 'bootstrap' },
      }
      segs.set(key, { wall })
    }
  }

  next.walls = [...segs.values()].map(s => s.wall).filter(w => wallLength(w) > NODE_EPS)
  const byRoom = new Map<string, string[]>()
  for (const wall of next.walls) {
    for (const rid of wall.roomIds) {
      const list = byRoom.get(rid) || []
      list.push(wall.id)
      byRoom.set(rid, list)
    }
  }
  for (const room of next.rooms) {
    room.wallIds = byRoom.get(room.id) || []
  }
  if (next.floorData[0]) {
    next.floorData[0].wallIds = next.walls.map(w => w.id)
  }
  return assignJunctions(touchScene(next))
}
