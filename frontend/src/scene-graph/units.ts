/** SceneDocument stores meters. FloorPlan / UI labels use feet. */

export const FEET_TO_METERS = 1 / 3.28084
export const METERS_TO_FEET = 3.28084

export function ftToM(value: number): number {
  return value * FEET_TO_METERS
}

export function mToFt(value: number): number {
  return value * METERS_TO_FEET
}

export function formatFeet(meters: number, digits = 2): string {
  const ft = mToFt(meters)
  return `${ft.toFixed(digits)}'`
}
