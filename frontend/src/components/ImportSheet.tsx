import { useState } from 'react'
import { DAILY_INDICATORS } from '../domain/parameters'
import { parseMeasurementsCsv, parseProfileJson, BASELINE_NOTE, type CrewProfileInput, type MeasurementsImport } from '../data/import/crewImport'
import { removeImport, storedImports } from '../state/crewLocal'
import { useCallback } from 'react'
import type { DataSource } from '../data'
import { useQuery } from '../hooks/useQuery'
import { useMutation } from '../hooks/useMutation'
import { config } from '../config'
import { FormError } from './Common'
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
 * Loads an astronaut's general profile (JSON) and day-to-day measurements
 * (CSV) — the formats the team's data arrive in. Parsed in the browser,
 * previewed, then sent to the OrbitVitals server.
 */
export function ImportSheet({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { notifyChanged } = useAppState()
  const toast = useToast()
  const crewQuery = useQuery(useCallback((ds: DataSource) => ds.listCrew(), []))
  const crew = crewQuery.data ?? []
  const [profileFile, setProfileFile] = useState<Picked | null>(null)
  const [csvFile, setCsvFile] = useState<Picked | null>(null)
  const [targetChoice, setTarget] = useState<string | null>(null)
  const [, setTick] = useState(0)
  const target = targetChoice ?? crew[0]?.id ?? ''

  let profile: CrewProfileInput | null = null
  let profileError: string | null = null
  if (profileFile) {
    try {
      profile = parseProfileJson(profileFile.text)
    } catch (e) {
      profileError = e instanceof Error ? e.message : String(e)
    }
  }
  const crewId = profile?.crewId && crew.some((p) => p.id === profile!.crewId) ? profile.crewId : target
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
  const importing = useMutation((ds: DataSource, id: string) =>
    Promise.all([
      ds.importDaily(id, result!.series, { displayName: profile?.displayName ?? null, files: [profileFile?.name, csvFile?.name].filter(Boolean) as string[] }),
      profile?.sex && profile.ageYears && profile.heightM ? ds.saveNutritionProfile(id, { sex: profile.sex, ageYears: profile.ageYears, heightM: profile.heightM, menstruating: false }) : Promise.resolve(),
    ]),
  )
  const apply = async () => {
    if (!result) return
    if (!(await importing.run(crewId))) return
    notifyChanged()
    toast(`Imported ${result.series.length} indicators for ${crew.find((c) => c.id === crewId)?.displayName ?? crewId}`)
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
          <button type="button" className="btn btn-primary" disabled={!ready || importing.busy} onClick={() => void apply()}>
            Import
          </button>
          <button type="button" className="btn" onClick={close}>
            Cancel
          </button>
        </div>
      }
    >
      <div className="stack import-sheet">
        <FormError message={importing.error} />
        <p className="body-text muted">
          General profile as <strong>JSON</strong>, measurements as <strong>CSV</strong> (one row per day, or one row per reading). Check the preview, then
          import: the readings are added to the astronaut's record.
        </p>
        <div className="import-grid">
          <label className="field import-drop">
            <span className="field-label">1 · Profile (JSON)</span>
            <input type="file" accept=".json,application/json" onChange={(e) => void pick(e.target.files?.[0], setProfileFile)} />
            {profile && (
              <span className="import-ok">
                ✓ {profileFile?.name} · {profile.displayName ?? 'No name'}
                {profile.role ? ` · ${profile.role}` : ''} · mission start {profile.missionStartDate}
                {profile.sex && profile.ageYears && profile.heightM ? ` · ${profile.sex}, ${profile.ageYears} y, ${profile.heightM.toFixed(2)} m` : ''}
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
            <span className="field-label">Astronaut</span>
            <select value={crewId} disabled={!!profile?.crewId && crewId === profile.crewId} onChange={(e) => setTarget(e.target.value)}>
              {crew.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.displayName}
                </option>
              ))}
            </select>
          </label>
          <p className="fineprint import-samples">
            File format examples:{' '}
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
        {config.dataSource === 'mock' && Object.keys(existing).length > 0 && (
          <p className="fineprint">
            Imported data in use for {Object.keys(existing).join(', ')}.{' '}
            <button
              type="button"
              className="text-button"
              onClick={() => {
                for (const id of Object.keys(existing)) removeImport(id)
                notifyChanged()
                setTick((t) => t + 1)
                toast('Imported data removed')
              }}
            >
              Remove imported data
            </button>
          </p>
        )}
        <p className="fineprint">Accepted columns and formats: frontend/docs/FRONTEND_DATA_CONTRACT.md.</p>
      </div>
    </Sheet>
  )
}
