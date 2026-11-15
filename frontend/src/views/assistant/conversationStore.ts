import { useSyncExternalStore } from 'react'
import { readJob, submitJob, explanationRequest, type AgentDomain, type AgentResponse, type AgentTurn, type ExplanationRequest } from './agentClient'

/**
 * One Assistant conversation per astronaut, kept outside React.
 *
 * - Threads are keyed by the backend crew member id and saved in localStorage, so they
 *   survive closing the Assistant, navigating, switching astronaut and refreshing.
 * - Each question becomes a server-owned job with its own request id. The answer is
 *   written to the turn of the astronaut that asked, whatever page is open; a request
 *   still pending after a refresh is resumed with the same id, never duplicated.
 * - Earlier exchanges of the same astronaut only are sent back as context.
 */

export type Topic = 'all' | AgentDomain

export interface StoredTurn {
  id: string
  crew: string
  question: string
  who: string
  topic: Topic
  askedAt: string
  status: 'pending' | 'done' | 'error'
  answer: AgentResponse | null
  error: string | null
  request: ExplanationRequest
}

type Threads = Readonly<Record<string, readonly StoredTurn[]>>

const STORAGE_KEY = 'orbitvitals.assistant.threads.v1'
const POLL_MS = 1500
const MAX_POLL_FAILURES = 8
/** Agent limit: at most 40 history items (20 exchanges). */
const MAX_CONTEXT_EXCHANGES = 20
const EMPTY: readonly StoredTurn[] = []

let threads: Threads = load()
const listeners = new Set<() => void>()
const polling = new Set<string>()

function load(): Threads {
  try {
    const raw = globalThis.localStorage?.getItem(STORAGE_KEY)
    const parsed = raw ? (JSON.parse(raw) as unknown) : null
    return parsed && typeof parsed === 'object' && !Array.isArray(parsed) ? (parsed as Threads) : {}
  } catch {
    return {}
  }
}

function save() {
  try {
    globalThis.localStorage?.setItem(STORAGE_KEY, JSON.stringify(threads))
  } catch {
    /* storage full or blocked: the conversation stays in memory for this session */
  }
}

function emit() {
  save()
  for (const l of listeners) l()
}

function update(crew: string, id: string, patch: Partial<StoredTurn>) {
  const list = threads[crew]
  if (!list?.some((t) => t.id === id)) return
  threads = { ...threads, [crew]: list.map((t) => (t.id === id ? { ...t, ...patch } : t)) }
  emit()
}

function newRequestId(): string {
  const c = globalThis.crypto
  if (c && typeof c.randomUUID === 'function') return c.randomUUID()
  return `req-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 12)}`
}

/** Completed exchanges of this astronaut, oldest first, as agent context. */
function contextFor(crew: string): AgentTurn[] {
  const done = (threads[crew] ?? EMPTY).filter((t) => t.status === 'done' && t.answer && t.crew === crew).slice(-MAX_CONTEXT_EXCHANGES)
  return done.flatMap((t) => {
    const domain = t.topic === 'all' ? null : t.topic
    return [
      { role: 'operator' as const, text: t.question.slice(0, 2000), crew_member_id: crew, domain },
      { role: 'assistant' as const, text: (t.answer?.headline ?? '').slice(0, 2000), crew_member_id: crew, domain },
    ].filter((x) => x.text.trim().length > 0)
  })
}

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms))

/** Submits (idempotently) and follows one job until it ends. Independent of any component. */
async function follow(turn: StoredTurn) {
  if (polling.has(turn.id)) return
  polling.add(turn.id)
  let failures = 0
  try {
    let job = null
    while (failures < MAX_POLL_FAILURES) {
      try {
        // POST with the same id returns the existing job, so a resumed turn never runs twice.
        job = job === null ? await submitJob(turn.id, turn.request) : await readJob(turn.id)
        failures = 0
        if (job.status !== 'running') break
      } catch (e) {
        failures += 1
        if (failures >= MAX_POLL_FAILURES) {
          update(turn.crew, turn.id, { status: 'error', error: e instanceof Error ? e.message : 'The assistant could not answer.' })
          return
        }
      }
      await sleep(POLL_MS)
    }
    if (!job) return
    if (job.status === 'done' && job.response && job.response.crew_member_id === turn.crew) {
      update(turn.crew, turn.id, { status: 'done', answer: job.response, error: null })
    } else {
      update(turn.crew, turn.id, { status: 'error', error: job.error ?? 'The assistant could not answer.' })
    }
  } finally {
    polling.delete(turn.id)
  }
}

export const conversations = {
  subscribe(listener: () => void) {
    listeners.add(listener)
    return () => listeners.delete(listener)
  },
  thread(crew: string | null): readonly StoredTurn[] {
    return (crew && threads[crew]) || EMPTY
  },
  ask(crew: string, who: string, topic: Topic, question: string) {
    const domain = topic === 'all' ? null : topic
    const turn: StoredTurn = {
      id: newRequestId(),
      crew,
      question: question || 'Give me an overview.',
      who,
      topic,
      askedAt: new Date().toISOString(),
      status: 'pending',
      answer: null,
      error: null,
      request: explanationRequest(crew, domain, question, contextFor(crew)),
    }
    threads = { ...threads, [crew]: [...(threads[crew] ?? EMPTY), turn] }
    emit()
    void follow(turn)
  },
  /** Starts a new conversation for this astronaut only. */
  reset(crew: string) {
    if (!threads[crew]) return
    const { [crew]: _removed, ...rest } = threads
    threads = rest
    emit()
  },
  /** Resumes requests that were still pending when the page was last closed. */
  resume() {
    for (const list of Object.values(threads)) for (const t of list) if (t.status === 'pending') void follow(t)
  },
}

export function useThread(crew: string | null): readonly StoredTurn[] {
  return useSyncExternalStore(conversations.subscribe, () => conversations.thread(crew))
}

conversations.resume()
