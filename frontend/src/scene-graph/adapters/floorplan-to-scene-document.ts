/**
 * Convert a KIYUB v4 FloorPlan (OR-Tools geometry in feet) plus the
 * user lot (meters) into SceneDocument v2.0.
 *
 * Site dimensions always come from the questionnaire lot in meters.
 * Buildify/HouseGAN footprint and the OR-Tools envelope in feet must
 * not overwrite the user's lot.
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
import { polygonArea, polygonBounds, roomPolygonFromFloorPlan, scalePolygon } from "./room-polygon";

export const FEET_TO_METERS = 1 / 3.28084;

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

function ftToM(value: number): number {
  return value * FEET_TO_METERS;
}

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
  const polyFt = roomPolygonFromFloorPlan(room);
  const polygon = scalePolygon(polyFt, FEET_TO_METERS);
  const b = polygon.length >= 3
    ? polygonBounds(polygon)
    : { min: { x: ftToM(room.x), y: ftToM(room.y) }, max: { x: ftToM(room.x + room.width), y: ftToM(room.y + room.height) } };
  const width = b.max.x - b.min.x;
  const height = b.max.y - b.min.y;
  const envelopeW = plan.totalWidth || 0;
  const envelopeD = plan.totalHeight || 0;
  const left = room.x <= 0.5;
  const front = room.y <= 0.5;
  const right = envelopeW > 0 && room.x + room.width >= envelopeW - 0.5;
  const rear = envelopeD > 0 && room.y + room.height >= envelopeD - 0.5;
  const exteriorSides = [left, front, right, rear].filter(Boolean).length;
  const needsDaylight = /bedroom|living|dining|kitchen|office/i.test(room.type);
  const parts = (room.footprint?.parts || []).map(p => ({
    x: ftToM(p.x),
    y: ftToM(p.y),
    width: ftToM(p.width),
    height: ftToM(p.height),
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
      units: "converted_from_feet",
      exteriorSides,
      daylightPotential: needsDaylight ? exteriorSides > 0 : null,
      windowOpportunity: needsDaylight && exteriorSides > 0,
      note: "Daylight potential is a geometric heuristic, not daylight simulation.",
      ...(parts.length ? { parts } : {}),
    },
  };
}

function convertWall(wall: PlanWall, floorId: string, heightFt: number): Wall {
  return {
    id: wall.id,
    floorId,
    type: (wall.kind === "exterior" ? "exterior" : "interior") as WallType,
    start: { x: ftToM(wall.x1), y: ftToM(wall.y1) },
    end: { x: ftToM(wall.x2), y: ftToM(wall.y2) },
    thickness: 0.15,
    height: ftToM(heightFt || 9),
    roomIds: [...(wall.roomIds || [])],
    openingIds: [],
    metadata: { units: "converted_from_feet", sourceKind: wall.kind },
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

function convertOpening(opening: PlanOpening, floorId: string, ceilingFt: number, wallId: string): Opening {
  const type = openingTypeOf(opening.kind);
  const heightFt = opening.height ?? (type === "window" ? 4 : 7);
  return {
    id: opening.id,
    floorId,
    wallId,
    type,
    position: { x: ftToM(opening.x), y: ftToM(opening.y) },
    width: ftToM(opening.width),
    height: ftToM(heightFt),
    sillHeight: ftToM(opening.sillHeight ?? (type === "window" ? 3 : 0)),
    metadata: {
      units: "converted_from_feet",
      isVertical: opening.isVertical,
      roomIds: opening.roomIds || [],
      ceilingFt,
      hinge: "left",
    },
  };
}

function convertDoor(door: Door, floorId: string, ceilingFt: number, wallId: string): Opening {
  return {
    id: door.id || `door-${wallId}-${Math.round(door.x)}-${Math.round(door.y)}`,
    floorId,
    wallId,
    type: "door",
    position: { x: ftToM(door.x), y: ftToM(door.y) },
    width: ftToM(3),
    height: ftToM(7),
    sillHeight: 0,
    metadata: {
      units: "converted_from_feet",
      isVertical: door.isVertical,
      roomIds: [door.roomA, door.roomB].filter(Boolean),
      ceilingFt,
      hinge: "left",
    },
  };
}

function convertFurniture(item: PlanFurniture): Furniture {
  return {
    id: item.id,
    roomId: item.roomId,
    kind: item.kind,
    position: { x: ftToM(item.x), y: ftToM(item.y) },
    dimensions: { width: ftToM(item.width), height: ftToM(item.depth) },
    rotation: item.rotation || 0,
    metadata: item.assetId ? { assetId: item.assetId } : {},
  };
}

export function floorPlanToSceneDocument(
  plan: FloorPlan,
  lot: LotMeters,
  options: { projectId?: string } = {},
): SceneDocument {
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
  const walls: Wall[] = engineWalls.map((wall) => convertWall(wall, floorId, plan.ceilingHeight || 9));
  const openings: Opening[] = [];
  const usedOpeningIds = new Set<string>();
  for (const opening of engineOpenings) {
    const p = { x: ftToM(opening.x), y: ftToM(opening.y) };
    const wallId =
      opening.wallId && walls.some((w) => w.id === opening.wallId)
        ? opening.wallId
        : nearestWallId(walls, p);
    if (!wallId) continue;
    const converted = convertOpening(opening, floorId, plan.ceilingHeight || 9, wallId);
    openings.push(converted);
    usedOpeningIds.add(converted.id);
  }
  for (const door of plan.doors || []) {
    if (door.id && usedOpeningIds.has(door.id)) continue
    const p = { x: ftToM(door.x), y: ftToM(door.y) };
    const wallId =
      door.wallId && walls.some((w) => w.id === door.wallId)
        ? door.wallId
        : nearestWallId(walls, p);
    if (!wallId) continue;
    const converted = convertDoor(door, floorId, plan.ceilingHeight || 9, wallId);
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
      envelopeWidthFt: plan.totalWidth,
      envelopeDepthFt: plan.totalHeight,
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
