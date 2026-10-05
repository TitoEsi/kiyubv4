import { describe, expect, it } from 'vitest'
import { renderToStaticMarkup } from 'react-dom/server'
import { FurnitureSymbol, furnitureBackSide } from './furniture-symbols'
import type { Furniture, Wall } from '../scene-graph/types'

const KINDS = [
  'bed', 'wardrobe', 'sofa', 'coffee_table', 'dining_table', 'counter', 'refrigerator',
  'stove', 'toilet', 'lavatory', 'shower', 'storage', 'vehicle', 'mystery_object',
]

function item(kind: string, over: Partial<Furniture> = {}): Furniture {
  return {
    id: `f-${kind}`,
    roomId: 'r1',
    kind,
    position: { x: 1, y: 1 },
    dimensions: { width: 2, height: 1.6 },
    rotation: 0,
    ...over,
  }
}

function wall(id: string, x1: number, y1: number, x2: number, y2: number): Wall {
  return { id, start: { x: x1, y: y1 }, end: { x: x2, y: y2 }, thickness: 0.15, type: 'interior' } as Wall
}

describe('FurnitureSymbol', () => {
  it.each(KINDS)('draws %s without text', kind => {
    for (const back of ['top', 'right', 'bottom', 'left'] as const) {
      const html = renderToStaticMarkup(
        <svg><FurnitureSymbol item={item(kind)} ox={0} oy={0} S={40} active={false} back={back} /></svg>,
      )
      expect(html).not.toContain('<text')
      expect(html).not.toContain(kind)
      expect(html).toContain('<rect')
    }
  })

  it('skips interior detail when the symbol is tiny', () => {
    const html = renderToStaticMarkup(
      <svg><FurnitureSymbol item={item('stove')} ox={0} oy={0} S={2} active={false} /></svg>,
    )
    expect(html).not.toContain('<circle')
  })
})

describe('furnitureBackSide', () => {
  const box = item('bed', { position: { x: 1, y: 1 }, dimensions: { width: 2, height: 1.6 } })

  it('picks the side nearest a wall', () => {
    expect(furnitureBackSide(box, [wall('n', 0, 0.9, 5, 0.9)])).toBe('top')
    expect(furnitureBackSide(box, [wall('s', 0, 2.7, 5, 2.7)])).toBe('bottom')
    expect(furnitureBackSide(box, [wall('w', 0.9, 0, 0.9, 5)])).toBe('left')
    expect(furnitureBackSide(box, [wall('e', 3.1, 0, 3.1, 5)])).toBe('right')
  })

  it('defaults to top without walls', () => {
    expect(furnitureBackSide(box, [])).toBe('top')
  })
})
