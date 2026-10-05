import { describe, expect, it } from 'vitest'
import { renderToStaticMarkup } from 'react-dom/server'
import NorthIndicator from './NorthIndicator'
import ScenePlan2D, { type EditorTool } from './ScenePlan2D'
import { floorPlanToSceneDocument } from '../scene-graph/adapters/floorplan-to-scene-document'
import { FIDELITY_PLAN } from '../scene-graph/adapters/fidelity.fixture'
import type { SiteLot } from '../scene-graph/site/site-context'
import type { SceneDocument } from '../scene-graph/types'
import { roomFill } from '../scene-graph/room-colors'

const scene = floorPlanToSceneDocument(FIDELITY_PLAN, { lotWidth: 15, lotDepth: 20, stories: 1 })

const ENGINE_KINDS = [
  'bed', 'wardrobe', 'sofa', 'coffee_table', 'dining_table', 'counter', 'refrigerator',
  'stove', 'toilet', 'lavatory', 'shower', 'storage', 'vehicle',
]

function renderPlan(
  zoom: number,
  pan: { x: number; y: number },
  editingEnabled: boolean,
  lot?: SiteLot | null,
  opts: {
    doc?: SceneDocument
    insets?: { top?: number }
    tool?: EditorTool
    annotationMode?: boolean
    onPanZoom?: (zoom: number, pan: { x: number; y: number }) => void
  } = {},
) {
  return renderToStaticMarkup(
    <ScenePlan2D
      scene={opts.doc ?? scene}
      lot={lot}
      insets={opts.insets}
      tool={opts.tool ?? 'select'}
      annotationMode={opts.annotationMode}
      onPanZoom={opts.onPanZoom}
      snapEnabled={false}
      grid={0.3}
      editingEnabled={editingEnabled}
      selected={null}
      onSelect={() => {}}
      zoom={zoom}
      pan={pan}
    />,
  )
}

function indicators(html: string): string[] {
  return html.match(/<div class="north-indicator"[\s\S]*?<\/svg><\/div>/g) ?? []
}

describe('NorthIndicator', () => {
  it('labels North with an N', () => {
    const html = renderToStaticMarkup(<NorthIndicator />)
    expect(html).toContain('class="north-indicator"')
    expect(html).toContain('aria-label="North"')
    expect(html).toMatch(/>N<\/text>/)
  })

  it.each([true, false])('renders once and ignores pan/zoom (editingEnabled=%s)', editingEnabled => {
    const small = indicators(renderPlan(0.5, { x: 0, y: 0 }, editingEnabled))
    const large = indicators(renderPlan(1.5, { x: 120, y: -80 }, editingEnabled))
    expect(small).toHaveLength(1)
    expect(large).toHaveLength(1)
    expect(large[0]).toBe(small[0])
    expect(small[0]).toBe(renderToStaticMarkup(<NorthIndicator />))
  })
})

describe('ScenePlan2D layers', () => {
  const lot = { width: 20, depth: 30 }

  it.each([true, false])('stacks layers back to front (editingEnabled=%s)', editingEnabled => {
    const html = renderPlan(1, { x: 0, y: 0 }, editingEnabled, lot)
    const order = [...html.matchAll(/data-layer="([a-z]+)"/g)].map(m => m[1])
    expect(order).toEqual(['site', 'landscape', 'rooms', 'furniture', 'walls', 'openings', 'labels', 'dimensions'])
    expect(html.indexOf('data-layer="site"')).toBeLessThan(html.indexOf('<polygon'))
    expect(indicators(html)).toHaveLength(1)
  })

  it('fills rooms by type and labels lot dimensions only for a real lot', () => {
    const real = renderPlan(1, { x: 0, y: 0 }, false, lot)
    for (const room of scene.rooms) expect(real).toContain(`fill="${roomFill(room.type)}"`)
    expect(real).toContain('20 m')
    const inferred = renderPlan(1, { x: 0, y: 0 }, false, null)
    expect(inferred).toContain('stroke-dasharray="4 3"')
    expect(inferred).not.toContain('20 m')
  })

  it('never renders furniture kind text', () => {
    const base = scene.furniture[0]
    const doc: SceneDocument = {
      ...scene,
      furniture: ENGINE_KINDS.map((kind, i) => ({ ...base, id: `f-${i}`, kind })),
    }
    const html = renderPlan(1, { x: 0, y: 0 }, false, lot, { doc })
    for (const kind of ENGINE_KINDS) expect(html).not.toMatch(new RegExp(`>\\s*${kind}\\s*<`))
  })

  it('draws at most one label per room, inside the labels layer', () => {
    const html = renderPlan(1, { x: 0, y: 0 }, false, lot)
    const labels = html.match(/class="plan-room-label"/g) ?? []
    expect(labels.length).toBeGreaterThan(0)
    expect(labels.length).toBeLessThanOrEqual(scene.rooms.length)
    const layer = html.slice(html.indexOf('data-layer="labels"'), html.indexOf('data-layer="dimensions"'))
    expect((layer.match(/class="plan-room-label"/g) ?? []).length).toBe(labels.length)
  })

  it('shifts the drawing origin by the top inset', () => {
    const lotY = (html: string) => Number(html.match(/<g data-layer="site"[^>]*><rect x="[^"]*" y="([^"]*)"/)?.[1])
    const plain = renderPlan(1, { x: 0, y: 0 }, false, lot)
    const inset = renderPlan(1, { x: 0, y: 0 }, false, lot, { insets: { top: 56 } })
    expect(lotY(plain)).toBeCloseTo(48)
    expect(lotY(inset)).toBeCloseTo(104)
  })
})

describe('ScenePlan2D pan', () => {
  const lot = { width: 20, depth: 30 }
  const noop = () => {}
  const lotRect = (html: string) => {
    const tag = html.match(/<g data-layer="site"[^>]*>(<rect [^>]*>)/)?.[1] ?? ''
    const attr = (name: string) => Number(tag.match(new RegExp(` ${name}="([^"]*)"`))?.[1])
    return { x: attr('x'), y: attr('y'), w: attr('width'), h: attr('height') }
  }
  const svgCursor = (html: string) => html.match(/<svg[^>]*cursor:([a-z-]+)/)?.[1]

  it('clamps an out-of-range pan so the plan cannot leave the view', () => {
    const far = lotRect(renderPlan(3, { x: 1e5, y: 1e5 }, false, lot, { onPanZoom: noop }))
    expect(far.x).toBeCloseTo(48)
    expect(far.y).toBeCloseTo(48)
    const near = lotRect(renderPlan(3, { x: -1e5, y: -1e5 }, false, lot, { onPanZoom: noop }))
    expect(near.x + near.w).toBeCloseTo(800 - 48)
    expect(near.y + near.h).toBeCloseTo(600 - 48)
  })

  it('applies an in-range pan unchanged', () => {
    const base = lotRect(renderPlan(3, { x: 0, y: 0 }, false, lot))
    const moved = lotRect(renderPlan(3, { x: -40, y: -60 }, false, lot))
    expect(moved.x - base.x).toBeCloseTo(-40)
    expect(moved.y - base.y).toBeCloseTo(-60)
  })

  it('pans only the viewport, never the scene', () => {
    const before = JSON.stringify(scene)
    const a = renderPlan(2.5, { x: -120, y: -300 }, true, lot, { onPanZoom: noop })
    const b = renderPlan(2.5, { x: 0, y: 0 }, true, lot, { onPanZoom: noop })
    expect(JSON.stringify(scene)).toBe(before)
    expect(a.match(/<polygon/g)?.length).toBe(b.match(/<polygon/g)?.length)
  })

  it.each([true, false])('shows a grab cursor only when empty-canvas pan is available (editingEnabled=%s)', editingEnabled => {
    expect(svgCursor(renderPlan(2, { x: 0, y: 0 }, editingEnabled, lot, { onPanZoom: noop }))).toBe('grab')
    expect(svgCursor(renderPlan(1, { x: 0, y: 0 }, editingEnabled, lot, { onPanZoom: noop }))).toBe('default')
    expect(svgCursor(renderPlan(0.6, { x: 0, y: 0 }, editingEnabled, lot, { onPanZoom: noop }))).toBe('default')
    expect(svgCursor(renderPlan(2, { x: 0, y: 0 }, editingEnabled, lot))).toBe('default')
    expect(svgCursor(renderPlan(2, { x: 0, y: 0 }, editingEnabled, lot, { onPanZoom: noop, tool: 'wall' }))).toBe('crosshair')
    expect(svgCursor(renderPlan(2, { x: 0, y: 0 }, editingEnabled, lot, { onPanZoom: noop, annotationMode: true }))).toBe('crosshair')
  })

  it('keeps the default cursor over walls while pan is available', () => {
    const walls = (html: string) => html.slice(html.indexOf('data-layer="walls"'), html.indexOf('data-layer="openings"'))
    expect(walls(renderPlan(2, { x: 0, y: 0 }, true, lot, { onPanZoom: noop }))).toContain('cursor:default')
    expect(walls(renderPlan(1, { x: 0, y: 0 }, true, lot, { onPanZoom: noop }))).not.toContain('cursor:default')
  })
})
