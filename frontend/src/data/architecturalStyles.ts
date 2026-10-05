export const ARCHITECTURAL_STYLES = [
  { id: 'modern', label: 'Modern', hint: 'clean geometry' },
  { id: 'traditional', label: 'Traditional', hint: 'formal rooms' },
  { id: 'contemporary', label: 'Contemporary', hint: 'current forms' },
  { id: 'japandi', label: 'Japandi', hint: 'calm + natural' },
  { id: 'minimalist', label: 'Minimalist', hint: 'reduced clutter' },
  { id: 'brutalist', label: 'Brutalist', hint: 'bold massing' },
  { id: 'modern_tropical', label: 'Modern Tropical', hint: 'climate-responsive' },
  { id: 'filipino_contemporary', label: 'Filipino Contemporary', hint: 'indoor / outdoor' },
  { id: 'tropical_minimalist', label: 'Tropical Minimalist', hint: 'shade + light' },
] as const

/** No longer offered; saved briefs may still carry these ids and must pick a new style to generate. */
export const RETIRED_STYLES: Record<string, string> = { craftsman: 'Craftsman', farmhouse: 'Farmhouse' }
