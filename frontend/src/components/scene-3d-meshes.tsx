import { useMemo } from 'react'
import * as THREE from 'three'
import type { Furniture, Opening, Room, SceneDocument, Wall } from '../scene-graph/types'
import { wallLength, wallPointAtT } from '../scene-graph/edit/geometry'
import { openingT } from '../scene-graph/edit/opening-ops'
import {
  metersToWorld,
  sceneWorldBounds,
  shapeXY,
  toWorld,
  wallYaw,
} from '../scene-graph/adapters/scene-to-world'
import type { BuildingBounds } from './view3d-camera'

const WALL_COLOR = '#e2e6ec'

type Part = { x: number; y: number; width: number; height: number }

function roomPartsM(room: Room): Part[] {
  const raw = room.metadata?.parts
  if (Array.isArray(raw) && raw.length) {
    return raw as Part[]
  }
  return [{ x: room.position.x, y: room.position.y, width: room.dimensions.width, height: room.dimensions.height }]
}

function roomColor(room: Room): string {
  return typeof room.metadata?.color === 'string' ? room.metadata.color : '#dce0e8'
}

export function sceneBuildingBounds(scene: SceneDocument): BuildingBounds {
  return sceneWorldBounds(scene)
}

function FloorFromParts({ room, parts }: { room: Room; parts: Part[] }) {
  const color = roomColor(room)
  return (
    <group>
      {parts.map((p, i) => {
        const c = toWorld(p.x + p.width / 2, p.y + p.height / 2)
        return (
          <mesh
            key={`${room.id}-p${i}`}
            position={[c.x, 0.012, c.z]}
            receiveShadow
          >
            <boxGeometry args={[metersToWorld(p.width), 0.024, metersToWorld(p.height)]} />
            <meshStandardMaterial color={color} roughness={0.86} />
          </mesh>
        )
      })}
    </group>
  )
}

function FloorFromPolygon({ room }: { room: Room }) {
  const color = roomColor(room)
  const poly = room.polygon?.length >= 3 ? room.polygon : [
    room.position,
    { x: room.position.x + room.dimensions.width, y: room.position.y },
    { x: room.position.x + room.dimensions.width, y: room.position.y + room.dimensions.height },
    { x: room.position.x, y: room.position.y + room.dimensions.height },
  ]
  const shape = useMemo(() => {
    const s = new THREE.Shape()
    poly.forEach((p, i) => {
      const xy = shapeXY(p.x, p.y)
      if (i === 0) s.moveTo(xy.x, xy.y)
      else s.lineTo(xy.x, xy.y)
    })
    s.closePath()
    return s
  }, [room.id, room.polygon, room.position.x, room.position.y, room.dimensions.width, room.dimensions.height])
  return (
    <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.012, 0]} receiveShadow>
      <shapeGeometry args={[shape]} />
      <meshStandardMaterial color={color} roughness={0.86} />
    </mesh>
  )
}

function FloorMesh({ room }: { room: Room }) {
  const parts = roomPartsM(room)
  if (parts.length > 1) return <FloorFromParts room={room} parts={parts} />
  return <FloorFromPolygon room={room} />
}

function WallMesh({ wall, wallH }: { wall: Wall; wallH: number }) {
  const len = metersToWorld(wallLength(wall))
  if (len < 0.02) return null
  const mid = toWorld((wall.start.x + wall.end.x) / 2, (wall.start.y + wall.end.y) / 2)
  const rot = wallYaw(wall)
  const thick = Math.max(metersToWorld(wall.thickness || 0.15), 0.018)
  return (
    <mesh position={[mid.x, wallH / 2, mid.z]} rotation={[0, -rot, 0]} castShadow receiveShadow>
      <boxGeometry args={[len, wallH, thick]} />
      <meshStandardMaterial color={WALL_COLOR} roughness={0.78} />
    </mesh>
  )
}

function OpeningMesh({ opening, wall, wallH }: { opening: Opening; wall: Wall; wallH: number }) {
  const t = openingT(opening, wall)
  const p = wallPointAtT(wall, t)
  const pos = toWorld(p.x, p.y)
  const rot = wallYaw(wall)
  const isWindow = opening.type === 'window'
  const h = isWindow ? metersToWorld(opening.height) : wallH * 0.82
  const y = isWindow ? metersToWorld(opening.sillHeight) + h / 2 : h / 2
  const w = metersToWorld(opening.width)
  return (
    <group position={[pos.x, 0, pos.z]} rotation={[0, -rot, 0]}>
      <mesh position={[0, y, 0]}>
        <boxGeometry args={[w, h, 0.03]} />
        <meshStandardMaterial color={isWindow ? '#9ec0d8' : '#6b4f3a'} roughness={0.55} />
      </mesh>
      {!isWindow && (
        <mesh position={[w * 0.35, h / 2, metersToWorld(0.12)]} rotation={[0, 0.6, 0]}>
          <boxGeometry args={[0.012, h, w * 0.7]} />
          <meshStandardMaterial color="#5a4030" roughness={0.7} />
        </mesh>
      )}
    </group>
  )
}

function FurnitureMesh({ item }: { item: Furniture }) {
  const w = metersToWorld(item.dimensions.width)
  const d = metersToWorld(item.dimensions.height)
  const h = Math.max(0.08, Math.min(w, d) * 0.55)
  const c = toWorld(
    item.position.x + item.dimensions.width / 2,
    item.position.y + item.dimensions.height / 2,
  )
  const rot = ((item.rotation || 0) * Math.PI) / 180
  return (
    <mesh position={[c.x, h / 2, c.z]} rotation={[0, -rot, 0]} castShadow>
      <boxGeometry args={[w, h, d]} />
      <meshStandardMaterial color="#c4b8a8" roughness={0.8} />
    </mesh>
  )
}

export function SceneBuilding({
  scene,
  wallH,
  includeFurniture = true,
}: {
  scene: SceneDocument
  wallH: number
  includeFurniture?: boolean
}) {
  const wallsById = useMemo(() => new Map(scene.walls.map(w => [w.id, w])), [scene.walls])
  return (
    <group>
      {scene.rooms.map(room => (
        <FloorMesh key={room.id} room={room} />
      ))}
      {scene.walls.map(wall => (
        <WallMesh key={wall.id} wall={wall} wallH={wallH} />
      ))}
      {scene.openings.map(opening => {
        const wall = wallsById.get(opening.wallId)
        if (!wall) return null
        return <OpeningMesh key={opening.id} opening={opening} wall={wall} wallH={wallH} />
      })}
      {includeFurniture && (scene.furniture || []).map(item => (
        <FurnitureMesh key={item.id} item={item} />
      ))}
    </group>
  )
}
