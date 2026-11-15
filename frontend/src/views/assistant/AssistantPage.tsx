import { useCallback, useEffect, useRef, useState, type FormEvent } from 'react'
import type { DataSource } from '../../data'
import { config } from '../../config'
import { href } from '../../hooks/useRoute'
import { useQuery } from '../../hooks/useQuery'
import { lastAstronaut } from '../../state/lastAstronaut'
import { Segmented } from '../../components/ui'
import { BackLink } from '../../components/BackLink'
import { agentHealth, askAgent, type AgentDomain, type AgentHealth, type AgentResponse } from './agentClient'

type Topic = 'all' | AgentDomain

const TOPICS: { value: Topic; label: string }[] = [
  { value: 'all', label: 'Everything' },
  { value: 'vital_signs', label: 'Vital signs' },
  { value: 'sleep', label: 'Sleep' },
  { value: 'physical_activity', label: 'Activity' },
  { value: 'nutrition', label: 'Nutrition' },
]

const SUGGESTIONS: Record<Topic, string[]> = {
  all: ['What needs attention right now?', 'How reliable is the recent data?'],
  vital_signs: ['Why is a vital sign flagged?', 'How does it compare with the usual range?'],
  sleep: ['Why is sleep flagged, and how does it compare with the baseline?', 'Which nights are missing?'],
  physical_activity: ['Is exercise below the usual level?', 'Which days were rest days?'],
  nutrition: ['Which nutrients are below the requirement?', 'Why does intake matter in space?'],
}

interface Turn {
  id: number
  question: string
  who: string
  topic: Topic
  answer: AgentResponse | null
  error: string | null
}

/**
 * The assistant explains what OrbitVitals has stored and computed for one
 * astronaut, with NASA sources for context. Answers come from the team's
 * assistant service: rule-based when no language model is available, always
 * verified against the data, never a diagnosis.
 */
export function AssistantPage() {
  const crewQuery = useQuery(useCallback((ds: DataSource) => ds.listCrew(), []))
  const crew = crewQuery.data ?? []
  const [who, setWho] = useState<string | null>(null)
  const [topic, setTopic] = useState<Topic>('all')
  const [question, setQuestion] = useState('')
  const [turns, setTurns] = useState<Turn[]>([])
  const [busy, setBusy] = useState(false)
  const [health, setHealth] = useState<AgentHealth | null | 'down'>(null)
  const endRef = useRef<HTMLDivElement>(null)
  const selected = who ?? lastAstronaut()?.crewId ?? crew[0]?.id ?? null
  const backendId = config.backendCrew.find((c) => c.id === selected)?.backendId ?? null
  const name = crew.find((c) => c.id === selected)?.displayName ?? ''
  const available = config.dataSource === 'http'

  useEffect(() => {
    if (!available) return
    let alive = true
    agentHealth()
      .then((h) => alive && setHealth(h))
      .catch(() => alive && setHealth('down'))
    return () => {
      alive = false
    }
  }, [available])

  // Show the start of the newest exchange (the question and the answer's headline).
  useEffect(() => {
    endRef.current?.parentElement?.querySelector('.turn:last-of-type')?.scrollIntoView({ block: 'start', behavior: 'smooth' })
  }, [turns])

  const ask = async (q: string) => {
    if (!backendId || busy) return
    const id = Date.now()
    setTurns((t) => [...t, { id, question: q || 'Give me an overview.', who: name, topic, answer: null, error: null }])
    setQuestion('')
    setBusy(true)
    try {
      const answer = await askAgent(backendId, topic === 'all' ? null : topic, q)
      setTurns((t) => t.map((x) => (x.id === id ? { ...x, answer } : x)))
    } catch (e) {
      setTurns((t) => t.map((x) => (x.id === id ? { ...x, error: e instanceof Error ? e.message : 'The assistant could not answer.' } : x)))
    } finally {
      setBusy(false)
    }
  }
  const submit = (e: FormEvent) => {
    e.preventDefault()
    void ask(question)
  }

  return (
    <div className="today assistant-page">
      <header className="today-head">
        <div className="today-title">
          <BackLink fallback={href.crewHome()} />
          <h1>Assistant</h1>
          <p className="eyebrow">Explains the results stored in OrbitVitals · no diagnosis</p>
        </div>
      </header>
      <div className="assistant-grid">
        <section className="card assistant-chat" aria-label="Conversation">
          <div className="assistant-context">
            <label className="field assistant-who">
              <span className="field-label">About</span>
              <select value={selected ?? ''} onChange={(e) => setWho(e.target.value)}>
                {crew.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.displayName}
                  </option>
                ))}
              </select>
            </label>
            <div className="field">
              <span className="field-label">Topic</span>
              <Segmented size="small" label="Topic" value={topic} onChange={setTopic} options={TOPICS} />
            </div>
          </div>

          <div className="chat-scroll" aria-live="polite">
            {!turns.length && (
              <div className="chat-empty">
                <p className="chat-empty-title">Ask about {name || 'an astronaut'}</p>
                <p className="muted">
                  The answer uses only what OrbitVitals has stored: evaluations, personal baselines and measurements. Each statement says where it comes from.
                </p>
              </div>
            )}
            {turns.map((t) => (
              <div key={t.id} className="turn">
                <div className="chat-q">
                  <span>{t.question}</span>
                  <small>
                    {t.who} · {TOPICS.find((x) => x.value === t.topic)?.label}
                  </small>
                </div>
                {t.error ? (
                  <div className="answer answer-error" role="alert">
                    {t.error}
                  </div>
                ) : t.answer ? (
                  <Answer a={t.answer} />
                ) : (
                  <div className="answer answer-loading">Reading the data…</div>
                )}
              </div>
            ))}
            <div ref={endRef} />
          </div>

          <div className="chat-suggestions" aria-label="Example questions">
            {SUGGESTIONS[topic].map((s) => (
              <button key={s} type="button" className="chip" disabled={!backendId || busy || !available} onClick={() => void ask(s)}>
                {s}
              </button>
            ))}
          </div>
          <form className="chat-composer" onSubmit={submit}>
            <label className="sr-only" htmlFor="ask">
              Ask the assistant
            </label>
            <input
              id="ask"
              type="text"
              maxLength={500}
              value={question}
              placeholder={available ? `Ask about ${name || 'the astronaut'}…` : 'Available with the OrbitVitals server'}
              disabled={!available}
              onChange={(e) => setQuestion(e.target.value)}
            />
            <button type="submit" className="btn btn-primary" disabled={!available || busy || !backendId}>
              {busy ? 'Asking…' : 'Ask'}
            </button>
          </form>
        </section>

        <aside className="assistant-side">
          <section className="card">
            <p className="eyebrow">Service</p>
            <ul className="service-list">
              <li>
                <span className={`server-dot is-${health === null ? 'checking' : health === 'down' ? 'down' : 'ok'}`} aria-hidden="true" />
                {health === null ? 'Checking…' : health === 'down' ? 'Assistant service not reachable' : 'Assistant service connected'}
              </li>
              {health && health !== 'down' && (
                <>
                  <li>
                    <span className={`server-dot is-${health.backend.reachable ? 'ok' : 'down'}`} aria-hidden="true" />
                    {health.backend.reachable ? 'Reads the OrbitVitals server' : 'Cannot read the OrbitVitals server'}
                  </li>
                  <li>
                    <span className={`server-dot is-${health.primary_model.available ? 'ok' : 'checking'}`} aria-hidden="true" />
                    {health.primary_model.available ? `Language model ${health.primary_model.name}` : 'Language model off: answers use fixed, verified rules'}
                  </li>
                </>
              )}
            </ul>
          </section>
          <section className="card">
            <p className="eyebrow">What it does</p>
            <ul className="plain-list">
              <li>Explains flagged results against the astronaut’s own baseline.</li>
              <li>Says what the data cannot tell, and suggests checks for a person to do.</li>
              <li>Adds NASA context, with a link to each source.</li>
            </ul>
          </section>
          <section className="card">
            <p className="eyebrow">What it never does</p>
            <ul className="plain-list">
              <li>No diagnosis, no treatment, no medication advice.</li>
              <li>It never changes a result.</li>
            </ul>
          </section>
        </aside>
      </div>
    </div>
  )
}

function Answer({ a }: { a: AgentResponse }) {
  const cite = new Map(a.citations.map((c, i) => [c.evidence_id, i + 1]))
  const refs = (ids: string[]) =>
    ids
      .filter((id) => cite.has(id))
      .map((id) => (
        <a key={id} className="cite" href={`#cite-${id}`} onClick={(e) => { e.preventDefault(); document.getElementById(`cite-${id}`)?.scrollIntoView({ block: 'nearest' }) }}>
          [{cite.get(id)}]
        </a>
      ))
  return (
    <article className="answer">
      <p className="answer-headline">{a.headline}</p>
      {a.human_review.recommended && (
        <p className="answer-review">
          <strong>Worth a review by the medical team.</strong> {a.human_review.reasons.join(' ')}
        </p>
      )}
      {a.observations.length > 0 && (
        <section>
          <h3>What the data show</h3>
          <ul>
            {a.observations.map((s) => (
              <li key={s.id}>{s.text}</li>
            ))}
          </ul>
        </section>
      )}
      {a.interpretations.length > 0 && (
        <section>
          <h3>How to read it</h3>
          <ul>
            {a.interpretations.map((s) => (
              <li key={s.id}>
                {s.text} {refs(s.evidence_ids)}
              </li>
            ))}
          </ul>
        </section>
      )}
      {a.uncertainties.length > 0 && (
        <section>
          <h3>Limits</h3>
          <ul className="answer-muted">
            {a.uncertainties.map((s) => (
              <li key={s.id}>{s.text}</li>
            ))}
          </ul>
        </section>
      )}
      {a.suggested_checks.length > 0 && (
        <section>
          <h3>Checks a person could do</h3>
          <ul>
            {a.suggested_checks.map((c) => (
              <li key={c.id}>{c.text}</li>
            ))}
          </ul>
        </section>
      )}
      {a.evidence_context.length > 0 && (
        <section>
          <h3>Context from NASA</h3>
          <ul className="answer-muted">
            {a.evidence_context.map((s) => (
              <li key={s.id}>
                {s.text} {refs(s.evidence_ids)}
              </li>
            ))}
          </ul>
        </section>
      )}
      {a.citations.length > 0 && (
        <ol className="citations">
          {a.citations.map((c) => (
            <li key={c.evidence_id} id={`cite-${c.evidence_id}`}>
              <a href={c.url} target="_blank" rel="noopener noreferrer">
                {c.document_title}
              </a>{' '}
              <span className="muted">· {c.section}</span>
            </li>
          ))}
        </ol>
      )}
      <p className="answer-foot">
        {a.generation.generative ? `Drafted by ${a.generation.primary_model ?? 'the language model'} and checked against the data.` : 'Written with fixed rules from the stored results.'} {a.data_provenance.crew_data_notice}
      </p>
    </article>
  )
}

export const BubbleIcon = ({ size = 18 }: { size?: number }) => (
  <svg width={size} height={size} viewBox="0 0 32 32" aria-hidden="true">
    {/* ring, back half (behind the planet) */}
    <path d="M3.6 19.6C2.3 17.4 7.6 13.3 15.5 10.7c7.9-2.6 14.4-2.6 15.3-.3" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" opacity="0.55" />
    {/* planet body with a speech-bubble tail at the lower left */}
    <path d="M16.5 6.5a9 9 0 1 1-6.1 15.6l-4.6 2.4 1.6-4.7A9 9 0 0 1 16.5 6.5Z" fill="currentColor" />
    {/* a band on the planet */}
    <path d="M9.3 13.4c3.6-.4 9.2-1.6 14-3.6" fill="none" stroke="var(--card, #fff)" strokeWidth="1.4" strokeLinecap="round" opacity="0.55" />
    {/* ring, front half: a gap in the card colour, then the ring itself */}
    <path d="M30.8 10.4c.8 2.2-4.6 6.3-12.4 8.8-6.9 2.2-12.7 2.6-14.8 1.2" fill="none" stroke="var(--card, #fff)" strokeWidth="4.2" strokeLinecap="round" />
    <path d="M30.8 10.4c.8 2.2-4.6 6.3-12.4 8.8-6.9 2.2-12.7 2.6-14.8 1.2" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
    {/* a small star */}
    <path d="M26 2.6v3.2M24.4 4.2h3.2" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
  </svg>
)
