import { useState } from 'react'
import { DAILY_INDICATORS } from '../domain/parameters'
import { parseMeasurementsCsv, parseProfileJson, BASELINE_NOTE, type CrewProfileInput, type MeasurementsImport } from '../data/import/crewImport'
import { CREW_PROFILES } from '../data/mock/generator'
import { removeImport, storedImports, storeImport } from '../state/crewLocal'
import { useAppState } from '../state/AppState'
import { useToast } from './Toast'
import { Sheet } from './ui'
import sampleProfile from '../data/import/samples/crew-profile.sample.json?raw'
import sampleCsv from '../data/import/samples/measurements.sample.csv?raw'

interface Picked {
  name: string
  text: string
}

const download = (name: string, text: string, type: string) => `data:${type};charset=utf-8,${encodeURIComponent(text)}` + `#${name}`

/**
 * Loads a crew member's general profile (JSON) and day-to-day measurements
 * (CSV) — the formats the team's data arrive in. Everything is parsed in the
 * browser and kept only in this browser; nothing is uploaded.
 */
export function ImportSheet({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { notifyChanged } = useAppState()
  const toast = useToast()
  const [profileFile, setProfileFile] = useState<Picked | null>(null)
  const [csvFile, setCsvFile] = useState<Picked | null>(null)
  const [target, setTarget] = useState(CREW_PROFILES[0].id)
  const [, setTick] = useState(0)

  let profile: CrewProfileInput | null = null
  let profileError: string | null = null
  if (profileFile) {
    try {
      profile = parseProfileJson(profileFile.text)
    } catch (e) {
      profileError = e instanceof Error ? e.message : String(e)
    }
  }
  const crewId = profile?.crewId && CREW_PROFILES.some((p) => p.id === profile!.crewId) ? profile.crewId : target
  let result: MeasurementsImport | null = null
  let csvError: string | null = null
  if (csvFile) {
    try {
      result = parseMeasurementsCsv(csvFile.text, crewId, profile?.missionStartDate, csvFile.name)
    } catch (e) {
      csvError = e instanceof Error ? e.message : String(e)
    }
  }
  const existing = storedImports()
  const ready = !!result && !profileError

  const pick = async (file: File | undefined, set: (p: Picked | null) => void) => {
    if (!file) return set(null)
    set({ name: file.name, text: await file.text() })
  }
  const reset = () => {
    setProfileFile(null)
    setCsvFile(null)
  }
  const close = () => {
    reset()
    onClose()
  }
  const apply = () => {
    if (!result) return
    storeImport({
      crewId,
      displayName: profile?.displayName ?? null,
      role: profile?.role ?? null,
      series: result.series,
      files: [profileFile?.name, csvFile?.name].filter(Boolean) as string[],
      importedAt: new Date().toISOString(),
    })
    notifyChanged()
    toast(`Imported ${result.series.length} indicators for ${profile?.displayName ?? crewId}`)
    close()
  }
  const noBaseline = result?.series.filter((s) => !s.baseline).map((s) => DAILY_INDICATORS[s.indicator].label) ?? []

  return (
    <Sheet
      open={open}
      title="Import crew data"
      onClose={close}
      wide
      footer={
        <div className="button-row">
          <button type="button" className="btn btn-primary" disabled={!ready} onClick={apply}>
            Import
          </button>
          <button type="button" className="btn" onClick={close}>
            Cancel
          </button>
        </div>
      }
    >
      <div className="stack import-sheet">
        <p className="body-text muted">
          General profile as <strong>JSON</strong>, measurements as <strong>CSV</strong> (one row per day, or one row per reading). Files are read in this
          browser only: nothing is uploaded.
        </p>
        <div className="import-grid">
          <label className="field import-drop">
            <span className="field-label">1 · Profile (JSON)</span>
            <input type="file" accept=".json,application/json" onChange={(e) => void pick(e.target.files?.[0], setProfileFile)} />
            {profile && (
              <span className="import-ok">
                ✓ {profileFile?.name} · {profile.displayName ?? 'No name'}
                {profile.role ? ` · ${profile.role}` : ''} · mission start {profile.missionStartDate}
              </span>
            )}
            {profileError && <span className="form-error">{profileError}</span>}
          </label>
          <label className="field import-drop">
            <span className="field-label">2 · Measurements (CSV)</span>
            <input type="file" accept=".csv,text/csv" onChange={(e) => void pick(e.target.files?.[0], setCsvFile)} />
            {result && (
              <span className="import-ok">
                ✓ {csvFile?.name} · {result.rowsUsed} readings from {result.rowsRead} rows · {result.firstDate} → {result.lastDate}
              </span>
            )}
            {csvError && <span className="form-error">{csvError}</span>}
          </label>
        </div>
        <div className="import-row">
          <label className="field import-target">
            <span className="field-label">Crew member</span>
            <select value={crewId} disabled={!!profile?.crewId && crewId === profile.crewId} onChange={(e) => setTarget(e.target.value)}>
              {CREW_PROFILES.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.id}
                  {existing[p.id] ? ' (has imported data)' : ''}
                </option>
              ))}
            </select>
          </label>
          <p className="fineprint import-samples">
            No files yet?{' '}
            <button
              type="button"
              className="text-button"
              onClick={() => {
                setProfileFile({ name: 'crew-profile.sample.json', text: sampleProfile })
                setCsvFile({ name: 'measurements.sample.csv', text: sampleCsv })
              }}
            >
              Use the sample files
            </button>{' '}
            · download{' '}
            <a className="text-button" download="crew-profile.sample.json" href={download('crew-profile.sample.json', sampleProfile, 'application/json')}>
              JSON
            </a>{' '}
            <a className="text-button" download="measurements.sample.csv" href={download('measurements.sample.csv', sampleCsv, 'text/csv')}>
              CSV
            </a>
          </p>
        </div>
        {result && (
          <section className="import-preview" aria-label="Preview">
            <p className="eyebrow">
              Preview · {result.layout === 'wide' ? 'one row per day' : 'one row per reading'}
            </p>
            <p className="body-text">
              {result.series.map((s) => DAILY_INDICATORS[s.indicator].label).join(' · ')}
            </p>
            {noBaseline.length > 0 && (
              <p className="fineprint">
                No personal baseline yet for {noBaseline.join(', ')}. {BASELINE_NOTE}
              </p>
            )}
            {result.issues.length > 0 && (
              <details className="import-issues">
                <summary>
                  {result.issues.length} {result.issues.length === 1 ? 'row was' : 'rows were'} skipped
                </summary>
                <ul>
                  {result.issues.slice(0, 8).map((i) => (
                    <li key={`${i.line}-${i.message}`}>
                      Line {i.line}: {i.message}
                    </li>
                  ))}
                  {result.issues.length > 8 && <li>…and {result.issues.length - 8} more</li>}
                </ul>
              </details>
            )}
          </section>
        )}
        {Object.keys(existing).length > 0 && (
          <p className="fineprint">
            Imported data in use for {Object.keys(existing).join(', ')}.{' '}
            <button
              type="button"
              className="text-button"
              onClick={() => {
                for (const id of Object.keys(existing)) removeImport(id)
                notifyChanged()
                setTick((t) => t + 1)
                toast('Back to the simulated data')
              }}
            >
              Remove and go back to simulated data
            </button>
          </p>
        )}
        <p className="fineprint">Proposed format, to be confirmed with the team: see docs/FRONTEND_DATA_CONTRACT.md and docs/samples/.</p>
      </div>
    </Sheet>
  )
}
