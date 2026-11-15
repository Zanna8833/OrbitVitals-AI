import type { MouseEvent } from 'react'

/** Pages visited in this tab, to make "Back" return where the user came from. */
const visited: string[] = typeof window !== 'undefined' ? [window.location.hash] : []
if (typeof window !== 'undefined') window.addEventListener('hashchange', () => visited.push(window.location.hash))

export function canGoBack(): boolean {
  return visited.length > 1
}

/**
 * "‹ Back": the previous page of the app when there is one (like the browser's
 * back button), otherwise `fallback`. Always a real link, so it also works
 * with a middle click or without JavaScript history.
 */
export function BackLink({ fallback, label = 'Back', className = 'back-link-inline' }: { fallback: string; label?: string; className?: string }) {
  const onClick = (e: MouseEvent<HTMLAnchorElement>) => {
    if (e.metaKey || e.ctrlKey || e.shiftKey || e.button !== 0) return
    if (canGoBack()) {
      e.preventDefault()
      window.history.back()
    }
  }
  return (
    <a className={className} href={fallback} onClick={onClick}>
      ‹ {label}
    </a>
  )
}
