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
  'Who is free of a sleeping pill on Wednesday night?',
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
/**
 * The assistant's mark: a ringed planet (unmistakably Saturn-like) whose body
 * ends in a speech-bubble tail. Solid body, ring passing in front of it.
 */
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
