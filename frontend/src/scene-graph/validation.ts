/**
 * KIYUB v4 - SceneDocument Validation
 *
 * This validator checks structural/data integrity.
 *
 * It does NOT determine whether a building complies
 * with Philippine building regulations.
 *
 * Building-code validation belongs in the generation/
 * constraint layer.
 */

import type {
    Opening,
    Room,
    SceneDocument,
    Stair,
    Wall,
  } from "./types";
  
  export interface SceneValidationResult {
    valid: boolean;
    errors: string[];
    warnings: string[];
  }
  
  /**
   * Validate a SceneDocument.
   */
  export function validateSceneDocument(
    scene: SceneDocument
  ): string[] {
    return validateSceneDocumentDetailed(scene).errors;
  }
  
  /**
   * Detailed SceneDocument validation.
   */
  export function validateSceneDocumentDetailed(
    scene: SceneDocument
  ): SceneValidationResult {
    const errors: string[] = [];
    const warnings: string[] = [];
  
    /*
     * -------------------------------------------------------
     * Basic document validation
     * -------------------------------------------------------
     */
  
    if (scene.version !== "2.0") {
      errors.push(
        `Unsupported SceneDocument version: ${scene.version}`
      );
    }
  
    if (!scene.projectId.trim()) {
      errors.push("projectId must not be empty.");
    }
  
    if (scene.units !== "metric") {
      errors.push(
        `Unsupported units: ${scene.units}. KIYUB currently uses metric units.`
      );
    }
  
    /*
     * -------------------------------------------------------
     * Site validation
     * -------------------------------------------------------
     */
  
    if (!Number.isFinite(scene.site.width)) {
      errors.push("Site width must be a finite number.");
    } else if (scene.site.width <= 0) {
      errors.push("Site width must be greater than zero.");
    }
  
    if (!Number.isFinite(scene.site.depth)) {
      errors.push("Site depth must be a finite number.");
    } else if (scene.site.depth <= 0) {
      errors.push("Site depth must be greater than zero.");
    }
  
    if (scene.site.boundary) {
      if (scene.site.boundary.length < 3) {
        errors.push(
          "Site boundary must contain at least 3 points."
        );
      }
    }
  
    /*
     * -------------------------------------------------------
     * Floor validation
     * -------------------------------------------------------
     */
  
    if (!Number.isInteger(scene.floors)) {
      errors.push("floors must be an integer.");
    } else if (scene.floors <= 0) {
      errors.push(
        "Scene must contain at least one floor."
      );
    }
  
    if (scene.floorData.length !== scene.floors) {
      errors.push(
        `floors (${scene.floors}) does not match floorData length (${scene.floorData.length}).`
      );
    }
  
    validateFloors(scene, errors, warnings);
  
    /*
     * -------------------------------------------------------
     * Room validation
     * -------------------------------------------------------
     */
  
    validateRooms(scene, errors, warnings);
  
    /*
     * -------------------------------------------------------
     * Wall validation
     * -------------------------------------------------------
     */
  
    validateWalls(scene, errors, warnings);
  
    /*
     * -------------------------------------------------------
     * Opening validation
     * -------------------------------------------------------
     */
  
    validateOpenings(scene, errors, warnings);
  
    /*
     * -------------------------------------------------------
     * Stair validation
     * -------------------------------------------------------
     */
  
    validateStairs(scene, errors, warnings);
  
    /*
     * -------------------------------------------------------
     * Metadata validation
     * -------------------------------------------------------
     */
  
    if (!scene.metadata.createdAt.trim()) {
      errors.push("metadata.createdAt must not be empty.");
    }
  
    if (!scene.metadata.updatedAt.trim()) {
      errors.push("metadata.updatedAt must not be empty.");
    }
  
    return {
      valid: errors.length === 0,
      errors,
      warnings,
    };
  }
  
  /**
   * Validate floors and their references.
   */
  function validateFloors(
    scene: SceneDocument,
    errors: string[],
    warnings: string[]
  ): void {
    const floorIds = new Set<string>();
  
    for (const floor of scene.floorData) {
      if (!floor.id.trim()) {
        errors.push("Floor ID must not be empty.");
      }
  
      if (floorIds.has(floor.id)) {
        errors.push(
          `Duplicate floor ID: ${floor.id}`
        );
      }
  
      floorIds.add(floor.id);
  
      if (!Number.isInteger(floor.level)) {
        errors.push(
          `Floor ${floor.id} level must be an integer.`
        );
      }
  
      if (floor.level <= 0) {
        errors.push(
          `Floor ${floor.id} level must be greater than zero.`
        );
      }
  
      if (floor.elevation < 0) {
        warnings.push(
          `Floor ${floor.id} has a negative elevation.`
        );
      }
  
      if (floor.height <= 0) {
        errors.push(
          `Floor ${floor.id} height must be greater than zero.`
        );
      }
    }
  
    /*
     * Check floor level uniqueness.
     */
    const levels = scene.floorData.map(
      (floor) => floor.level
    );
  
    if (new Set(levels).size !== levels.length) {
      errors.push(
        "Multiple floors use the same floor level."
      );
    }
  }
  
  /**
   * Validate rooms.
   */
  function validateRooms(
    scene: SceneDocument,
    errors: string[],
    warnings: string[]
  ): void {
    const roomIds = new Set<string>();
    const floorIds = new Set(
      scene.floorData.map((floor) => floor.id)
    );
  
    for (const room of scene.rooms) {
      validateRoom(
        room,
        roomIds,
        floorIds,
        errors,
        warnings
      );
    }
  }
  
  /**
   * Validate an individual room.
   */
  function validateRoom(
    room: Room,
    roomIds: Set<string>,
    floorIds: Set<string>,
    errors: string[],
    warnings: string[]
  ): void {
    if (!room.id.trim()) {
      errors.push("Room ID must not be empty.");
    }
  
    if (roomIds.has(room.id)) {
      errors.push(
        `Duplicate room ID: ${room.id}`
      );
    }
  
    roomIds.add(room.id);
  
    if (!floorIds.has(room.floorId)) {
      errors.push(
        `Room ${room.id} references unknown floor ${room.floorId}.`
      );
    }
  
    if (!room.name.trim()) {
      warnings.push(
        `Room ${room.id} has no display name.`
      );
    }
  
    if (room.dimensions.width <= 0) {
      errors.push(
        `Room ${room.id} has invalid width.`
      );
    }
  
    if (room.dimensions.height <= 0) {
      errors.push(
        `Room ${room.id} has invalid height.`
      );
    }
  
    if (room.area < 0) {
      errors.push(
        `Room ${room.id} has invalid area.`
      );
    }
  
    if (room.polygon.length < 3) {
      errors.push(
        `Room ${room.id} polygon must contain at least 3 points.`
      );
    }
  
    if (
      !Number.isFinite(room.position.x) ||
      !Number.isFinite(room.position.y)
    ) {
      errors.push(
        `Room ${room.id} has an invalid position.`
      );
    }
  }
  
  /**
   * Validate walls.
   */
  function validateWalls(
    scene: SceneDocument,
    errors: string[],
    warnings: string[]
  ): void {
    const wallIds = new Set<string>();
    const floorIds = new Set(
      scene.floorData.map((floor) => floor.id)
    );
    const roomIds = new Set(
      scene.rooms.map((room) => room.id)
    );
  
    for (const wall of scene.walls) {
      validateWall(
        wall,
        wallIds,
        floorIds,
        roomIds,
        errors,
        warnings
      );
    }
  }
  
  /**
   * Validate an individual wall.
   */
  function validateWall(
    wall: Wall,
    wallIds: Set<string>,
    floorIds: Set<string>,
    roomIds: Set<string>,
    errors: string[],
    warnings: string[]
  ): void {
    if (!wall.id.trim()) {
      errors.push("Wall ID must not be empty.");
    }
  
    if (wallIds.has(wall.id)) {
      errors.push(
        `Duplicate wall ID: ${wall.id}`
      );
    }
  
    wallIds.add(wall.id);
  
    if (!floorIds.has(wall.floorId)) {
      errors.push(
        `Wall ${wall.id} references unknown floor ${wall.floorId}.`
      );
    }
  
    if (wall.thickness <= 0) {
      errors.push(
        `Wall ${wall.id} has invalid thickness.`
      );
    }
  
    if (wall.height <= 0) {
      errors.push(
        `Wall ${wall.id} has invalid height.`
      );
    }
  
    if (
      wall.start.x === wall.end.x &&
      wall.start.y === wall.end.y
    ) {
      errors.push(
        `Wall ${wall.id} has zero length.`
      );
    }
  
    for (const roomId of wall.roomIds) {
      if (!roomIds.has(roomId)) {
        errors.push(
          `Wall ${wall.id} references unknown room ${roomId}.`
        );
      }
    }
  }
  
  /**
   * Validate openings.
   */
  function validateOpenings(
    scene: SceneDocument,
    errors: string[],
    warnings: string[]
  ): void {
    const openingIds = new Set<string>();
    const floorIds = new Set(
      scene.floorData.map((floor) => floor.id)
    );
    const wallIds = new Set(
      scene.walls.map((wall) => wall.id)
    );
  
    for (const opening of scene.openings) {
      if (!opening.id.trim()) {
        errors.push(
          "Opening ID must not be empty."
        );
      }
  
      if (openingIds.has(opening.id)) {
        errors.push(
          `Duplicate opening ID: ${opening.id}`
        );
      }
  
      openingIds.add(opening.id);
  
      if (!floorIds.has(opening.floorId)) {
        errors.push(
          `Opening ${opening.id} references unknown floor ${opening.floorId}.`
        );
      }
  
      if (!wallIds.has(opening.wallId)) {
        errors.push(
          `Opening ${opening.id} references unknown wall ${opening.wallId}.`
        );
      }
  
      if (opening.width <= 0) {
        errors.push(
          `Opening ${opening.id} has invalid width.`
        );
      }
  
      if (opening.height <= 0) {
        errors.push(
          `Opening ${opening.id} has invalid height.`
        );
      }
  
      if (opening.sillHeight < 0) {
        errors.push(
          `Opening ${opening.id} has invalid sill height.`
        );
      }
    }
  }
  
  /**
   * Validate stairs.
   */
  function validateStairs(
    scene: SceneDocument,
    errors: string[],
    warnings: string[]
  ): void {
    const stairIds = new Set<string>();
    const floorIds = new Set(
      scene.floorData.map((floor) => floor.id)
    );
  
    for (const stair of scene.stairs) {
      if (!stair.id.trim()) {
        errors.push(
          "Stair ID must not be empty."
        );
      }
  
      if (stairIds.has(stair.id)) {
        errors.push(
          `Duplicate stair ID: ${stair.id}`
        );
      }
  
      stairIds.add(stair.id);
  
      if (!floorIds.has(stair.fromFloorId)) {
        errors.push(
          `Stair ${stair.id} references unknown fromFloorId ${stair.fromFloorId}.`
        );
      }
  
      if (!floorIds.has(stair.toFloorId)) {
        errors.push(
          `Stair ${stair.id} references unknown toFloorId ${stair.toFloorId}.`
        );
      }
  
      if (stair.fromFloorId === stair.toFloorId) {
        warnings.push(
          `Stair ${stair.id} connects the same floor.`
        );
      }
  
      if (stair.width <= 0) {
        errors.push(
          `Stair ${stair.id} has invalid width.`
        );
      }
  
      if (stair.length <= 0) {
        errors.push(
          `Stair ${stair.id} has invalid length.`
        );
      }
  
      if (!Number.isInteger(stair.stepCount)) {
        errors.push(
          `Stair ${stair.id} stepCount must be an integer.`
        );
      } else if (stair.stepCount <= 0) {
        errors.push(
          `Stair ${stair.id} stepCount must be greater than zero.`
        );
      }
    }
  }