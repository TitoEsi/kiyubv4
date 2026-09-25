import { useCallback, useEffect, useRef, useState, type KeyboardEvent, type PointerEvent } from 'react'
import { CaretLeft, CaretRight } from '@phosphor-icons/react'
import FloorPlanPreview from './FloorPlanPreview'
import { LANDING_CONCEPTS, type LandingConcept } from '../data/landingConcepts'

function prefersReducedMotion() {
  return typeof window !== 'undefined' && window.matchMedia('(prefers-reduced-motion: reduce)').matches
}

export default function ConceptCarousel() {
  const count = LANDING_CONCEPTS.length
  const [index, setIndex] = useState(1)
  const [animate, setAnimate] = useState(true)
  const trackRef = useRef<HTMLDivElement>(null)
  const drag = useRef<{ x: number; start: number; dragging: boolean }>({ x: 0, start: 0, dragging: false })
  const slides: LandingConcept[] = [LANDING_CONCEPTS[count - 1], ...LANDING_CONCEPTS, LANDING_CONCEPTS[0]]

  const go = useCallback((next: number) => {
    if (prefersReducedMotion()) {
      let wrapped = next
      if (next <= 0) wrapped = count
      else if (next >= count + 1) wrapped = 1
      setAnimate(false)
      setIndex(wrapped)
      return
    }
    setAnimate(true)
    setIndex(next)
  }, [count])

  function onTransitionEnd() {
    if (index === 0) {
      setAnimate(false)
      setIndex(count)
    } else if (index === count + 1) {
      setAnimate(false)
      setIndex(1)
    }
  }

  useEffect(() => {
    if (!animate) {
      const id = requestAnimationFrame(() => setAnimate(!prefersReducedMotion()))
      return () => cancelAnimationFrame(id)
    }
  }, [animate])

  function pointerDown(e: PointerEvent<HTMLDivElement>) {
    drag.current = { x: e.clientX, start: index, dragging: true }
    ;(e.currentTarget as HTMLElement).setPointerCapture(e.pointerId)
  }

  function pointerMove(e: PointerEvent<HTMLDivElement>) {
    if (!drag.current.dragging || !trackRef.current) return
    const dx = e.clientX - drag.current.x
    const width = trackRef.current.clientWidth || 1
    if (Math.abs(dx) > width * 0.18) {
      const dir = dx < 0 ? 1 : -1
      drag.current.dragging = false
      go(index + dir)
    }
  }

  function pointerUp() {
    drag.current.dragging = false
  }

  function onKeyDown(e: KeyboardEvent<HTMLDivElement>) {
    if (e.key === 'ArrowRight') go(index + 1)
    if (e.key === 'ArrowLeft') go(index - 1)
  }

  const logical = ((index - 1) % count + count) % count

  return (
    <div
      className="concept-carousel"
      tabIndex={0}
      onKeyDown={onKeyDown}
      aria-roledescription="carousel"
      aria-label="Example architectural concepts"
    >
      <div
        className="concept-viewport"
        onPointerDown={pointerDown}
        onPointerMove={pointerMove}
        onPointerUp={pointerUp}
        onPointerCancel={pointerUp}
      >
        <div
          ref={trackRef}
          className={`concept-track${animate ? ' is-animated' : ''}`}
          style={{ transform: `translateX(calc(var(--peek) - ${index} * var(--slide)))` }}
          onTransitionEnd={onTransitionEnd}
        >
          {slides.map((concept, i) => (
            <article
              className={`concept-slide${i === index ? ' is-active' : ''}`}
              key={`${concept.id}-${i}`}
              aria-hidden={i !== index}
            >
              <p className="studio-meta">Concept {String(((i + count - 1) % count) + 1).padStart(2, '0')}</p>
              <div className="concept-pair">
                <figure className="concept-plate">
                  {concept.floorPlanImage ? (
                    <img src={concept.floorPlanImage} alt={`2D floor-plan example for ${concept.title}`} />
                  ) : (
                    <FloorPlanPreview plan={concept.plan} width={420} height={240} />
                  )}
                  <figcaption>2D floor plan</figcaption>
                </figure>
                <figure className="concept-plate">
                  <img src={concept.renderImage} alt={`3D architectural example for ${concept.title}`} />
                  <figcaption>3D visualization</figcaption>
                </figure>
              </div>
              <h3>{concept.title}</h3>
              <p>{concept.description}</p>
            </article>
          ))}
        </div>
      </div>
      <div className="concept-controls">
        <button type="button" className="concept-nav" aria-label="Previous concept" onClick={() => go(index - 1)}>
          <CaretLeft size={16} />
        </button>
        <ol className="concept-dots">
          {LANDING_CONCEPTS.map((c, i) => (
            <li key={c.id}>
              <button
                type="button"
                className={i === logical ? 'is-active' : ''}
                aria-label={`Show ${c.title}`}
                aria-current={i === logical ? 'true' : undefined}
                onClick={() => go(i + 1)}
              />
            </li>
          ))}
        </ol>
        <button type="button" className="concept-nav" aria-label="Next concept" onClick={() => go(index + 1)}>
          <CaretRight size={16} />
        </button>
      </div>
    </div>
  )
}
