/**
 * Small line icons (24×24, currentColor). Decorative only: every icon sits next
 * to a text label, so they are hidden from assistive technology.
 */
import type { ReactNode } from 'react'

function Icon({ children, size = 24, className }: { children: ReactNode; size?: number; className?: string }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.8}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      className={`icon ${className ?? ''}`}
    >
      {children}
    </svg>
  )
}

type P = { size?: number; className?: string }

/** Circle with a check mark: nothing to do. */
export const IconCheckCircle = (p: P) => (
  <Icon {...p}>
    <circle cx="12" cy="12" r="9" />
    <path d="m8 12.5 2.7 2.7L16 9.8" />
  </Icon>
)

/** Clock: something to do later (after the activity). */
export const IconClock = (p: P) => (
  <Icon {...p}>
    <circle cx="12" cy="12" r="9" />
    <path d="M12 7v5l3.5 2" />
  </Icon>
)

/** Speech bubble: a message or a planned contact. */
export const IconMessage = (p: P) => (
  <Icon {...p}>
    <path d="M5 5h14a1 1 0 0 1 1 1v9a1 1 0 0 1-1 1h-8l-4.5 3.5V16H5a1 1 0 0 1-1-1V6a1 1 0 0 1 1-1Z" />
  </Icon>
)

/** Broken link: no ground link. */
export const IconLinkOff = (p: P) => (
  <Icon {...p}>
    <path d="M9.5 14.5 8 16a3 3 0 0 1-4.2-4.2L6 9.5" />
    <path d="M14.5 9.5 16 8a3 3 0 0 1 4.2 4.2L18 14.5" />
    <path d="M4 4l16 16" />
  </Icon>
)

/** Chest strap sensor. */
export const IconChestStrap = (p: P) => (
  <Icon {...p}>
    <path d="M3 10c3 1.6 6 2.4 9 2.4s6-.8 9-2.4" />
    <path d="M3 14c3 1.6 6 2.4 9 2.4s6-.8 9-2.4" />
    <rect x="9" y="10.5" width="6" height="7.5" rx="1.5" />
  </Icon>
)

/** Finger-clip sensor (pulse oximeter). */
export const IconFingerClip = (p: P) => (
  <Icon {...p}>
    <path d="M10 21v-9.5a2 2 0 0 1 4 0V21" />
    <rect x="7" y="4" width="10" height="8" rx="2" />
    <path d="M10 8h4" />
  </Icon>
)

/** Generic sensor (fallback). */
export const IconSensor = (p: P) => (
  <Icon {...p}>
    <rect x="5" y="5" width="14" height="14" rx="3" />
    <path d="M8 12h2l1.5-3 2 6 1.5-3h1" />
  </Icon>
)

/** Flag: items to review. */
export const IconFlag = (p: P) => (
  <Icon {...p}>
    <path d="M5 21V4" />
    <path d="M5 4h11l-2 4 2 4H5" />
  </Icon>
)

/** Line leaving a band: value outside the personal historical range. */
export const IconTrendBand = (p: P) => (
  <Icon {...p}>
    <path d="M3 15h18" strokeDasharray="2 3" />
    <path d="M3 19h18" strokeDasharray="2 3" />
    <path d="M3 17l5-1 4-8 3 3 6-6" />
  </Icon>
)

/** Wave with a gap: signal quality to check. */
export const IconSignalQuality = (p: P) => (
  <Icon {...p}>
    <path d="M2 12h3l2-5 3 10 1.5-5" />
    <path d="M15 12h0.5" />
    <path d="M18.5 12H22" />
  </Icon>
)

/** Antenna with a slash: data not updated. */
export const IconNoData = (p: P) => (
  <Icon {...p}>
    <path d="M12 20v-7" />
    <circle cx="12" cy="11" r="1.5" />
    <path d="M8.5 7.5a5 5 0 0 0 0 7" />
    <path d="M15.5 7.5a5 5 0 0 1 0 7" />
    <path d="M4 4l16 16" />
  </Icon>
)

/** Information mark. */
export const IconInfo = (p: P) => (
  <Icon {...p}>
    <circle cx="12" cy="12" r="9" />
    <path d="M12 11v5" />
    <path d="M12 8h.01" />
  </Icon>
)

/** Satellite dish: ground link. */
export const IconLink = (p: P) => (
  <Icon {...p}>
    <path d="M5 13a7 7 0 0 0 7 7" />
    <path d="M4 20 9.5 14.5" />
    <path d="M5 13 12 20l3-3-7-7-3 3Z" />
    <path d="M15 4a5 5 0 0 1 5 5" />
    <path d="M15 8a1 1 0 0 1 1 1" />
  </Icon>
)

/** Chevron right. */
export const IconChevron = (p: P) => (
  <Icon {...p}>
    <path d="m9 6 6 6-6 6" />
  </Icon>
)

/** Brand mark: a pulse line on an orbit. */
export const BrandMark = ({ size = 28 }: { size?: number }) => (
  <svg width={size} height={size} viewBox="0 0 32 32" aria-hidden="true" className="brand-mark">
    <rect width="32" height="32" rx="7" fill="var(--tint)" />
    <ellipse cx="16" cy="16" rx="12" ry="5.5" fill="none" stroke="#fff" strokeOpacity="0.35" strokeWidth="1.5" transform="rotate(-20 16 16)" />
    <path d="M5 17h6l3-7 4 13 3-6h6" fill="none" stroke="#fff" strokeWidth="2.4" strokeLinejoin="round" strokeLinecap="round" />
  </svg>
)
