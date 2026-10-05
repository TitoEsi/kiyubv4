const INK = '#17191c'

/** North glyph. Plan north is smaller plan y, which the 2D plan draws upward. */
export function NorthMark() {
  return (
    <g data-north="true">
      <path d="M11 1 L15 9 L7 9 Z" fill={INK} />
      <line x1={11} y1={9} x2={11} y2={20} stroke={INK} strokeWidth={1.25} />
      <text
        x={11}
        y={32}
        textAnchor="middle"
        fontSize={11}
        fontWeight={600}
        letterSpacing="0.04em"
        fill={INK}
        fontFamily="Helvetica"
      >
        N
      </text>
    </g>
  )
}

/** Fixed screen-up North marker for the 2D plan. */
export default function NorthIndicator() {
  return (
    <div className="north-indicator" role="img" aria-label="North" title="North">
      <svg width={22} height={34} viewBox="0 0 22 34" aria-hidden="true" focusable="false">
        <NorthMark />
      </svg>
    </div>
  )
}
