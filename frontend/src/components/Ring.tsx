/**
 * Progress ring that fills towards a daily target. The number in the middle
 * and the caption below carry the meaning; the colour only supports them.
 */
export function Ring({
  fill,
  size = 64,
  stroke = 7,
  tone,
  over = false,
  children,
  label,
}: {
  /** 0–1 */
  fill: number
  size?: number
  stroke?: number
  tone: 'water' | 'energy' | 'micro' | 'protein'
  /** Above an upper limit: drawn with the attention colour and a notch. */
  over?: boolean
  children?: React.ReactNode
  label: string
}) {
  const r = (size - stroke) / 2
  const c = 2 * Math.PI * r
  const f = Math.max(0, Math.min(1, fill))
  return (
    <span className={`ring ring-${tone}${over ? ' is-over' : ''}${f >= 1 ? ' is-full' : ''}`} style={{ width: size, height: size }} role="img" aria-label={label}>
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} aria-hidden="true">
        <circle className="ring-track" cx={size / 2} cy={size / 2} r={r} strokeWidth={stroke} fill="none" />
        <circle
          className="ring-fill"
          cx={size / 2}
          cy={size / 2}
          r={r}
          strokeWidth={stroke}
          fill="none"
          strokeLinecap="round"
          strokeDasharray={`${c * f} ${c}`}
          transform={`rotate(-90 ${size / 2} ${size / 2})`}
        />
      </svg>
      {children && <span className="ring-center">{children}</span>}
    </span>
  )
}
