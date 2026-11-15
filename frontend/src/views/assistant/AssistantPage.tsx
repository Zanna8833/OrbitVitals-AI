import { href } from '../../hooks/useRoute'

/**
 * SLOT for the team's language-model assistant. Nothing is connected in this
 * demo: no prompt is sent anywhere and no answer is generated.
 *
 * To integrate: replace <Conversation /> with the real chat, reading
 * VITE_ASSISTANT_URL (to be added to config.ts) and keeping the boundaries
 * listed on the right (no diagnosis, cite the data used, simulated data only).
 */
const SUGGESTIONS = [
  'Why is my resting heart rate marked as higher than usual?',
  'Who is free of a sleep aid on Wednesday night?',
  'What does “uncertain quality” mean for a reading?',
]

export function AssistantPage() {
  return (
    <div className="today assistant-page">
      <header className="today-head">
        <div className="today-title">
          <a className="back-link-inline" href={href.crew()}>
            ‹ Today
          </a>
          <h1>Assistant</h1>
          <span className="pill tone-gray">Preview · not connected</span>
        </div>
      </header>
      <div className="assistant-grid">
        <section className="card assistant-chat" aria-label="Conversation">
          <div className="chat-scroll">
            <div className="chat-msg is-assistant">
              <span className="chat-avatar" aria-hidden="true">
                <BubbleIcon />
              </span>
              <div>
                <p>
                  Hi — this space is reserved for the team’s assistant. It will answer questions about <strong>your own data in OrbitVitals</strong>:
                  trends, data quality, the sleep plan, the medical team’s messages.
                </p>
                <p className="muted">It is not connected in this demo, so nothing you see here is a generated answer.</p>
              </div>
            </div>
          </div>
          <div className="chat-suggestions" aria-label="Example questions">
            {SUGGESTIONS.map((s) => (
              <button key={s} type="button" className="chip" disabled title="Available once the assistant is connected">
                {s}
              </button>
            ))}
          </div>
          <form className="chat-composer" onSubmit={(e) => e.preventDefault()}>
            <label className="sr-only" htmlFor="ask">
              Ask the assistant
            </label>
            <input id="ask" type="text" placeholder="Ask about your data… (not connected in this demo)" disabled />
            <button type="submit" className="btn btn-primary" disabled>
              Send
            </button>
          </form>
        </section>
        <aside className="assistant-side">
          <section className="card">
            <p className="eyebrow">What it will do</p>
            <ul className="plain-list">
              <li>Explain what a reading, a trend or a quality flag means, using your own data.</li>
              <li>Point to the screen where the information lives.</li>
              <li>Help draft a note for the medical team — you decide whether to send it.</li>
            </ul>
          </section>
          <section className="card">
            <p className="eyebrow">What it will not do</p>
            <ul className="plain-list">
              <li>No diagnosis, no treatment advice, no medication decisions.</li>
              <li>No alarms: urgent matters follow the mission’s procedures.</li>
              <li>Every answer says which data it used.</li>
            </ul>
          </section>
        </aside>
      </div>
    </div>
  )
}

/** A planet shaped like a speech bubble: round body, a short tail, and a tilted ring. */
export const BubbleIcon = ({ size = 18 }: { size?: number }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    {/* planet body with a speech-bubble tail */}
    <path d="M12 4.2a7.3 7.3 0 1 1-4.6 13l-3.3 1.4 1.1-3.2A7.3 7.3 0 0 1 12 4.2Z" />
    {/* ring: the front arc crosses the body, the back arc is hidden behind it */}
    <path d="M3.2 13.6c-.9-1.4 2.9-3.9 8.4-5.4 5.6-1.6 10.2-1.5 10.6.1.3 1-1.5 2.5-4.5 3.9" />
    <circle cx="9.6" cy="10.4" r="0.9" fill="currentColor" stroke="none" />
  </svg>
)
