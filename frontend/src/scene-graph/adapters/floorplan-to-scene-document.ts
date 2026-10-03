/**
 * Convert a KIYUB v4 FloorPlan (meters) plus the user lot (meters) into SceneDocument v2.0.
 * Legacy feet plans (no `units`) are normalized first, so no scaling happens here.
 *
 * Site dimensions always come from the questionnaire lot. The building
 * envelope must not overwrite the user's lot.
 *
 * Walls and openings are mapped only when the engine emits them.
 * Empty engine payload stays empty — this adapter does not invent walls.
 */
import type { Constraints, Door, FloorPlan, PlanFurniture, PlanOpening, PlanWall, Room as FloorPlanRoom } from "../../types/floorplan";
import type {
  Floor,
  Furniture,
  Opening,
  OpeningType,
  Point2D,
  Room,
  RoomType,
  SceneDocument,
  SceneMetadata,
  Wall,
  WallType,
} from "../types";
import { validateSceneDocumentDetailed } from "../validation";
import { dist, nearestOnWall, wallLength } from "../edit/geometry";
import { polygonArea, polygonBounds, roomPolygonFromFloorPlan } from "./room-polygon";
import { normalizeFloorPlan } from "../../units/legacy";
import { fromMeters } from "../../units/measurement";

const metersToLegacyFeet = (m: number) => fromMeters(m, "ft");

const DEFAULT_CEILING_M = 2.7432;
const DEFAULT_DOOR_WIDTH_M = 0.9144;
const DEFAULT_DOOR_HEIGHT_M = 2.1336;
const DEFAULT_WINDOW_HEIGHT_M = 1.2192;
const DEFAULT_WINDOW_SILL_M = 0.9144;
/** A room within this distance of the envelope edge counts as exterior on that side. */
const EDGE_TOLERANCE_M = 0.15;

const ROOM_TYPE_MAP: Record<string, RoomType> = {
  living_room: "living_room",
  living: "living_room",
  dining_room: "dining_room",
  dining: "dining_room",
  kitchen: "kitchen",
  bedroom: "bedroom",
  master_bedroom: "master_bedroom",
  bathroom: "bathroom",
  ensuite_bathroom: "bathroom",
  half_bath: "toilet",
  toilet: "toilet",
  garage: "garage",
  laundry: "laundry",
  laundry_room: "laundry",
  storage: "storage",
  walk_in_closet: "storage",
  closet: "storage",
  hallway: "hallway",
  corridor: "corridor",
  stairs: "stairs",
  balcony: "balcony",
  patio: "balcony",
  deck: "balcony",
  office: "office",
  home_office: "office",
  utility: "utility",
  utility_room: "utility",
  mudroom: "utility",
  pantry: "storage",
  porch: "porch",
  foyer: "entry",
  entry: "entry",
  other: "other",
};

export type LotMeters = Pick<Constraints, "lotWidth" | "lotDepth"> & {
  stories?: number;
};

function normalizeRoomType(type: string): RoomType {
  const normalized = type.trim().toLowerCase();
  return ROOM_TYPE_MAP[normalized] ?? "other";
}

function roomPolygon(x: number, y: number, width: number, height: number): Point2D[] {
  return [
    { x, y },
    { x: x + width, y },
    { x: x + width, y: y + height },
    { x, y: y + height },
  ];
}

function createFloors(floorCount: number): Floor[] {
  return Array.from({ length: floorCount }, (_, index) => {
    const level = index + 1;
    return {
      id: `floor-${level}`,
      level,
      elevation: index * 3,
      height: 3,
      roomIds: [],
      wallIds: [],
      openingIds: [],
      stairIds: [],
    };
  });
}

function convertRoom(room: FloorPlanRoom, floorId: string, plan: FloorPlan): Room {
  const polygon = roomPolygonFromFloorPlan(room);
  const b = polygon.length >= 3
    ? polygonBounds(polygon)
    : { min: { x: room.x, y: room.y }, max: { x: room.x + room.width, y: room.y + room.height } };
  const width = b.max.x - b.min.x;
  const height = b.max.y - b.min.y;
  const envelopeW = plan.totalWidth || 0;
  const envelopeD = plan.totalHeight || 0;
  const left = room.x <= EDGE_TOLERANCE_M;
  const front = room.y <= EDGE_TOLERANCE_M;
  const right = envelopeW > 0 && room.x + room.width >= envelopeW - EDGE_TOLERANCE_M;
  const rear = envelopeD > 0 && room.y + room.height >= envelopeD - EDGE_TOLERANCE_M;
  const exteriorSides = [left, front, right, rear].filter(Boolean).length;
  const needsDaylight = /bedroom|living|dining|kitchen|office/i.test(room.type);
  const parts = (room.footprint?.parts || []).map(p => ({
    x: p.x,
    y: p.y,
    width: p.width,
    height: p.height,
  }));
  return {
    id: room.id,
    floorId,
    name: room.name || room.id,
    type: normalizeRoomType(room.type),
    position: { ...b.min },
    dimensions: { width, height },
    polygon: polygon.length >= 3 ? polygon : roomPolygon(b.min.x, b.min.y, width, height),
    area: polygon.length >= 3 ? polygonArea(polygon) : width * height,
    wallIds: [],
    openingIds: [],
    metadata: {
      sourceType: room.type,
      color: room.color,
      exteriorSides,
      daylightPotential: needsDaylight ? exteriorSides > 0 : null,
      windowOpportunity: needsDaylight && exteriorSides > 0,
      note: "Daylight potential is a geometric heuristic, not daylight simulation.",
      ...(parts.length ? { parts } : {}),
    },
  };
}

function convertWall(wall: PlanWall, floorId: string, heightM: number): Wall {
  return {
    id: wall.id,
    floorId,
    type: (wall.kind === "exterior" ? "exterior" : "interior") as WallType,
    start: { x: wall.x1, y: wall.y1 },
    end: { x: wall.x2, y: wall.y2 },
    thickness: 0.15,
    height: heightM,
    roomIds: [...(wall.roomIds || [])],
    openingIds: [],
    metadata: { sourceKind: wall.kind },
  };
}

function openingTypeOf(kind: string): OpeningType {
  const k = (kind || "window").toLowerCase();
  if (k === "door") return "door";
  if (k === "sliding_door") return "sliding_door";
  if (k === "garage_door") return "garage_door";
  return "window";
}

function nearestWallId(walls: Wall[], p: Point2D): string | null {
  let best: Wall | null = null;
  let bestD = Infinity;
  for (const wall of walls) {
    if (wallLength(wall) < 0.08) continue;
    const d = dist(nearestOnWall(wall, p), p);
    if (d < bestD) {
      bestD = d;
      best = wall;
    }
  }
  return best?.id || null;
}

function convertOpening(opening: PlanOpening, floorId: string, ceilingM: number, wallId: string): Opening {
  const type = openingTypeOf(opening.kind);
  return {
    id: opening.id,
    floorId,
    wallId,
    type,
    position: { x: opening.x, y: opening.y },
    width: opening.width,
    height: opening.height ?? (type === "window" ? DEFAULT_WINDOW_HEIGHT_M : DEFAULT_DOOR_HEIGHT_M),
    sillHeight: opening.sillHeight ?? (type === "window" ? DEFAULT_WINDOW_SILL_M : 0),
    metadata: {
      isVertical: opening.isVertical,
      roomIds: opening.roomIds || [],
      ceilingM,
      hinge: "left",
    },
  };
}

function convertDoor(door: Door, floorId: string, ceilingM: number, wallId: string): Opening {
  return {
    // Fallback ids are keyed on whole feet so ids persisted before meters stay stable.
    id: door.id || `door-${wallId}-${Math.round(metersToLegacyFeet(door.x))}-${Math.round(metersToLegacyFeet(door.y))}`,
    floorId,
    wallId,
    type: "door",
    position: { x: door.x, y: door.y },
    width: DEFAULT_DOOR_WIDTH_M,
    height: DEFAULT_DOOR_HEIGHT_M,
    sillHeight: 0,
    metadata: {
      isVertical: door.isVertical,
      roomIds: [door.roomA, door.roomB].filter(Boolean),
      ceilingM,
      hinge: "left",
    },
  };
}

function convertFurniture(item: PlanFurniture): Furniture {
  return {
    id: item.id,
    roomId: item.roomId,
    kind: item.kind,
    position: { x: item.x, y: item.y },
    dimensions: { width: item.width, height: item.depth },
    rotation: item.rotation || 0,
    metadata: item.assetId ? { assetId: item.assetId } : {},
  };
}

export function floorPlanToSceneDocument(
  input: FloorPlan,
  lot: LotMeters,
  options: { projectId?: string } = {},
): SceneDocument {
  const plan = normalizeFloorPlan(input);
  if (!Number.isFinite(lot.lotWidth) || lot.lotWidth <= 0) {
    throw new Error("lotWidth must be a finite number greater than zero (meters).");
  }
  if (!Number.isFinite(lot.lotDepth) || lot.lotDepth <= 0) {
    throw new Error("lotDepth must be a finite number greater than zero (meters).");
  }

  const floorCount = 1;
  const floors = createFloors(floorCount);
  const floorId = floors[0].id;

  const rooms: Room[] = (plan.rooms || []).map((room) => {
    const converted = convertRoom(room, floorId, plan);
    floors[0].roomIds.push(converted.id);
    return converted;
  });

  const engineWalls = plan.walls || [];
  const engineOpenings = plan.openings || [];
  const ceilingM = plan.ceilingHeight || DEFAULT_CEILING_M;
  const walls: Wall[] = engineWalls.map((wall) => convertWall(wall, floorId, ceilingM));
  const openings: Opening[] = [];
  const usedOpeningIds = new Set<string>();
  for (const opening of engineOpenings) {
    const p = { x: opening.x, y: opening.y };
    const wallId =
      opening.wallId && walls.some((w) => w.id === opening.wallId)
        ? opening.wallId
        : nearestWallId(walls, p);
    if (!wallId) continue;
    const converted = convertOpening(opening, floorId, ceilingM, wallId);
    openings.push(converted);
    usedOpeningIds.add(converted.id);
  }
  for (const door of plan.doors || []) {
    if (door.id && usedOpeningIds.has(door.id)) continue
    const p = { x: door.x, y: door.y };
    const wallId =
      door.wallId && walls.some((w) => w.id === door.wallId)
        ? door.wallId
        : nearestWallId(walls, p);
    if (!wallId) continue;
    const converted = convertDoor(door, floorId, ceilingM, wallId);
    if (usedOpeningIds.has(converted.id)) continue;
    openings.push(converted);
    usedOpeningIds.add(converted.id);
  }

  const furniture: Furniture[] = (plan.furniture || []).map(convertFurniture);

  const openingsByWall = new Map<string, string[]>();
  for (const opening of openings) {
    const list = openingsByWall.get(opening.wallId) || [];
    list.push(opening.id);
    openingsByWall.set(opening.wallId, list);
  }
  for (const wall of walls) {
    wall.openingIds = openingsByWall.get(wall.id) || [];
    floors[0].wallIds.push(wall.id);
  }
  floors[0].openingIds = openings.map((o) => o.id);

  const wallsByRoom = new Map<string, string[]>();
  for (const wall of walls) {
    for (const rid of wall.roomIds) {
      const list = wallsByRoom.get(rid) || [];
      list.push(wall.id);
      wallsByRoom.set(rid, list);
    }
  }
  const openingsByRoom = new Map<string, string[]>();
  for (const opening of openings) {
    const roomIds = (opening.metadata?.roomIds as string[] | undefined) || [];
    for (const rid of roomIds) {
      const list = openingsByRoom.get(rid) || [];
      list.push(opening.id);
      openingsByRoom.set(rid, list);
    }
  }
  for (const room of rooms) {
    room.wallIds = wallsByRoom.get(room.id) || [];
    room.openingIds = openingsByRoom.get(room.id) || [];
  }

  const now = new Date().toISOString();
  const metadata: SceneMetadata = {
    createdAt: now,
    updatedAt: now,
    generator: "kiyub-v4",
    generatorVersion: "4.0.0",
    extra: {
      planId: plan.id,
      envelopeWidthM: plan.totalWidth,
      envelopeDepthM: plan.totalHeight,
      lotWidthM: lot.lotWidth,
      lotDepthM: lot.lotDepth,
    },
  };

  const scene: SceneDocument = {
    version: "2.0",
    projectId: options.projectId ?? plan.name ?? "kiyub-v4",
    units: "metric",
    floors: floorCount,
    site: {
      width: lot.lotWidth,
      depth: lot.lotDepth,
    },
    metadata,
    floorData: floors,
    rooms,
    walls,
    openings,
    furniture,
    stairs: [],
  };

  const validation = validateSceneDocumentDetailed(scene);
  if (!validation.valid) {
    throw new Error(
      ["Generated SceneDocument failed validation:", ...validation.errors.map((e) => `- ${e}`)].join(
        "\n",
      ),
    );
  }

  return scene;
}
