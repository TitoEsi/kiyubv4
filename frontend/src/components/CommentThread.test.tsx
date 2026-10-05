import { describe, expect, it } from 'vitest'
import { renderToStaticMarkup } from 'react-dom/server'
import CommentThread, { type CommentActions } from './CommentThread'
import SidebarComments from './SidebarComments'
import ScenePlan2D from './ScenePlan2D'
import type { Comment } from '../workflow/api'
import { buildThreads } from '../workflow/commentThreads'
import { FIDELITY_PLAN } from '../scene-graph/adapters/fidelity.fixture'
import { loadLiveScene } from '../scene-graph/edit/load-scene'
import type { PlanAnnotation } from './planAnnotations'

const noop = () => {}
const comment = (id: string, extra: Partial<Comment> = {}): Comment => ({
  id,
  body: `Body ${id}`,
  author_id: 'client-1',
  author_email: 'client@example.com',
  author_role: 'CLIENT',
  created_at: '2026-10-05T02:15:00Z',
  ...extra,
})

const architect: CommentActions = { currentUserId: 'arch-1', canResolve: true, canComment: true, onReply: noop, onEdit: noop, onResolve: noop }
const client: CommentActions = { currentUserId: 'client-1', canResolve: false, canComment: true, onReply: noop, onEdit: noop, onResolve: noop }

describe('CommentThread', () => {
  const [thread] = buildThreads([
    comment('c1', { edit_history: [{ previous: 'Old text', body: 'Body c1', edited_by: 'client-1', edited_by_role: 'CLIENT', edited_at: '2026-10-05T03:00:00Z' }] }),
    comment('r1', { parent_id: 'c1', author_id: 'arch-1', author_role: 'ARCHITECT', author_email: 'arch@example.com' }),
  ])

  it('renders the comment, its replies, an Edited marker and a reply box', () => {
    const html = renderToStaticMarkup(<CommentThread thread={thread} actions={client} />)
    expect(html).toContain('Body c1')
    expect(html).toContain('class="comment-replies"')
    expect(html).toContain('Body r1')
    expect(html).toContain('>Edited</button>')
    expect(html).toContain('aria-label="Reply to comment"')
  })

  it('lets only the author edit, and never offers Delete', () => {
    const own = renderToStaticMarkup(<CommentThread thread={thread} actions={client} />)
    expect((own.match(/>Edit<\/button>/g) || []).length).toBe(1)
    const other = renderToStaticMarkup(<CommentThread thread={{ ...thread, replies: [] }} actions={architect} />)
    expect(other).not.toContain('>Edit</button>')
    expect(own).not.toMatch(/Delete/i)
    expect(other).not.toMatch(/Delete/i)
  })

  it('shows the Resolved checkbox to the Architect only', () => {
    expect(renderToStaticMarkup(<CommentThread thread={thread} actions={architect} />)).toContain('type="checkbox"')
    expect(renderToStaticMarkup(<CommentThread thread={thread} actions={client} />)).not.toContain('type="checkbox"')
  })

  it('shows who resolved it, the resolution and the related version', () => {
    const html = renderToStaticMarkup(<CommentThread thread={{
      ...thread, resolved: true, resolved_by_role: 'ARCHITECT', resolved_at: '2026-10-05T04:00:00Z',
      resolution_note: 'Widened the door', resolution_version: 6,
    }} actions={client} />)
    expect(html).toContain('Resolved by Architect')
    expect(html).toContain('Resolution: Widened the door')
    expect(html).toContain('Related version: Version 6')
  })
})

describe('SidebarComments', () => {
  const threads = buildThreads([comment('a'), comment('b', { resolved: true }), comment('r', { parent_id: 'a' })])

  it('counts active and resolved threads and shows replies on the row', () => {
    const html = renderToStaticMarkup(<SidebarComments threads={threads} actions={client} />)
    expect(html).toContain('Active (1)')
    expect(html).toContain('Resolved (1)')
    expect(html).toContain('1 reply')
    expect(html).not.toContain('Body b')
  })

  it('expands the selected thread with its details', () => {
    const html = renderToStaticMarkup(<SidebarComments threads={threads} actions={client} selectedId="a" />)
    expect(html).toContain('aria-expanded="true"')
    expect(html).toContain('class="comment-thread"')
    expect(html).toContain('Body r')
  })

  it('offers a general composer only when posting is allowed', () => {
    expect(renderToStaticMarkup(<SidebarComments threads={threads} actions={{ ...client, onAddGeneral: noop }} />)).toContain('aria-label="New comment"')
    expect(renderToStaticMarkup(<SidebarComments threads={threads} />)).not.toContain('aria-label="New comment"')
  })
})

describe('ScenePlan2D sticky notes', () => {
  const scene = loadLiveScene(FIDELITY_PLAN, undefined, { projectId: 'p' })
  const render = (annotations: PlanAnnotation[], selectedAnnotationId: string | null = null) => renderToStaticMarkup(
    <ScenePlan2D scene={scene} tool="select" snapEnabled={false} grid={0.3} editingEnabled={false}
      selected={null} onSelect={noop} zoom={1} pan={{ x: 0, y: 0 }}
      annotations={annotations} selectedAnnotationId={selectedAnnotationId} onSelectAnnotation={noop} commentActions={client} />,
  )

  it('draws a sticky-note marker for each unresolved pinned comment only', () => {
    const html = render(buildThreads([
      comment('open', { x: 2, y: 3 }),
      comment('done', { x: 4, y: 3, resolved: true }),
      comment('general'),
      comment('reply', { parent_id: 'open', x: 1, y: 1 }),
    ]))
    expect(html.match(/class="plan-sticky/g)?.length).toBe(1)
    expect(html).toContain('data-comment-id="open"')
    expect(html).not.toMatch(/plan-sticky[^>]*data-comment-id="done"/)
    expect(html).not.toContain('<circle r="5"')
  })

  it('moves markers with zoom and pan', () => {
    const at = (zoom: number, pan: { x: number; y: number }) => {
      const html = renderToStaticMarkup(
        <ScenePlan2D scene={scene} tool="select" snapEnabled={false} grid={0.3} editingEnabled={false}
          selected={null} onSelect={noop} zoom={zoom} pan={pan} annotations={buildThreads([comment('n', { x: 2, y: 3 })])} />,
      )
      const m = html.match(/class="plan-sticky[^"]*" style="left:([\d.-]+)px;top:([\d.-]+)px"/)
      return m ? { left: Number(m[1]), top: Number(m[2]) } : null
    }
    const a = at(1, { x: 0, y: 0 })!
    const b = at(2, { x: 0, y: 0 })!
    const c = at(1, { x: 40, y: 25 })!
    expect(b.left).not.toBeCloseTo(a.left, 3)
    expect(c.left - a.left).toBeCloseTo(40, 3)
    expect(c.top - a.top).toBeCloseTo(25, 3)
  })

  it('opens a popup with an X close button for the selected note', () => {
    const html = render(buildThreads([comment('open', { x: 2, y: 3 })]), 'open')
    expect(html).toContain('class="plan-note-card plan-note-popup')
    expect(html).toContain('aria-label="Close comment"')
    expect(html).toContain('Body open')
    expect(html).not.toMatch(/>Delete</)
  })

  it('does not open a popup for a resolved note', () => {
    const html = render(buildThreads([comment('done', { x: 2, y: 3, resolved: true })]), 'done')
    expect(html).not.toContain('plan-note-popup')
  })
})
