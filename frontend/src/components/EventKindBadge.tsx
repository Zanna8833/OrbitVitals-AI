import type { EventKind } from '../domain/types'
import { IconMessage, IconNoData, IconSignalQuality, IconTrendBand } from './Icons'

const KIND_ICON: Record<EventKind, typeof IconTrendBand> = {
  outside_personal_range: IconTrendBand,
  signal_quality: IconSignalQuality,
  data_stale: IconNoData,
  crew_report: IconMessage,
}

/**
 * The event type's own colour (see --kind-* tokens) and icon. Always placed
 * next to the type's text label, so the colour is never the only cue.
 */
export function EventKindBadge({ kind, size = 22 }: { kind: EventKind; size?: number }) {
  const Icon = KIND_ICON[kind]
  return (
    <span className={`kind-badge kind-${kind}`} aria-hidden="true">
      <Icon size={size} />
    </span>
  )
}
