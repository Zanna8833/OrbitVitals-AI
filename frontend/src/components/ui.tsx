import { useEffect, useId, useRef, type ReactNode } from 'react'

/**
 * Small set of interface primitives shared by every view.
 * Visual language: grouped lists, sheets and segmented controls — calm,
 * native-feeling, no decoration that does not carry information.
 */

/* ------------------------------------------------------------------ */
/* Sheet: a focused task on top of the page (not a new screen).        */
/* Built on <dialog>: focus trap, Esc and inert background are native. */
/* ------------------------------------------------------------------ */

export function Sheet({
  open,
  title,
  onClose,
  children,
  footer,
  wide = false,
}: {
  open: boolean
  title: string
  onClose: () => void
  children: ReactNode
  footer?: ReactNode
  wide?: boolean
}) {
  const ref = useRef<HTMLDialogElement>(null)
  const titleId = useId()

  useEffect(() => {
    const d = ref.current
    if (!d) return
    if (open && !d.open) {
      d.showModal()
      document.documentElement.classList.add('has-sheet')
    }
    if (!open && d.open) d.close()
    return () => document.documentElement.classList.remove('has-sheet')
  }, [open])

  return (
    <dialog
      ref={ref}
      className={`sheet${wide ? ' sheet-wide' : ''}`}
      aria-labelledby={titleId}
      onClose={onClose}
      onCancel={(e) => {
        e.preventDefault()
        onClose()
      }}
      onClick={(e) => {
        // Click on the backdrop (the dialog element itself) closes the sheet.
        if (e.target === e.currentTarget) onClose()
      }}
    >
      {open && (
        <div className="sheet-inner">
          <header className="sheet-head">
            <h2 id={titleId}>{title}</h2>
            <button type="button" className="sheet-close" onClick={onClose} aria-label="Close">
              <svg width="12" height="12" viewBox="0 0 12 12" aria-hidden="true">
                <path d="M2 2l8 8M10 2l-8 8" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
              </svg>
            </button>
          </header>
          <div className="sheet-body">{children}</div>
          {footer && <footer className="sheet-foot">{footer}</footer>}
        </div>
      )}
    </dialog>
  )
}

/* ------------------------------------------------------------------ */

export function Segmented<T extends string>({
  value,
  options,
  onChange,
  label,
  size = 'regular',
}: {
  value: T
  options: { value: T; label: string }[]
  onChange: (v: T) => void
  label: string
  size?: 'regular' | 'small'
}) {
  return (
    <div className={`segmented segmented-${size}`} role="radiogroup" aria-label={label}>
      {options.map((o) => (
        <button
          key={o.value}
          type="button"
          role="radio"
          aria-checked={value === o.value}
          className={value === o.value ? 'is-selected' : undefined}
          onClick={() => onChange(o.value)}
        >
          {o.label}
        </button>
      ))}
    </div>
  )
}

/* ------------------------------------------------------------------ */

/** One row of an inset grouped list. Renders a link, a button or static content. */
export function Row({
  leading,
  title,
  subtitle,
  trailing,
  href,
  onClick,
  selected,
  newTab = false,
  chevron = !!(href || onClick),
}: {
  leading?: ReactNode
  title: ReactNode
  subtitle?: ReactNode
  trailing?: ReactNode
  href?: string
  onClick?: () => void
  selected?: boolean
  /** Opens in a new tab (a separate app, e.g. the cognition battery). */
  newTab?: boolean
  chevron?: boolean
}) {
  const body = (
    <>
      {leading && <span className="row-leading">{leading}</span>}
      <span className="row-text">
        <span className="row-title">{title}</span>
        {subtitle && <span className="row-subtitle">{subtitle}</span>}
      </span>
      {trailing && <span className="row-trailing">{trailing}</span>}
      {chevron && (
        <svg className="row-chevron" width="8" height="13" viewBox="0 0 8 13" aria-hidden="true">
          <path d="M1.5 1.5 6.5 6.5l-5 5" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      )}
    </>
  )
  const cls = `row${selected ? ' is-selected' : ''}`
  if (href) {
    return (
      <a className={cls} href={href} aria-current={selected ? 'page' : undefined} {...(newTab ? { target: '_blank', rel: 'noopener' } : {})}>
        {body}
      </a>
    )
  }
  if (onClick) {
    return (
      <button type="button" className={cls} onClick={onClick}>
        {body}
      </button>
    )
  }
  return <div className={cls}>{body}</div>
}

export function List({ children, label }: { children: ReactNode; label?: string }) {
  return (
    <div className="list" role="list" aria-label={label}>
      {Array.isArray(children)
        ? children.filter(Boolean).map((c, i) => (
            <div role="listitem" key={i}>
              {c}
            </div>
          ))
        : <div role="listitem">{children}</div>}
    </div>
  )
}

/** Small round symbol in a category colour, used as a row's leading element. */
export function Symbol({ tone, children }: { tone: Tone; children: ReactNode }) {
  return (
    <span className={`symbol tone-${tone}`} aria-hidden="true">
      {children}
    </span>
  )
}

export type Tone = 'heart' | 'respiration' | 'rest' | 'activity' | 'body' | 'blue' | 'gray' | 'orange'

export function Pill({ children, tone = 'gray' }: { children: ReactNode; tone?: Tone }) {
  return <span className={`pill tone-${tone}`}>{children}</span>
}

export function SectionTitle({ children, action, id }: { children: ReactNode; action?: ReactNode; id?: string }) {
  return (
    <div className="section-title">
      <h2 id={id}>{children}</h2>
      {action}
    </div>
  )
}

/**
 * Marks anything that is simulated in this prototype (data, ground link,
 * deliveries to the medical team). Shape + word, never colour alone.
 */
export function SimTag({ children = 'Simulated', title }: { children?: ReactNode; title?: string }) {
  return (
    <span className="sim-tag" title={title ?? 'Simulated in this prototype: nothing leaves this browser'}>
      {children}
    </span>
  )
}
