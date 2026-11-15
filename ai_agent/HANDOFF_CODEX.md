# Assistant chat: frontend handoff

For the frontend integration of `POST /agent/v1/explanations` (agent schema 0.2.0).
Source: branch `feature/ai-agent-integration`, verified at commit `60c6519` (not on
`main`; it also contains the NASA evidence adapter merged from `cc7c55a`). Everything
below is optional and additive: the current client in
`frontend/src/views/assistant/agentClient.ts` keeps working unchanged.

## 0. Start the services

```powershell
# Backend of this branch (includes /api/v1/nasa-evidence), then the demo data
Set-Location backend
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
python -m app.demo_seed seed --base-url 'http://127.0.0.1:8000/api/v1'

# Models (Ollama): Qwen is required for generated answers, MedGemma is optional
ollama pull qwen3.5:4b
ollama pull medgemma1.5:4b

# Agent on port 8100 (frontend config: agentBaseUrl = http://127.0.0.1:8100/agent/v1)
Set-Location ai_agent
py -3.11 -m venv .venv; .\.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
# optional, for MedGemma's rag/ background: CPU torch, then requirements-specialist.txt
$env:ORBITVITALS_AGENT_BACKEND_BASE_URL = "http://127.0.0.1:8000/api/v1"
$env:ORBITVITALS_AGENT_SPECIALIST = "medgemma"   # or "none": Qwen only
uvicorn orbit_agent.api:app --port 8100
```

`GET /agent/v1/health` reports the backend, Qwen and MedGemma availability. Without
Ollama the agent still answers with fixed rule-based sentences (`generation.generative:
false`).

## Who answers what (routing; nothing to do in the frontend)

| Message | `answer_profile` | Models |
| --- | --- | --- |
| Greeting, thanks, "what can you do?", off-topic | `conversation` | Qwen, ~1-1.5 s |
| General science, dashboard or mission question | `general` | Qwen, ~4-8 s |
| Stored values ("How much did Crew A sleep?") | `brief` | Qwen, ~5-7 s |
| Why / meaning / trend of a result | `full` | Qwen; MedGemma reviews only readings of a flagged result, ~17-20 s |
| Medication, dose, diagnosis | `full` | Qwen, no advice given; never MedGemma |

`generation.specialist.decision` says whether MedGemma was consulted and why not. Show
a loading state: reviewed answers can take about 20 s.

## 1. Request: two new optional fields

```ts
export interface AgentTurn {
  role: 'operator' | 'assistant'
  text: string                 // 1-2000 characters
  crew_member_id?: string | null
  domain?: AgentDomain | null
}

export function askAgent(
  crewMemberId: string,
  domain: AgentDomain | null,
  question: string,
  conversation: AgentTurn[] = [],
  language?: 'en' | 'it',
): Promise<AgentResponse> {
  return call<AgentResponse>('/explanations', {
    method: 'POST',
    body: JSON.stringify({
      crew_member_id: crewMemberId,
      domain,
      question: question.trim() || null,
      mode: 'auto',
      conversation,              // omit or [] for a single question
      ...(language ? { language } : {}),
    }),
  })
}
```

### `conversation` (chat history)

- The agent stores nothing between requests. The chat history lives in the frontend and
  is sent with every request; the agent uses the last 8 turns.
- Oldest first, at most 40 items. Per earlier exchange, append two turns:
  - `{ role: 'operator', text: <the question as typed>, crew_member_id, domain }`
  - `{ role: 'assistant', text: <response.headline>, crew_member_id, domain }`
- Send the headline only, not the whole report.
- **Always set `crew_member_id`** on every turn to the crew member that exchange was
  about. Turns for another crew member are ignored, so switching the selected astronaut
  needs no special handling. As a second guard, a turn that names another crew member
  ("Crew A", "Vega", ...) is ignored even without the field.
- Do not include the current question; it goes in `question`.
- Simplest option: keep one history per crew member, or one shared history and let the
  agent filter it.

### `language`

- Omit it: English by default; Italian when the operator writes in Italian or asks for it
  ("rispondi in italiano").
- Set `'en'` or `'it'` only to force a language, for example from a language switch.

## 2. Response: what to read

New fields in `generation` (add them to the `AgentResponse` type if used):

```ts
generation: {
  mode: string; generative: boolean; fallback_reason: string | null; primary_model: string | null
  question_kind: 'none' | 'greeting' | 'general' | 'factual' | 'interpretive' | 'clinical_advice'
  answer_profile: 'conversation' | 'general' | 'brief' | 'full'
  reply_language: 'en' | 'it'
  context_turns: number        // earlier turns the model used; 0 = answered on its own
}
```

### Conversational answers (`generation.answer_profile === 'conversation'`)

Greetings, thanks, small talk, "what can you do?", "how does OrbitVitals work?",
out-of-scope requests. The response has:

- `headline`: the reply. Show it as a plain chat message.
- `observations`, `interpretations`, `evidence_context`, `suggested_checks`, `citations`:
  empty. `uncertainties`: usually empty (a fixed sentence when the operator mentions the
  mission, or asks about an earlier message without history being sent).
- `human_review.recommended`: `false`.
- `facts`, `status_summary`: still filled; do not render them for this profile.

The current `Answer` component already hides empty sections, so no change is required;
rendering a conversational answer as a compact bubble (headline only) is recommended.

### Other answers

Unchanged: render the sections as today. Model sentences may be Italian when
`reply_language === 'it'`; the fixed rule-based sentences (limits, checks, status line)
are English.

## 3. Compatibility

- Requests without `conversation` and `language` behave exactly as before.
- Unknown request fields are still rejected (`422`): send only the fields above.
- `schema_version` is `0.2.0`; the snapshot is `ai_agent/schemas/agent_response.schema.json`
  and `ai_agent/schemas/explanation_request.schema.json`.
- Errors are unchanged: `502` when the backend cannot be read.

## 4. Guarantees the frontend can rely on

- Crew values, statuses and dates in an answer come only from the backend records of the
  requested `crew_member_id`. History is used to understand follow-up questions ("And
  compared to yesterday?"), never as a source of values: a number repeated from the
  history that the backend does not hold for this crew member is rejected.
- History turns about another crew member are dropped: by `crew_member_id`, and by name
  ("Crew A", "Astronaut A", "Vega", ...; setting `CREW_ALIASES`, defaults match
  `frontend/src/config.ts` and the demo seeder). A model sentence naming another crew
  member fails the `crew_identity` audit check, and a rule-based answer is returned
  instead. Verified live with Qwen (Crew A history in Crew B's context, untagged
  "Astronaut A" history, Crew B values credited to Crew A): 4 of 4 checks passed.
- Replies that claim memory without history, actions (notify, schedule) or a lack of
  access to the data are rejected.
- MedGemma is never called for conversational answers.
- `verification.passed` is true for every returned answer; the response lists failed
  checks otherwise.

## 5. Quick check

```bash
curl -s localhost:8100/agent/v1/explanations -H 'Content-Type: application/json' -d '{
  "crew_member_id": "sim-mission-v1-01", "question": "And compared to yesterday?",
  "conversation": [
    {"role": "operator", "text": "How much did Crew A sleep?", "crew_member_id": "sim-mission-v1-01"},
    {"role": "assistant", "text": "Crew A slept 480 minutes with nominal status.", "crew_member_id": "sim-mission-v1-01"}
  ]}' | jq '.generation.context_turns, .generation.question_kind, .headline'
```

Expected: `2`, `"interpretive"`, a headline about Crew A's sleep.

Essential end-to-end checks from the dashboard (agent on 8100, seeded backend):

| Send | Expect |
| --- | --- |
| "ciao" | Italian greeting only; `answer_profile: "conversation"`, `reply_language: "it"`, no sections, no review banner |
| "How does OrbitVitals work?" | Short description; no sections |
| Crew A, "How much did Crew A sleep?" then "And compared to yesterday?" with history | Second answer `context_turns: 2`, values from Crew A's records |
| Crew B selected, history from Crew A, "And compared to yesterday?" | `context_turns: 0`; nothing about Crew A |
| Crew B, "Why is Noor's sleep flagged?" | Full answer; `specialist.decision: "consulted"` when MedGemma is configured |
| "Which medication should Noor take?" | No advice; `decision: "clinical_advice_question"` |
| Stop Ollama, send "Hello" | Fixed greeting, `generative: false` |
| Request without `conversation` and `language` | Same behaviour as before |

Agent tests (offline, no models): `cd ai_agent; python -m pytest` (372 pass at
`60c6519`; `tests/test_multiturn.py`, `tests/test_bilingual.py`,
`tests/test_conversation.py` cover this handoff). A full description is in
[INTEGRATION.md](INTEGRATION.md).
