import { describe, expect, it } from 'vitest'
import { renderToStaticMarkup } from 'react-dom/server'
import ScenePlan2D, { wallJunctions, wallStrokePx } from './ScenePlan2D'
import { wallStrokeSegments } from './opening-symbols'
import { FIDELITY_PLAN } from '../scene-graph/adapters/fidelity.fixture'
import { loadLiveScene } from '../scene-graph/edit/load-scene'
import type { SceneDocument } from '../scene-graph/types'
import type { Comment } from '../workflow/api'

const base = loadLiveScene(FIDELITY_PLAN, undefined, { projectId: 'p' })

function wallWidths(scene: SceneDocument, zoom: number, trueWallThickness: boolean): Map<string, number> {
  const html = renderToStaticMarkup(
    <ScenePlan2D scene={scene} tool="select" snapEnabled={false} grid={0.3} editingEnabled={false}
      selected={null} onSelect={() => undefined} zoom={zoom} pan={{ x: 0, y: 0 }} trueWallThickness={trueWallThickness} />,
  )
  const layer = html.slice(html.indexOf('data-layer="walls"'), html.indexOf('data-layer="openings"'))
  const out = new Map<string, number>()
  const lines = [...layer.matchAll(/<line[^>]*stroke-width="([\d.]+)"/g)].map(m => Number(m[1]))
  let i = 0
  for (const w of scene.walls) {
    out.set(w.id, lines[i])
    i += wallStrokeSegments(w, scene.openings).length
  }
  return out
}

describe('ScenePlan2D wall thickness', () => {
  it('keeps the fixed hairline stroke unless true thickness is requested', () => {
    expect(new Set(wallWidths(base, 1, false).values())).toEqual(new Set([3.5]))
  })

  it('draws walls at thickness × scale, following zoom and per-wall thickness', () => {
    const scene: SceneDocument = { ...base, walls: base.walls.map((w, i) => (i === 0 ? { ...w, thickness: 0.3 } : w)) }
    const z1 = wallWidths(scene, 1, true)
    const z2 = wallWidths(scene, 2, true)
    const thick = scene.walls[0], thin = scene.walls[1]
    expect(z2.get(thin.id)! / z1.get(thin.id)!).toBeCloseTo(2, 2)
    expect(z1.get(thick.id)! / z1.get(thin.id)!).toBeCloseTo(2, 2)
  })

  it('never draws a wall thinner than the visibility floor', () => {
    expect(wallStrokePx({ ...base.walls[0], thickness: 0.15 }, 100)).toBeCloseTo(15, 9)
    expect(wallStrokePx({ ...base.walls[0], thickness: 0.15 }, 1)).toBe(2)
  })

  it('caps every junction shared by two or more walls', () => {
    const joints = wallJunctions(base.walls)
    expect(joints.length).toBeGreaterThan(0)
    for (const j of joints) {
      const meeting = base.walls.filter(w =>
        (w.start.x === j.p.x && w.start.y === j.p.y) || (w.end.x === j.p.x && w.end.y === j.p.y))
      expect(meeting.length).toBeGreaterThanOrEqual(2)
    }
  })
  it('keeps exterior dimension chains off the interactive canvas', () => {
    const html = renderToStaticMarkup(
      <ScenePlan2D scene={base} tool="select" snapEnabled={false} grid={0.3} editingEnabled={false}
        selected={null} onSelect={() => undefined} zoom={1} pan={{ x: 0, y: 0 }} />,
    )
    expect(html).not.toContain('data-sheet-dimensions')
    expect(html).toContain('paint-order="stroke"')
    const labels = html.slice(html.indexOf('data-layer="labels"'), html.indexOf('data-layer="dimensions"'))
    expect(labels).toContain('fill="#2a2d31"')
    expect(labels).not.toContain('stroke="none"')
  })
})

describe('ScenePlan2D document sheet', () => {
  it('draws the plan without canvas UI, comments, or selection handles', () => {
    const note = {
      id: 'c1',
      body: 'Move the wall',
      author_id: 'u',
      created_at: '2026-10-05T00:00:00Z',
      x: 2,
      y: 2,
      author_role: 'CLIENT',
    } as Comment
    const html = renderToStaticMarkup(
      <ScenePlan2D
        frame={{ width: 900, height: 640 }}
        scene={base}
        lot={{ width: 20, depth: 30, shape: 'rectangle' }}
        tool="select"
        snapEnabled
        grid={0.3}
        editingEnabled
        selected={{ kind: 'wall', id: base.walls[0].id }}
        onSelect={() => undefined}
        zoom={2.4}
        pan={{ x: 80, y: -40 }}
        annotations={[note]}
        annotationMode
      />,
    )
    const walls = html.slice(html.indexOf('data-layer="walls"'), html.indexOf('data-layer="openings"'))
    const openings = html.slice(html.indexOf('data-layer="openings"'), html.indexOf('data-layer="dimension-lines"'))
    const furniture = html.slice(html.indexOf('data-layer="furniture"'), html.indexOf('data-layer="walls"'))
    const lines = html.slice(html.indexOf('data-layer="dimension-lines"'), html.indexOf('data-layer="dimension-text"'))
    const values = html.slice(html.indexOf('data-layer="dimension-text"'), html.indexOf('data-layer="labels"'))
    const labels = html.slice(html.indexOf('data-layer="labels"'), html.indexOf('data-north="sheet"'))
    expect(html.indexOf('data-layer="dimension-lines"')).toBeLessThan(html.indexOf('data-layer="dimension-text"'))
    expect(html.indexOf('data-layer="dimension-text"')).toBeLessThan(html.indexOf('data-layer="labels"'))
    expect(html.indexOf('data-layer="labels"')).toBeLessThan(html.indexOf('data-north="sheet"'))
    expect(html).toContain('data-document="true"')
    expect(html).toContain('class="plan-room-label"')
    expect(html).toContain('font-size="')
    expect(walls).toContain('stroke-linecap="butt"')
    expect(openings).toContain('<path')
    expect(furniture).toContain('<rect')
    expect(html).toContain('data-north="true"')
    expect(html).toContain('>N</text>')
    expect(html).toContain('data-footprint="true"')
    expect(html).toContain('data-sheet-dimensions="true"')
    expect(lines).toContain('<path')
    expect(lines).toContain('stroke="#17191c"')
    expect(lines).toContain('stroke-width="1.1"')
    expect(values).not.toContain('#faf9f5')
    expect(values).not.toContain('paint-order')
    expect(values).toContain('fill="#17191c"')
    expect(values).toContain('stroke="none"')
    expect(values).toContain('font-weight="normal"')
    expect(labels.match(/class="plan-room-label"/g)?.length).toBe(base.rooms.length)
    expect(labels).toContain('fill="#17191c"')
    expect(labels).toContain('stroke="none"')
    expect(labels).toContain('font-weight="bold"')
    expect(labels).not.toContain('paint-order')
    const labelText = labels.replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ')
    for (const room of base.rooms) expect(labelText).toContain(room.name.toUpperCase())
    expect(html).toContain('font-family="Helvetica"')
    expect(html).not.toContain('plan-sticky')
    expect(html).not.toContain('data-comment-id')
    expect(html).not.toContain('north-indicator')
    expect(html).not.toContain('class="plan-note')
  })
})
