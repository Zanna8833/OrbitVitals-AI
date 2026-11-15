import { config } from '../../config'

/**
 * Client of the team's assistant service (ai_agent/, POST /agent/v1/explanations).
 * The service reads the backend with GET only, answers from stored results,
 * cites NASA summaries and never diagnoses. Shapes follow
 * ai_agent/schemas/agent_response.schema.json (fields the interface uses).
 */
export type AgentDomain = 'vital_signs' | 'sleep' | 'physical_activity' | 'nutrition'

export interface AgentSentence {
  id: string
  text: string
  origin: 'rule' | 'model'
  fact_ids: string[]
  evidence_ids: string[]
}
export interface AgentInterpretation extends AgentSentence {
  kind: string
  confidence: string
}
export interface AgentCheck {
  id: string
  action_code: string
  text: string
  rationale: string
  requires_human_review: boolean
}
export interface AgentCitation {
  evidence_id: string
  publisher: string
  document_title: string
  section: string
  url: string
  summary: string
}
export interface AgentResponse {
  crew_member_id: string
  question: string | null
  status_summary: string
  headline: string
  headline_origin: 'rule' | 'model'
  observations: AgentSentence[]
  evidence_context: AgentSentence[]
  interpretations: AgentInterpretation[]
  uncertainties: AgentSentence[]
  suggested_checks: AgentCheck[]
  human_review: { recommended: boolean; reasons: string[] }
  citations: AgentCitation[]
  data_provenance: { crew_data_kind: string; crew_data_notice: string; evidence_notice: string }
  generation: { mode: string; generative: boolean; fallback_reason: string | null; primary_model: string | null }
  disclaimer: string
}
export interface AgentHealth {
  status: string
  backend: { reachable: boolean }
  primary_model: { name: string; available: boolean }
}

export class AgentError extends Error {}

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response
  try {
    res = await fetch(`${config.agentBaseUrl.replace(/\/$/, '')}${path}`, {
      ...init,
      headers: { Accept: 'application/json', ...(init?.body ? { 'Content-Type': 'application/json' } : {}) },
    })
  } catch {
    throw new AgentError('The assistant service is not reachable.')
  }
  if (!res.ok) {
    let detail = `Assistant error ${res.status}`
    try {
      const body = (await res.json()) as { detail?: unknown }
      if (typeof body.detail === 'string') detail = body.detail
    } catch {
      /* not JSON */
    }
    if (res.status === 502) detail = 'The assistant cannot read the OrbitVitals server right now.'
    throw new AgentError(detail)
  }
  return (await res.json()) as T
}

export function agentHealth(): Promise<AgentHealth> {
  return call<AgentHealth>('/health')
}

export function askAgent(crewMemberId: string, domain: AgentDomain | null, question: string): Promise<AgentResponse> {
  return call<AgentResponse>('/explanations', {
    method: 'POST',
    body: JSON.stringify({ crew_member_id: crewMemberId, domain, question: question.trim() || null, mode: 'auto' }),
  })
}
