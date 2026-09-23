/**
 * KIYUB v4 - Scene Graph Types
 *
 * SceneDocument is the canonical representation of a generated
 * architectural scene.
 *
 * ArchitecturalSpecification = what the user wants
 * SceneDocument             = what the generation engine produced
 *
 * Units:
 * - All architectural dimensions are expressed in meters.
 * - Angles are expressed in degrees unless otherwise specified.
 */

export type SceneDocumentVersion = "2.0";

export type Units = "metric";

/**
 * Basic 2D point.
 *
 * Coordinate system:
 * - x = horizontal position
 * - y = vertical/depth position
 *
 * Architectural coordinates are expressed in meters.
 */
export interface Point2D {
  x: number;
  y: number;
}

/**
 * Basic 3D point.
 *
 * Coordinate system:
 * - x = horizontal position
 * - y = vertical/elevation
 * - z = depth position
 *
 * Architectural coordinates are expressed in meters.
 */
export interface Point3D {
  x: number;
  y: number;
  z: number;
}

/**
 * Width/height dimensions in meters.
 */
export interface Dimensions2D {
  width: number;
  height: number;
}

/**
 * Width/height/depth dimensions in meters.
 */
export interface Dimensions3D {
  width: number;
  height: number;
  depth: number;
}

/**
 * Axis-aligned rectangular bounds.
 */
export interface Bounds2D {
  min: Point2D;
  max: Point2D;
}

/**
 * Supported room categories.
 *
 * This is intentionally extensible.
 * New room types can be added as KIYUB develops.
 */
export type RoomType =
  | "living_room"
  | "dining_room"
  | "kitchen"
  | "bedroom"
  | "master_bedroom"
  | "bathroom"
  | "toilet"
  | "garage"
  | "laundry"
  | "storage"
  | "hallway"
  | "corridor"
  | "stairs"
  | "balcony"
  | "office"
  | "utility"
  | "porch"
  | "entry"
  | "other";

/**
 * Wall classification.
 */
export type WallType =
  | "exterior"
  | "interior"
  | "partition"
  | "structural";

/**
 * Opening classification.
 */
export type OpeningType =
  | "door"
  | "window"
  | "sliding_door"
  | "garage_door";

/**
 * Floor information.
 */
export interface Floor {
  /**
   * Unique floor identifier.
   *
   * Example:
   * "floor-1"
   */
  id: string;

  /**
   * Human-readable floor level.
   *
   * Example:
   * 1 = ground floor
   * 2 = second floor
   */
  level: number;

  /**
   * Elevation of the floor's finished floor level.
   *
   * Expressed in meters.
   */
  elevation: number;

  /**
   * Floor-to-floor height.
   *
   * Expressed in meters.
   */
  height: number;

  /**
   * IDs of rooms belonging to this floor.
   */
  roomIds: string[];

  /**
   * IDs of walls belonging to this floor.
   */
  wallIds: string[];

  /**
   * IDs of openings belonging to this floor.
   */
  openingIds: string[];

  /**
   * IDs of stairs associated with this floor.
   */
  stairIds: string[];
}

/**
 * Room entity.
 */
export interface Room {
  /**
   * Unique room identifier.
   *
   * Example:
   * "bedroom-1"
   */
  id: string;

  /**
   * Floor containing this room.
   */
  floorId: string;

  /**
   * Human-readable room name.
   *
   * Example:
   * "Master Bedroom"
   */
  name: string;

  /**
   * Functional room category.
   */
  type: RoomType;

  /**
   * Reference position for the room.
   *
   * Usually represents the minimum x/y point of the room.
   */
  position: Point2D;

  /**
   * Overall room dimensions.
   *
   * Expressed in meters.
   */
  dimensions: Dimensions2D;

  /**
   * Actual room boundary.
   *
   * This allows KIYUB to support non-rectangular rooms
   * in addition to simple rectangles.
   */
  polygon: Point2D[];

  /**
   * Calculated floor area.
   *
   * Expressed in square meters.
   */
  area: number;

  /**
   * IDs of walls defining this room.
   */
  wallIds: string[];

  /**
   * IDs of doors/windows/openings associated with this room.
   */
  openingIds: string[];

  /**
   * Optional room metadata.
   *
   * This allows future features without immediately
   * changing the core room structure.
   */
  metadata?: Record<string, unknown>;
}

/**
 * Wall entity.
 */
export interface Wall {
  /**
   * Unique wall identifier.
   */
  id: string;

  /**
   * Floor containing this wall.
   */
  floorId: string;

  /**
   * Wall classification.
   */
  type: WallType;

  /**
   * Starting point of wall centerline.
   */
  start: Point2D;

  /**
   * Ending point of wall centerline.
   */
  end: Point2D;

  /**
   * Wall thickness.
   *
   * Expressed in meters.
   */
  thickness: number;

  /**
   * Wall height.
   *
   * Expressed in meters.
   */
  height: number;

  /**
   * IDs of rooms connected/defined by this wall.
   *
   * Usually:
   * - exterior wall → one room
   * - interior wall → two rooms
   */
  roomIds: string[];

  /**
   * IDs of openings cut into this wall.
   */
  openingIds: string[];

  /**
   * Optional metadata.
   */
  metadata?: Record<string, unknown>;
}

/**
 * Door/window/opening entity.
 */
export interface Opening {
  /**
   * Unique opening identifier.
   */
  id: string;

  /**
   * Floor containing this opening.
   */
  floorId: string;

  /**
   * Wall containing this opening.
   */
  wallId: string;

  /**
   * Opening classification.
   */
  type: OpeningType;

  /**
   * Position of the opening.
   *
   * This represents the architectural position
   * of the opening in 2D space.
   */
  position: Point2D;

  /**
   * Opening width.
   *
   * Expressed in meters.
   */
  width: number;

  /**
   * Opening height.
   *
   * Expressed in meters.
   */
  height: number;

  /**
   * Height of the opening's bottom edge above
   * finished floor level.
   *
   * Doors normally use 0.
   * Windows normally have a positive sill height.
   */
  sillHeight: number;

  /**
   * Optional opening rotation.
   *
   * Expressed in degrees.
   */
  rotation?: number;

  /**
   * Optional metadata.
   */
  metadata?: Record<string, unknown>;
}

/**
 * Placed furniture / fixture entity (meters).
 */
export interface Furniture {
  id: string;
  roomId: string;
  kind: string;
  position: Point2D;
  dimensions: Dimensions2D;
  rotation: number;
  metadata?: Record<string, unknown>;
}

/**
 * Stair entity connecting two floors.
 */
export interface Stair {
  /**
   * Unique stair identifier.
   */
  id: string;

  /**
   * Floor where the stair begins.
   */
  fromFloorId: string;

  /**
   * Floor where the stair ends.
   */
  toFloorId: string;

  /**
   * Reference position of the stair.
   */
  position: Point2D;

  /**
   * Stair width.
   *
   * Expressed in meters.
   */
  width: number;

  /**
   * Stair length.
   *
   * Expressed in meters.
   */
  length: number;

  /**
   * Number of steps.
   */
  stepCount: number;

  /**
   * Stair rotation.
   *
   * Expressed in degrees.
   */
  rotation: number;

  /**
   * Optional metadata.
   */
  metadata?: Record<string, unknown>;
}

/**
 * Site/buildable lot information.
 */
export interface Site {
  /**
   * Lot width in meters.
   */
  width: number;

  /**
   * Lot depth in meters.
   */
  depth: number;

  /**
   * Optional site boundary polygon.
   *
   * If omitted, the site is assumed to be a rectangle:
   *
   * (0,0) → (width,0) → (width,depth) → (0,depth)
   */
  boundary?: Point2D[];

  /**
   * Optional metadata.
   */
  metadata?: Record<string, unknown>;
}

/**
 * Scene generation metadata.
 */
export interface SceneMetadata {
  /**
   * ISO timestamp when the scene was created.
   */
  createdAt: string;

  /**
   * ISO timestamp when the scene was last updated.
   */
  updatedAt: string;

  /**
   * Name of the system that generated the scene.
   *
   * Example:
   * "kiyub-generation-engine"
   */
  generator?: string;

  /**
   * Generator version.
   *
   * Example:
   * "3.0.0"
   */
  generatorVersion?: string;

  /**
   * ID of the ArchitecturalSpecification
   * that produced this scene.
   */
  sourceSpecificationId?: string;

  /**
   * Optional generation run identifier.
   */
  generationId?: string;

  /**
   * Optional additional metadata.
   */
  extra?: Record<string, unknown>;
}

/**
 * The canonical KIYUB v4 scene representation.
 *
 * This is the central contract shared by:
 *
 * Generation Engine
 *        ↓
 * SceneDocument
 *        ↓
 *  ┌─────┴─────┐
 *  ↓           ↓
 * 2D Editor   3D Viewer
 *
 * It may also be persisted to Supabase
 * and used for versioning.
 */
export interface SceneDocument {
  /**
   * SceneDocument schema version.
   */
  version: SceneDocumentVersion;

  /**
   * KIYUB project identifier.
   */
  projectId: string;

  /**
   * Architectural measurement system.
   */
  units: Units;

  /**
   * Number of floors in the building.
   *
   * This is intentionally separate from floorData,
   * because it is a convenient summary value.
   */
  floors: number;

  /**
   * Site/lot information.
   */
  site: Site;

  /**
   * Scene metadata.
   */
  metadata: SceneMetadata;

  /**
   * Floor entities.
   *
   * Named floorData to avoid collision with
   * the numeric `floors` property.
   */
  floorData: Floor[];

  /**
   * All rooms in the scene.
   */
  rooms: Room[];

  /**
   * All walls in the scene.
   */
  walls: Wall[];

  /**
   * All doors/windows/openings.
   */
  openings: Opening[];

  /**
   * Generated furniture / fixtures.
   */
  furniture: Furniture[];

  /**
   * All stairs.
   */
  stairs: Stair[];
}