import { useRef, useEffect, useLayoutEffect, useMemo } from 'react'
import { Canvas, useFrame, useThree } from '@react-three/fiber'
import { OrbitControls, Text, Html } from '@react-three/drei'
import * as THREE from 'three'
import { FloorPlan, roomBoundary, roomCentroid, roomParts } from '../types/floorplan'
import type { SceneDocument } from '../scene-graph/types'
import { sceneDocumentToFloorPlan } from '../scene-graph/adapters/scene-document-to-floorplan'
import { SceneBuilding, sceneBuildingBounds } from './scene-3d-meshes'
import { normalizeFloorPlan } from '../units/legacy'
import {
  WORLD_UNITS_PER_METER,
  buildingBounds,
  viewCameraConfig,
  walkStartPosition,
  type View3DMode,
  type ViewCameraConfig,
} from './view3d-camera'

/** Plan meters -> world units. */
const S = WORLD_UNITS_PER_METER
type Mode = View3DMode

const WALL_COLOR = '#e2e6ec'
const WT = 0.022  // wall thickness, world units
const DEFAULT_CEILING_M = 2.7432
const DOOR_WIDTH_M = 0.9144
/** Rooms whose y falls in the same band share one roof section. */
const ROOF_ROW_BAND_M = 0.6096
/** Walkthrough keeps the camera this far inside room edges. */
const WALK_WALL_MARGIN_M = 0.15
const WALK_DOOR_DEPTH_M = 0.3048

// ─────────────────────────────────────────────────────────────────────────────
// SHARED UTILITIES
// ─────────────────────────────────────────────────────────────────────────────

function roomCenter(room: FloorPlan['rooms'][number]): [number, number, number] {
  const c = roomCentroid(room)
  return [c.x * S, 0, c.y * S]
}

function FloorParts({
  room, y, height, color, extra = 0,
}: {
  room: FloorPlan['rooms'][number]
  y: number
  height: number
  color: string
  extra?: number
}) {
  return (
    <>
      {roomParts(room).map((p, i) => {
        const rw = p.width * S
        const rd = p.height * S
        const px = (p.x + p.width / 2) * S
        const pz = (p.y + p.height / 2) * S
        return (
          <mesh key={`${room.id}-p${i}`} position={[px, y, pz]} castShadow receiveShadow>
            <boxGeometry args={[rw + extra, height, rd + extra]} />
            <meshStandardMaterial color={color} roughness={0.82} metalness={0.0} />
          </mesh>
        )
      })}
    </>
  )
}

function WallSegments({
  room, wallH, color,
}: {
  room: FloorPlan['rooms'][number]
  wallH: number
  color: string
}) {
  const segs = roomBoundary(room)
  if (!segs.length) return null
  return (
    <>
      {segs.map((seg, i) => {
        const dx = (seg.x2 - seg.x1) * S
        const dz = (seg.y2 - seg.y1) * S
        const len = Math.hypot(dx, dz)
        if (len < 1e-6) return null
        const mx = ((seg.x1 + seg.x2) / 2) * S
        const mz = ((seg.y1 + seg.y2) / 2) * S
        const rot = Math.atan2(dz, dx)
        return (
          <mesh
            key={`${room.id}-w${i}`}
            position={[mx, wallH / 2, mz]}
            rotation={[0, -rot, 0]}
            castShadow
          >
            <boxGeometry args={[len, wallH, WT]} />
            <meshStandardMaterial color={color} roughness={0.78} />
          </mesh>
        )
      })}
    </>
  )
}

// Removed frontend findDoors in favor of backend plan.doors data

// ─────────────────────────────────────────────────────────────────────────────
// EXTERIOR SCENE — Presentation model: light massing, soft edges
// ─────────────────────────────────────────────────────────────────────────────

/** White architectural walls — unified house mass from room bounding box */
function ArchitecturalHouse({ plan, wallH }: { plan: FloorPlan; wallH: number }) {
  // Compute overall bounding box for the main house body
  const rooms = plan.rooms.filter(r =>
    r.type !== 'patio' && r.type !== 'deck' && r.type !== 'rear_patio' && r.type !== 'outdoor_living'
  )
  const outdoor = plan.rooms.filter(r =>
    r.type === 'patio' || r.type === 'deck' || r.type === 'rear_patio' || r.type === 'outdoor_living'
  )

  const WHITE = '#f1f4f8'
  const EDGE = '#c5cdd8'

  return (
    <>
      {/* 🏠 Main house volume — one solid white box per room (they merge visually) */}
      {rooms.map(room => {
        const isGarage = room.type === 'garage'
        const h = isGarage ? wallH * 0.88 : wallH
        return <FloorParts key={room.id} room={room} y={h / 2} height={h} color={WHITE} />
      })}

      {/* 🌿 Outdoor / patio areas — flat slab, slightly different tone */}
      {outdoor.map(room => (
        <FloorParts key={room.id} room={room} y={0.018} height={0.036} color="#d4dce8" />
      ))}

      {/* Edge cap on top to create crisp roofline edge */}
      {rooms.map(room => {
        const isGarage = room.type === 'garage'
        const h = isGarage ? wallH * 0.88 : wallH
        return <FloorParts key={`cap-${room.id}`} room={room} y={h - 0.005} height={0.012} color={EDGE} extra={0.008} />
      })}
    </>
  )
}

/** Hip-style roof masses — neutral studio gray-white */
function ArchitecturalRoof({ plan, wallH }: { plan: FloorPlan; wallH: number }) {
  const rooms = plan.rooms.filter(r =>
    r.type !== 'patio' && r.type !== 'deck' && r.type !== 'rear_patio' &&
    r.type !== 'outdoor_living' && r.type !== 'garage'
  )

  const WHITE = '#e8ecf2'
  const overhang = 0.28

  // Group rooms into row-based sub-roofs for more realistic complex roofline
  const rowMap: Map<number, typeof rooms> = new Map()
  for (const room of rooms) {
    const key = Math.round(room.y / ROOF_ROW_BAND_M)
    if (!rowMap.has(key)) rowMap.set(key, [])
    rowMap.get(key)!.push(room)
  }

  const roofSections: { mx: number; my: number; mw: number; mh: number }[] = []
  for (const rowRooms of rowMap.values()) {
    const minX = Math.min(...rowRooms.map(r => r.x))
    const maxX = Math.max(...rowRooms.map(r => r.x + r.width))
    const minY = Math.min(...rowRooms.map(r => r.y))
    const maxY = Math.max(...rowRooms.map(r => r.y + r.height))
    roofSections.push({ mx: minX, my: minY, mw: maxX - minX, mh: maxY - minY })
  }

  return (
    <>
      {roofSections.map((sec, idx) => {
        const tw = sec.mw * S
        const td = sec.mh * S
        const cx = (sec.mx + sec.mw / 2) * S
        const cz = (sec.my + sec.mh / 2) * S
        const peakH = Math.min(tw, td) * 0.38

        // Simple hip roof mesh via a slightly elevated pyramidal shape
        // Build as two crossed gable prisms
        return (
          <group key={idx} position={[cx, wallH, cz]}>
            {/* Main roof deck — flat with slope suggestion */}
            <mesh castShadow>
              <boxGeometry args={[tw + overhang * 2, 0.025, td + overhang * 2]} />
              <meshStandardMaterial color={WHITE} roughness={0.86} />
            </mesh>
            {/* Ridge beam along long axis */}
            <mesh position={[0, peakH / 2, 0]} castShadow>
              <boxGeometry args={[tw * 0.85, peakH, 0.04]} />
              <meshStandardMaterial color={WHITE} roughness={0.82} />
            </mesh>
            {/* Cross ridge */}
            <mesh position={[0, peakH / 2, 0]} castShadow>
              <boxGeometry args={[0.04, peakH, td * 0.85]} />
              <meshStandardMaterial color={WHITE} roughness={0.82} />
            </mesh>
            {/* Ridge cap */}
            <mesh position={[0, peakH, 0]}>
              <boxGeometry args={[tw * 0.5, 0.025, 0.06]} />
              <meshStandardMaterial color="#d0d6de" roughness={0.9} />
            </mesh>
          </group>
        )
      })}
    </>
  )
}

/** Windows and front door details — clean white frames */
function ArchitecturalDetails({ plan, wallH }: { plan: FloorPlan; wallH: number }) {
  const tw = plan.totalWidth * S
  const td = plan.totalHeight * S
  const cx = tw / 2

  const winCount = Math.min(5, Math.max(2, Math.floor(plan.rooms.length * 0.5)))
  const winPositions = Array.from({ length: winCount }, (_, i) => (i + 1) / (winCount + 1))

  const FRAME = '#c5ccd6'
  const GLASS = '#C8D8E8'

  return (
    <group>
      {/* Green lawn base */}
      <mesh position={[cx, -0.015, td / 2]} receiveShadow>
        <boxGeometry args={[tw + 2.4, 0.03, td + 2.4]} />
        <meshStandardMaterial color="#8FB87A" roughness={0.95} />
      </mesh>

      {/* Concrete foundation lip */}
      <mesh position={[cx, 0.016, td / 2]} receiveShadow>
        <boxGeometry args={[tw + 0.06, 0.032, td + 0.06]} />
        <meshStandardMaterial color="#b8c0c8" roughness={0.88} />
      </mesh>

      {/* Windows — front face (z = 0) */}
      {winPositions.map((xf, i) => {
        const wx = (xf - 0.5) * tw * 0.78 + cx
        return (
          <group key={i} position={[wx, wallH * 0.58, 0.01]}>
            {/* Frame */}
            <mesh>
              <boxGeometry args={[tw * 0.11, wallH * 0.30, 0.018]} />
              <meshStandardMaterial color={FRAME} roughness={0.7} />
            </mesh>
            {/* Glass pane */}
            <mesh>
              <boxGeometry args={[tw * 0.095, wallH * 0.265, 0.022]} />
              <meshStandardMaterial color={GLASS} roughness={0.08} metalness={0.2} transparent opacity={0.6} />
            </mesh>
            {/* Mullion */}
            <mesh position={[0, 0, 0.019]}>
              <boxGeometry args={[tw * 0.095, 0.008, 0.004]} />
              <meshStandardMaterial color={FRAME} roughness={0.8} />
            </mesh>
          </group>
        )
      })}

      {/* Front door */}
      <group position={[cx, wallH * 0.28, 0.01]}>
        <mesh>
          <boxGeometry args={[tw * 0.065, wallH * 0.52, 0.018]} />
          <meshStandardMaterial color="#d4dce6" roughness={0.72} />
        </mesh>
        {/* Door glass lite */}
        <mesh position={[0, wallH * 0.08, 0.012]}>
          <boxGeometry args={[tw * 0.042, wallH * 0.14, 0.008]} />
          <meshStandardMaterial color={GLASS} roughness={0.1} transparent opacity={0.55} />
        </mesh>
        {/* Simple stoop */}
        <mesh position={[0, -wallH * 0.28, -0.08]}>
          <boxGeometry args={[tw * 0.12, 0.02, 0.18]} />
          <meshStandardMaterial color="#b8c0cc" roughness={0.88} />
        </mesh>
      </group>
    </group>
  )
}


// ─────────────────────────────────────────────────────────────────────────────
// DOLLHOUSE SCENE (existing)
// ─────────────────────────────────────────────────────────────────────────────

function RoomDollhouse({ room, wallH }: { room: FloorPlan['rooms'][number]; wallH: number }) {
  const c = roomCentroid(room)
  const parts = roomParts(room)
  const segs = roomBoundary(room)
  const minDim = Math.min(...parts.map(p => Math.min(p.width, p.height)), room.width, room.height)

  return (
    <group>
      <FloorParts room={room} y={WT / 2} height={WT} color={room.color} />
      {segs.length > 0 ? (
        <WallSegments room={room} wallH={wallH} color={WALL_COLOR} />
      ) : null}
      <Text
        position={[c.x * S, WT + 0.005, c.y * S]}
        rotation={[-Math.PI / 2, 0, 0]}
        fontSize={minDim * S * 0.18}
        color="#1a1a1a80"
        anchorX="center"
        anchorY="middle"
      >
        {room.name.toUpperCase()}
      </Text>
    </group>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
// WALKTHROUGH MODE — First-person WASD walking
// ─────────────────────────────────────────────────────────────────────────────

function WalkthroughRoom({ room, wallH }: { room: FloorPlan['rooms'][number]; wallH: number }) {
  const c = roomCentroid(room)
  const parts = roomParts(room)
  const segs = roomBoundary(room)
  const minDim = Math.min(...parts.map(p => Math.min(p.width, p.height)), room.width, room.height)

  return (
    <group>
      <FloorParts room={room} y={0.005} height={0.01} color={room.color} />
      {segs.length > 0 ? (
        <WallSegments room={room} wallH={wallH} color="#e8ecf2" />
      ) : null}
      <Text
        position={[c.x * S, wallH * 0.6, (parts[0] ? parts[0].y : room.y) * S + 0.02]}
        fontSize={wallH * 0.12}
        color="#475569"
        anchorX="center"
        anchorY="middle"
        maxWidth={minDim * S * 0.9}
      >
        {room.name}
      </Text>
    </group>
  )
}

/** Door opening markers for the walkthrough */
function DoorOpenings({ doors, wallH }: { doors: FloorPlan['doors']; wallH: number }) {
  return (
    <>
      {doors.map((door, i) => {
        const dx = door.x * S
        const dz = door.y * S
        const dw = DOOR_WIDTH_M * S
        return (
          <group key={i} position={[dx, 0, dz]}>
            {/* Door frame */}
            <mesh position={[0, wallH * 0.38, 0]}>
              <boxGeometry args={[
                door.isVertical ? 0.04 : dw,
                wallH * 0.76,
                door.isVertical ? dw : 0.04
              ]} />
              <meshStandardMaterial color="#8B7355" roughness={0.7} />
            </mesh>
            {/* Door threshold */}
            <mesh position={[0, 0.01, 0]}>
              <boxGeometry args={[
                door.isVertical ? 0.06 : dw + 0.02,
                0.02,
                door.isVertical ? dw + 0.02 : 0.06
              ]} />
              <meshStandardMaterial color="#A89070" roughness={0.85} />
            </mesh>
          </group>
        )
      })}
    </>
  )
}

/** First-person camera controller with WASD movement */
function FirstPersonController({ plan, wallH }: { plan: FloorPlan; wallH: number }) {
  const { camera, gl } = useThree()
  const moveState = useRef({ forward: false, backward: false, left: false, right: false })
  const yaw = useRef(0)
  const pitch = useRef(0)
  const isLocked = useRef(false)
  const speed = 0.025

  const start = walkStartPosition(plan.rooms, wallH)
  const startPos = useRef(new THREE.Vector3(start[0], start[1], start[2]))

  // Set initial camera position
  useEffect(() => {
    camera.position.copy(startPos.current)
    camera.rotation.set(0, 0, 0)
  }, [camera])

  // Pointer lock
  useEffect(() => {
    const canvas = gl.domElement

    const onClick = () => {
      canvas.requestPointerLock()
    }

    const onLockChange = () => {
      isLocked.current = document.pointerLockElement === canvas
    }

    const onMouseMove = (e: MouseEvent) => {
      if (!isLocked.current) return
      yaw.current -= e.movementX * 0.002
      pitch.current -= e.movementY * 0.002
      pitch.current = Math.max(-Math.PI / 3, Math.min(Math.PI / 3, pitch.current))
    }

    const onKeyDown = (e: KeyboardEvent) => {
      switch (e.code) {
        case 'KeyW': case 'ArrowUp': moveState.current.forward = true; break
        case 'KeyS': case 'ArrowDown': moveState.current.backward = true; break
        case 'KeyA': case 'ArrowLeft': moveState.current.left = true; break
        case 'KeyD': case 'ArrowRight': moveState.current.right = true; break
      }
    }

    const onKeyUp = (e: KeyboardEvent) => {
      switch (e.code) {
        case 'KeyW': case 'ArrowUp': moveState.current.forward = false; break
        case 'KeyS': case 'ArrowDown': moveState.current.backward = false; break
        case 'KeyA': case 'ArrowLeft': moveState.current.left = false; break
        case 'KeyD': case 'ArrowRight': moveState.current.right = false; break
      }
    }

    canvas.addEventListener('click', onClick)
    document.addEventListener('pointerlockchange', onLockChange)
    document.addEventListener('mousemove', onMouseMove)
    document.addEventListener('keydown', onKeyDown)
    document.addEventListener('keyup', onKeyUp)

    return () => {
      canvas.removeEventListener('click', onClick)
      document.removeEventListener('pointerlockchange', onLockChange)
      document.removeEventListener('mousemove', onMouseMove)
      document.removeEventListener('keydown', onKeyDown)
      document.removeEventListener('keyup', onKeyUp)
      if (document.pointerLockElement === canvas) {
        document.exitPointerLock()
      }
    }
  }, [gl])

  // Movement + collision detection
  useFrame(() => {
    const euler = new THREE.Euler(pitch.current, yaw.current, 0, 'YXZ')
    camera.quaternion.setFromEuler(euler)

    const direction = new THREE.Vector3()
    const m = moveState.current
    if (m.forward) direction.z -= 1
    if (m.backward) direction.z += 1
    if (m.left) direction.x -= 1
    if (m.right) direction.x += 1

    if (direction.lengthSq() > 0) {
      direction.normalize().multiplyScalar(speed)
      direction.applyAxisAngle(new THREE.Vector3(0, 1, 0), yaw.current)

      const nextX = camera.position.x + direction.x
      const nextZ = camera.position.z + direction.z

      // Collision helper: find if point is inside a room OR a door
      const isPassable = (tx: number, tz: number) => {
        const mX = tx / S
        const mY = tz / S
        const margin = WALK_WALL_MARGIN_M

        // 1. Check if inside any room, keeping a small margin from the walls
        const insideRoom = plan.rooms.some(r =>
          mX >= r.x + margin && mX <= r.x + r.width - margin &&
          mY >= r.y + margin && mY <= r.y + r.height - margin
        )
        if (insideRoom) return true

        // 2. Check if inside a door opening
        const nearDoor = plan.doors.some(d => {
          const dx = d.x, dy = d.y
          const half = DOOR_WIDTH_M / 2
          if (d.isVertical) {
            return Math.abs(mX - dx) < WALK_DOOR_DEPTH_M && Math.abs(mY - dy) < half
          } else {
            return Math.abs(mY - dy) < WALK_DOOR_DEPTH_M && Math.abs(mX - dx) < half
          }
        })
        return nearDoor
      }

      // Sliding collision (check X and Z separately)
      if (isPassable(nextX, camera.position.z)) camera.position.x = nextX
      if (isPassable(camera.position.x, nextZ)) camera.position.z = nextZ
      
      camera.position.y = wallH * 0.62
    }
  })

  return null
}

// ─────────────────────────────────────────────────────────────────────────────
// TOP VIEW MODE — Bird's-eye colored blocks with labels
// ─────────────────────────────────────────────────────────────────────────────

const ZONE_COLORS: Record<string, string> = {
  living_room: '#a8d0bc', kitchen: '#e2d9a8', dining_room: '#d4cfa0',
  family_room: '#b8dcc4', master_bedroom: '#e8d4dc', bedroom: '#c8d4e8',
  ensuite_bathroom: '#a8cfe8', bathroom: '#a8cfe8', half_bath: '#b8e0e4',
  hallway: '#d8dce4', foyer: '#d8e0c8', home_office: '#c4c8e8',
  laundry_room: '#b8d4e8', garage: '#c4c8c4', walk_in_closet: '#d8dce8',
  closet: '#d8dce8', pantry: '#e0dcc8', mudroom: '#d0d4cc',
  utility_room: '#ccd0d0', patio: '#a8d8bc', deck: '#a8d8bc',
}

function TopViewBlock({ room, blockH }: { room: FloorPlan['rooms'][number]; blockH: number }) {
  const color = ZONE_COLORS[room.type] || room.color || '#dce0e8'
  const c = roomCentroid(room)
  const parts = roomParts(room)
  const minDim = Math.min(...parts.map(p => Math.min(p.width, p.height)), room.width, room.height) * S

  return (
    <group>
      {parts.map((p, i) => {
        const rw = p.width * S
        const rd = p.height * S
        const px = (p.x + p.width / 2) * S
        const pz = (p.y + p.height / 2) * S
        return (
          <group key={i} position={[px, 0, pz]}>
            <mesh position={[0, blockH / 2, 0]} castShadow receiveShadow>
              <boxGeometry args={[rw - 0.01, blockH, rd - 0.01]} />
              <meshStandardMaterial color={color} roughness={0.75} metalness={0.05} />
            </mesh>
            <mesh position={[0, blockH, 0]}>
              <boxGeometry args={[rw, 0.004, rd]} />
              <meshStandardMaterial color="#FFFFFF" roughness={0.5} transparent opacity={0.3} />
            </mesh>
          </group>
        )
      })}
      <Text
        position={[c.x * S, blockH + 0.03, c.y * S]}
        rotation={[-Math.PI / 2, 0, 0]}
        fontSize={minDim * 0.22}
        color="#1e293b"
        anchorX="center"
        anchorY="middle"
        maxWidth={minDim * 0.9}
      >
        {room.name}
      </Text>
    </group>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
// WALKTHROUGH HUD (overlays)
// ─────────────────────────────────────────────────────────────────────────────

function WalkthroughHUD({ plan }: { plan: FloorPlan }) {
  return (
    <>
      {/* Crosshair */}
      <div className="walkthrough-crosshair">+</div>
      {/* Controls hint */}
      <div className="walkthrough-hint">
        <div>Click to look around</div>
        <div>WASD or arrows to walk</div>
        <div>ESC to release cursor</div>
      </div>
      {/* Minimap */}
      <div className="walkthrough-minimap">
        <svg viewBox={`0 0 ${plan.totalWidth} ${plan.totalHeight}`} preserveAspectRatio="xMidYMid meet">
          {plan.rooms.map(room => (
            <rect
              key={room.id}
              x={room.x} y={room.y}
              width={room.width} height={room.height}
              fill={room.color} stroke="#333" strokeWidth="0.15"
            />
          ))}
        </svg>
      </div>
    </>
  )
}

function ActiveCamera({ viewMode, config }: { viewMode: Mode; config: ViewCameraConfig }) {
  const { set, size } = useThree()
  const [px, py, pz] = config.position
  const [tx, ty, tz] = config.target
  const [ux, uy, uz] = config.up ?? [0, 1, 0]
  useLayoutEffect(() => {
    const aspect = size.width / Math.max(size.height, 1)
    let next: THREE.PerspectiveCamera | THREE.OrthographicCamera
    if (config.kind === 'orthographic') {
      const hw = config.halfWidth ?? 4
      const hh = config.halfHeight ?? 4
      const buildingAspect = hw / Math.max(hh, 1e-6)
      const ortho = new THREE.OrthographicCamera(-hw, hw, hh, -hh, 0.1, 80)
      if (aspect > buildingAspect) {
        ortho.left = -hh * aspect
        ortho.right = hh * aspect
        ortho.top = hh
        ortho.bottom = -hh
      } else {
        ortho.left = -hw
        ortho.right = hw
        ortho.top = hw / aspect
        ortho.bottom = -hw / aspect
      }
      next = ortho
    } else {
      next = new THREE.PerspectiveCamera(config.fov ?? 50, aspect, 0.1, 100)
    }
    next.position.set(px, py, pz)
    next.up.set(ux, uy, uz)
    next.lookAt(tx, ty, tz)
    next.updateProjectionMatrix()
    set({ camera: next })
  }, [viewMode, config.kind, config.fov, config.halfWidth, config.halfHeight, px, py, pz, tx, ty, tz, ux, uy, uz, set, size.width, size.height])
  return null
}

// ─────────────────────────────────────────────────────────────────────────────
// MAIN COMPONENT
// ─────────────────────────────────────────────────────────────────────────────

interface Props {
  plan?: FloorPlan
  scene?: SceneDocument
  viewMode: Mode
}

export default function View3D({ plan, scene, viewMode }: Props) {
  const resolved = useMemo(() => scene ? sceneDocumentToFloorPlan(scene) : normalizeFloorPlan(plan!), [scene, plan])
  const wallH = scene
    ? (scene.walls[0]?.height || scene.floorData[0]?.height || 2.74) * S
    : (resolved.ceilingHeight || DEFAULT_CEILING_M) * S
  const bounds = useMemo(
    () => scene ? sceneBuildingBounds(scene) : buildingBounds(resolved),
    [scene, resolved],
  )
  const walkStart = useMemo(() => {
    if (scene?.rooms[0]) {
      const r = scene.rooms[0]
      const cx = (r.position.x + r.dimensions.width / 2) * S
      const cz = (r.position.y + r.dimensions.height / 2) * S
      return [cx, wallH * 0.62, cz] as [number, number, number]
    }
    return walkStartPosition(resolved.rooms, wallH)
  }, [scene, resolved.rooms, wallH])
  const cam = viewCameraConfig(viewMode, bounds, wallH, walkStart)
  const cx = bounds.cx
  const cz = bounds.cz

  const doors = resolved.doors || []

  return (
    <div style={{ width: '100%', height: '100%', position: 'relative' }}>
      {viewMode === 'walkthrough' && <WalkthroughHUD plan={resolved} />}

      <Canvas
        shadows
        style={{ width: '100%', height: '100%', cursor: viewMode === 'walkthrough' ? 'crosshair' : 'grab' }}
        gl={{ antialias: true }}
      >
        <ActiveCamera viewMode={viewMode} config={cam} />

        {/* ── EXTERIOR MODE ── */}
        {viewMode === 'exterior' && (
          <>
            <color attach="background" args={['#0B0D10']} />

            <ambientLight intensity={0.35} color="#c8cdd3" />
            <directionalLight
              position={[10, 18, 9]} intensity={1.1} color="#e8e6df"
              castShadow
              shadow-mapSize-width={2048} shadow-mapSize-height={2048}
              shadow-camera-left={-16} shadow-camera-right={16}
              shadow-camera-top={16} shadow-camera-bottom={-16}
              shadow-camera-far={60}
            />
            <directionalLight position={[-7, 7, -5]} intensity={0.18} color="#8aa0b0" />

            <mesh rotation={[-Math.PI / 2, 0, 0]} receiveShadow position={[cx, 0, cz]}>
              <planeGeometry args={[bounds.spanX * 7, bounds.spanZ * 7]} />
              <meshStandardMaterial color="#15181D" roughness={0.96} />
            </mesh>

            {scene ? (
              <SceneBuilding scene={scene} wallH={wallH} />
            ) : (
              <>
                <ArchitecturalHouse plan={resolved} wallH={wallH} />
                <ArchitecturalDetails plan={resolved} wallH={wallH} />
                <ArchitecturalRoof plan={resolved} wallH={wallH} />
              </>
            )}

            <OrbitControls
              key={viewMode}
              target={cam.target}
              minDistance={1} maxDistance={30}
              maxPolarAngle={Math.PI / 2 - 0.03}
            />
          </>
        )}

        {/* ── DOLLHOUSE MODE ── */}
        {viewMode === 'dollhouse' && (
          <>
            <color attach="background" args={['#0B0D10']} />

            <ambientLight intensity={0.55} color="#d7dbe0" />
            <directionalLight
              position={[cx, wallH * 7, cz + resolved.totalHeight * S * 0.8]}
              intensity={0.85} color="#f2f1ed"
              castShadow
              shadow-mapSize-width={2048} shadow-mapSize-height={2048}
              shadow-camera-left={-20} shadow-camera-right={20}
              shadow-camera-top={20} shadow-camera-bottom={-20}
            />
            <directionalLight position={[cx, wallH * 0.5, cz + bounds.spanZ * 3]} intensity={0.25} color="#9ba3ae" />

            <mesh rotation={[-Math.PI / 2, 0, 0]} receiveShadow position={[cx, 0, cz]}>
              <planeGeometry args={[bounds.spanX * 2.5, bounds.spanZ * 2.5]} />
              <meshStandardMaterial color="#15181D" roughness={0.96} />
            </mesh>

            {scene ? (
              <SceneBuilding scene={scene} wallH={wallH} />
            ) : resolved.rooms.map(room => (
              <RoomDollhouse key={room.id} room={room} wallH={wallH} />
            ))}

            <OrbitControls
              key={viewMode}
              target={cam.target}
              minDistance={0.5} maxDistance={22}
              maxPolarAngle={Math.PI / 2 - 0.01}
            />
          </>
        )}

        {/* ── WALKTHROUGH MODE ── */}
        {viewMode === 'walkthrough' && (
          <>
            <color attach="background" args={['#0B0D10']} />

            <ambientLight intensity={0.4} color="#d4d0c8" />
            <directionalLight
              position={[cx, wallH * 4, cz]}
              intensity={0.9} color="#f2f1ed"
              castShadow
              shadow-mapSize-width={2048} shadow-mapSize-height={2048}
              shadow-camera-left={-20} shadow-camera-right={20}
              shadow-camera-top={20} shadow-camera-bottom={-20}
            />
            {/* Fill lights from corners */}
            <pointLight position={[0, wallH * 0.7, 0]} intensity={0.25} color="#c5b8a4" />
            <pointLight position={[bounds.maxX, wallH * 0.7, bounds.maxZ]} intensity={0.25} color="#c5b8a4" />

            {/* Base ground plane */}
            <mesh rotation={[-Math.PI / 2, 0, 0]} receiveShadow position={[cx, -0.01, cz]}>
              <planeGeometry args={[bounds.spanX * 3, bounds.spanZ * 3]} />
              <meshStandardMaterial color="#15181D" roughness={0.95} />
            </mesh>

            {scene ? (
              <SceneBuilding scene={scene} wallH={wallH} />
            ) : (
              <>
                {resolved.rooms.map(room => (
                  <WalkthroughRoom key={room.id} room={room} wallH={wallH} />
                ))}
                <DoorOpenings doors={doors} wallH={wallH} />
              </>
            )}

            <FirstPersonController plan={resolved} wallH={wallH} />
          </>
        )}

        {/* ── TOP VIEW MODE ── */}
        {viewMode === 'topview' && (
          <>
            <color attach="background" args={['#0B0D10']} />

            <ambientLight intensity={0.5} color="#d7dbe0" />
            <directionalLight
              position={[cx + 2, wallH * 10, cz - 2]}
              intensity={0.7} color="#f2f1ed"
              castShadow
              shadow-mapSize-width={2048} shadow-mapSize-height={2048}
              shadow-camera-left={-20} shadow-camera-right={20}
              shadow-camera-top={20} shadow-camera-bottom={-20}
            />
            <directionalLight position={[cx - 3, wallH * 5, cz + 3]} intensity={0.2} color="#9ba3ae" />

            {/* Subtle ground */}
            <mesh rotation={[-Math.PI / 2, 0, 0]} receiveShadow position={[cx, -0.01, cz]}>
              <planeGeometry args={[bounds.spanX * 3, bounds.spanZ * 3]} />
              <meshStandardMaterial color="#15181D" roughness={0.96} />
            </mesh>

            {scene ? (
              <SceneBuilding scene={scene} wallH={wallH * 0.5} />
            ) : resolved.rooms.map(room => (
              <TopViewBlock key={room.id} room={room} blockH={wallH * 0.5} />
            ))}

            <OrbitControls
              key={viewMode}
              target={cam.target}
              enableRotate={false}
              enablePan
            />
          </>
        )}
      </Canvas>
    </div>
  )
}
