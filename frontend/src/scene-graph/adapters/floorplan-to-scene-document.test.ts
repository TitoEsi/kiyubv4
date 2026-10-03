import { describe, expect, it } from "vitest";
import type { FloorPlan } from "../../types/floorplan";
import { floorPlanToSceneDocument } from "./floorplan-to-scene-document";
import { normalizeFloorPlan } from "../../units/legacy";

/** PLAN is a legacy feet plan (no `units`). */
const FEET_TO_METERS = 0.3048;

const PLAN: FloorPlan = {
  id: "baseline",
  name: "KIYUB v4 baseline",
  totalWidth: 55.5,
  totalHeight: 88.3,
  ceilingHeight: 9,
  rooms: [
    {
      id: "living",
      name: "Living Room",
      type: "living_room",
      x: 10,
      y: 10,
      width: 14,
      height: 16,
      color: "#ccc",
    },
    {
      id: "kitchen",
      name: "Kitchen",
      type: "kitchen",
      x: 24,
      y: 10,
      width: 12,
      height: 12,
      color: "#ddd",
    },
  ],
  doors: [],
};

describe("floorPlanToSceneDocument", () => {
  it("uses questionnaire lot meters for site, not the OR-Tools envelope", () => {
    const scene = floorPlanToSceneDocument(PLAN, { lotWidth: 20, lotDepth: 30, stories: 1 });
    expect(scene.version).toBe("2.0");
    expect(scene.units).toBe("metric");
    expect(scene.site.width).toBe(20);
    expect(scene.site.depth).toBe(30);
    expect(scene.site.width).not.toBe(PLAN.totalWidth);
    expect(scene.site.depth).not.toBe(PLAN.totalHeight);
    expect(scene.rooms.length).toBeGreaterThan(0);
    expect(scene.floors).toBe(1);
  });

  it("uses metric plans as-is without scaling", () => {
    const metric: FloorPlan = { ...PLAN, units: "metric", rooms: [{ ...PLAN.rooms[0], x: 1, y: 2, width: 4.2, height: 3.6 }] };
    const scene = floorPlanToSceneDocument(metric, { lotWidth: 20, lotDepth: 30 });
    const living = scene.rooms.find((r) => r.id === "living")!;
    expect(living.position).toEqual({ x: 1, y: 2 });
    expect(living.dimensions.width).toBeCloseTo(4.2, 9);
    expect(living.dimensions.height).toBeCloseTo(3.6, 9);
  });

  it("gives the same scene for a legacy plan and its normalized form", () => {
    const a = floorPlanToSceneDocument(PLAN, { lotWidth: 20, lotDepth: 30 });
    const b = floorPlanToSceneDocument(normalizeFloorPlan(PLAN), { lotWidth: 20, lotDepth: 30 });
    expect(b.rooms).toEqual(a.rooms);
  });

  it("converts legacy room geometry from feet to meters", () => {
    const scene = floorPlanToSceneDocument(PLAN, { lotWidth: 20, lotDepth: 30 });
    const living = scene.rooms.find((r) => r.id === "living");
    expect(living).toBeDefined();
    expect(living!.dimensions.width).toBeCloseTo(14 * FEET_TO_METERS, 5);
    expect(living!.dimensions.height).toBeCloseTo(16 * FEET_TO_METERS, 5);
  });

  it("does not invent walls the engine does not emit", () => {
    const scene = floorPlanToSceneDocument(PLAN, { lotWidth: 20, lotDepth: 30 });
    expect(scene.walls).toEqual([]);
    expect(scene.openings).toEqual([]);
  });

  it("maps engine-emitted walls and openings without fabricating extras", () => {
    const populated: FloorPlan = {
      ...PLAN,
      walls: [
        {
          id: "w0",
          x1: 10,
          y1: 10,
          x2: 24,
          y2: 10,
          kind: "exterior",
          roomIds: ["living"],
        },
      ],
      openings: [
        {
          id: "win0",
          wallId: "w0",
          kind: "window",
          x: 14,
          y: 10,
          width: 4,
          height: 4,
          isVertical: false,
          roomIds: ["living"],
          sillHeight: 3,
        },
      ],
    };
    const scene = floorPlanToSceneDocument(populated, { lotWidth: 20, lotDepth: 30 });
    expect(scene.walls).toHaveLength(1);
    expect(scene.walls[0].id).toBe("w0");
    expect(scene.walls[0].start.x).toBeCloseTo(10 * FEET_TO_METERS, 5);
    expect(scene.openings).toHaveLength(1);
    expect(scene.openings[0].wallId).toBe("w0");
    expect(scene.rooms.find((r) => r.id === "living")?.wallIds).toContain("w0");
  });

  it("records daylight potential metadata without fabricating openings", () => {
    const scene = floorPlanToSceneDocument(PLAN, { lotWidth: 20, lotDepth: 30 });
    const living = scene.rooms.find((r) => r.id === "living");
    expect(living?.metadata?.sourceType).toBe("living_room");
    expect(living?.metadata).toHaveProperty("daylightPotential");
    expect(scene.openings).toEqual([]);
  });
});
