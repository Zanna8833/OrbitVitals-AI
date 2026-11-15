import type { BackendEvaluation } from '../../domain/metricCatalog'
import { formatDate } from '../../domain/time'

const DOMAIN: Record<string, string> = {
  vital_signs: 'Vital signs',
  sleep: 'Sleep',
  physical_activity: 'Physical activity',
  nutrition: 'Nutrition',
  cognition: 'Cognition',
}
const STATUS: Record<string, string> = { nominal: 'Nominal', attention: 'Attention', alert: 'Alert', insufficient_data: 'Insufficient data' }

/**
 * Results of the backend's scientific engines, shown as they are: status,
 * summary, each finding's explanation, data quality and algorithm. "Attention"
 * is a review signal, never a diagnosis (docs/frontend-integration.md).
 */
export function EvaluationsList({ items, compact = false, openFirst = false }: { items: BackendEvaluation[]; compact?: boolean; openFirst?: boolean }) {
  if (!items.length) return <p className="list-empty">No evaluation stored on the backend for this crew member.</p>
  const sorted = [...items].sort((a, b) => (a.window_end < b.window_end ? 1 : -1))
  return (
    <ul className={`eval-list${compact ? ' is-compact' : ''}`}>
      {sorted.map((e) => (
        <li key={e.evaluation_id} className={`eval is-${e.status}`}>
          <details open={openFirst && sorted.length === 1 ? true : undefined}>
            <summary>
              <span className={`eval-status is-${e.status}`}>{STATUS[e.status] ?? e.status}</span>
              <span className="eval-title">
                {DOMAIN[e.domain] ?? e.domain}
                <small>
                  {formatDate(e.window_start)} → {formatDate(e.window_end)}
                </small>
              </span>
            </summary>
            <div className="eval-body">
              <p>{e.summary.replace(/^SIMULATED DATA: this evaluation includes synthetic measurements\.\s*/, '')}</p>
              {e.findings.map((f, i) => (
                <div key={`${f.metric}-${i}`} className="eval-finding">
                  <p className="eval-finding-head">
                    <strong>{f.metric.replace(/_/g, ' ')}</strong> · {STATUS[f.status] ?? f.status}
                    {f.observed_value != null && (
                      <>
                        {' '}
                        · observed {round(f.observed_value)} {f.unit}
                        {f.baseline_value != null ? ` vs ${round(f.baseline_value)} ${f.unit}` : ''}
                      </>
                    )}
                  </p>
                  <p className="eval-explain">{f.explanation.replace(/^SIMULATED DATA: this evaluation includes synthetic measurements\.\s*/, '')}</p>
                </div>
              ))}
              <p className="fineprint">
                Data quality: {e.data_quality?.status ?? 'not reported'}
                {e.data_quality?.completeness != null ? ` · completeness ${Math.round(e.data_quality.completeness * 100)}%` : ''}
                {e.algorithm ? ` · ${e.algorithm.name} ${e.algorithm.version}` : ''} · {e.summary.startsWith('SIMULATED') ? 'includes simulated measurements' : 'source as stored'}
              </p>
            </div>
          </details>
        </li>
      ))}
    </ul>
  )
}

const round = (v: number) => (Math.abs(v) >= 100 ? Math.round(v) : Math.round(v * 10) / 10)
