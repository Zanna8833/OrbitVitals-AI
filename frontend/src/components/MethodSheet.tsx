import { useEffect, useRef } from 'react'
import { Sheet } from './ui'
import type { MethodTopic } from './Pillars'

/**
 * Plain-language method notes for the three pillars. They describe what the
 * prototype computes and why (from the team's interviews), and its limits.
 * No clinical claim, no invented literature.
 */
export function MethodSheet({ topic, onClose }: { topic: MethodTopic | null; onClose: () => void }) {
  const refs = { quality: useRef<HTMLElement>(null), baseline: useRef<HTMLElement>(null), trend: useRef<HTMLElement>(null) }
  useEffect(() => {
    if (topic) refs[topic].current?.scrollIntoView({ block: 'start' })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [topic])
  return (
    <Sheet open={!!topic} title="How OrbitVitals reads your data" onClose={onClose} wide>
      <div className="method">
        <section ref={refs.quality} className={topic === 'quality' ? 'is-focus' : undefined}>
          <h3>
            <span className="pillar-n">1</span> Data quality
          </h3>
          <p>
            Every reading carries a quality flag: <strong>good</strong>, <strong>uncertain</strong>, <strong>poor</strong> or <strong>missing</strong>. Movement,
            poor sensor contact or a lost transmission can make a value look physiological when it is not.
          </p>
          <p>
            <em>What the app does:</em> only good readings are used for the baseline and the trend. Uncertain readings are drawn as hollow rings, missing days
            as hatched columns, and nothing is interpolated.
          </p>
          <p className="method-why">Why: interview with D. Simeone (signal artefacts), F. Torchia (calibrated, reliable signals).</p>
        </section>
        <section ref={refs.baseline} className={topic === 'baseline' ? 'is-focus' : undefined}>
          <h3>
            <span className="pillar-n">2</span> Personal baseline
          </h3>
          <p>
            The usual range is computed from <strong>your own</strong> first mission days, using reliable readings only. It is a personal comparison point,
            not a medical reference and not a normal range.
          </p>
          <p>
            <em>What the app does:</em> it shades the range on every chart and states which days it comes from.
          </p>
          <p className="method-why">Why: interview with M. Cerri (values only make sense in the context of the person and the mission).</p>
        </section>
        <section ref={refs.trend} className={topic === 'trend' ? 'is-focus' : undefined}>
          <h3>
            <span className="pillar-n">3</span> Trend
          </h3>
          <p>
            A single unusual day is common. A change is marked as <strong>worth a look</strong> only when reliable readings stay on the same side of the usual
            range for at least <strong>3 consecutive days</strong>.
          </p>
          <p>
            <em>What the app does:</em> it shows how many days, and how far from the usual median, and highlights those days on the chart. It never says
            why — that is for you and the medical team.
          </p>
          <p className="method-why">Why: interview with F. Ongaro (the hard part is telling whether a change is real, and what can be done).</p>
        </section>
        <p className="fineprint">
          Demo settings: the 3-day rule and the baseline days are prototype choices, to be validated with the medical team. Data are simulated.
        </p>
      </div>
    </Sheet>
  )
}
