import { useState } from 'react'
import Icon from '@/components/qontext/icon'
import { INAZUMA } from '@/lib/inazuma-mock'

interface Props {
  conflictId: string | null
}

const OPTS = [
  { id: 'A',      title: 'Accept Source A — CRM',          desc: 'renewal_date = 2026-06-15', kbd: '1' },
  { id: 'B',      title: 'Accept Source B — Email',        desc: 'renewal_date = 2026-08-31', kbd: '2' },
  { id: 'BOTH',   title: 'Keep both with qualifier',       desc: 'Add context (e.g. EMEA vs US, draft vs final)', kbd: '3' },
  { id: 'CUSTOM', title: 'Custom value',                   desc: 'Enter a different value entirely', kbd: '4' },
  { id: 'REJECT', title: 'Reject both',                    desc: 'Mark fact as unknown — no claim survives', kbd: '5' },
]

function optLetter(id: string) {
  if (id === 'BOTH')   return '+'
  if (id === 'CUSTOM') return '✎'
  if (id === 'REJECT') return '✕'
  return id
}

export default function DecisionPanel({ conflictId }: Props) {
  const [choice, setChoice] = useState<string | null>('B')
  const [rationale, setRationale] = useState('')

  const conflict = INAZUMA.conflicts.find((c) => c.id === conflictId)

  if (!conflictId || !conflict?.claimA) {
    return (
      <div className="col">
        <div className="panel-header sticky">
          <span className="panel-title">Decide</span>
        </div>
        <div className="empty">
          <div className="empty-card">
            <div className="empty-text" style={{ color: 'var(--text-tertiary)', fontSize: 13 }}>
              Decision controls appear when a conflict is selected.
            </div>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="col">
      <div className="panel-header sticky">
        <span className="panel-title">Decide</span>
        <span className="spacer" />
        <span className="panel-sub">2 of 5 this session</span>
      </div>
      <div className="decide-panel">
        <div className="decide-head">
          <h3>Resolve renewal_date</h3>
          <p>Your decision becomes a <span className="mono">human_resolution</span> source. Future ingests will respect it.</p>
        </div>
        <div className="decide-body">
          {OPTS.map((o) => (
            <button
              key={o.id}
              className={`decide-option${choice === o.id ? ' selected' : ''}`}
              onClick={() => setChoice(o.id)}
            >
              <div className="decide-option-head">
                <span className="decide-option-letter">{optLetter(o.id)}</span>
                <span className="decide-option-title">{o.title}</span>
                <span className="kbd">{o.kbd}</span>
              </div>
              <div className="decide-option-desc">{o.desc}</div>
            </button>
          ))}

          <div className="decide-rationale">
            <label>Rationale (optional)</label>
            <textarea
              placeholder="Why this decision? Helps future re-runs and audit."
              value={rationale}
              onChange={(e) => setRationale(e.target.value)}
            />
          </div>
        </div>

        <div className="decide-foot">
          <button className="btn btn-ghost">
            Skip <span className="kbd"><Icon name="arrow-right" size={10} /></span>
          </button>
          <button className="btn btn-primary" disabled={!choice}>
            Resolve <span className="kbd">↵</span>
          </button>
        </div>
      </div>
    </div>
  )
}
