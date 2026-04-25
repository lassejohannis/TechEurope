import { useState } from 'react'
import Icon from '@/components/qontext/icon'
import { ConfBadge, SourceBadge, EntityPill } from '@/components/qontext/badges'
import { INAZUMA } from '@/lib/inazuma-mock'

const FILTERS = [
  { id: 'type',    label: 'Type: any',        active: false },
  { id: 'since',   label: 'Since: 30d',       active: true  },
  { id: 'minconf', label: 'Confidence ≥ 0.7', active: true  },
  { id: 'src',     label: 'Sources: all',     active: false },
] as const

const REFERENCED_ENTITIES = [
  { id: 'ent:acme',       name: 'ACME GmbH',         type: 'customer', initials: 'AC' },
  { id: 'ent:alice',      name: 'Alice Schmidt',      type: 'person',   initials: 'AS' },
  { id: 'ent:jose',       name: 'José Barros',        type: 'person',   initials: 'JB' },
  { id: 'ent:p:flow',     name: 'Inazuma Flow',       type: 'product',  initials: 'IF' },
  { id: 'ent:p:atlas',    name: 'Inazuma Atlas',      type: 'product',  initials: 'IA' },
  { id: 'ent:prj:renewal',name: 'ACME Renewal 2026',  type: 'project',  initials: 'AR' },
  { id: 'ent:tkt:8821',   name: 'INZ-8821',           type: 'ticket',   initials: 'TK' },
]

export default function SearchPage() {
  const [q, setQ] = useState(INAZUMA.search.query)
  const a = INAZUMA.search.answer

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
  }

  return (
    <div className="workspace search" style={{ overflowY: 'auto' }}>
      <div className="col-center" style={{ flex: 1 }}>
        <div className="search-shell">
          <div className="panel-eyebrow" style={{ marginBottom: 10 }}>
            <Icon name="sparkles" size={11} style={{ verticalAlign: '-2px', marginRight: 4 }} />
            Ask the context base
          </div>

          <form onSubmit={handleSubmit}>
            <div className="search-bar-wrap">
              <div className="search-bar">
                <Icon name="search" size={20} className="search-icon" />
                <input
                  value={q}
                  onChange={(e) => setQ(e.target.value)}
                  placeholder="Ask anything about Inazuma…"
                />
                <button type="submit" className="ask-btn">
                  Ask <span className="kbd">↵</span>
                </button>
              </div>
              <div className="search-filters">
                {FILTERS.map((f) => (
                  <span key={f.id} className={`search-filter${f.active ? ' active' : ''}`}>
                    {f.label}
                    {f.active && <Icon name="x" size={10} className="x" />}
                  </span>
                ))}
                <span className="search-filter">
                  <Icon name="plus" size={11} /> Add filter
                </span>
              </div>
            </div>
          </form>

          {/* Answer card */}
          <div className="answer-card">
            <div className="answer-head">
              <span className="ai-mark">Q</span>
              <span className="answer-q">{q}</span>
              <span className="chip" style={{ background: 'var(--conf-high-soft)', color: 'var(--conf-high)', fontWeight: 600 }}>
                <Icon name="check" size={11} /> 5 sources · 0.9s
              </span>
            </div>
            <div className="answer-body">
              {a.paragraphs.map((p, i) => {
                const html = p.replace(/<span data-cite="(\d+)"><\/span>/g, '<span class="cite">$1</span>')
                return <p key={i} dangerouslySetInnerHTML={{ __html: html }} />
              })}
            </div>
            <div className="answer-foot">
              <button><Icon name="thumbs-up" size={13} /> Helpful</button>
              <button><Icon name="thumbs-down" size={13} /> Not quite</button>
              <button><Icon name="copy" size={13} /> Copy</button>
              <span className="spacer" />
              <span>Generated from 5 source records · provenance preserved at fact-level</span>
            </div>
          </div>

          {/* Evidence */}
          <div style={{ marginTop: 24 }}>
            <div className="panel-eyebrow" style={{ marginBottom: 10 }}>Evidence</div>
            <div className="evidence-grid">
              {a.evidence.map((ev) => (
                <div className="evidence-card" key={ev.n}>
                  <span className="src-num">{ev.n}</span>
                  <div className="evidence-body">
                    <div className="evidence-title">
                      <SourceBadge
                        src={{ id: `src:${ev.srcType}:${ev.n}`, type: ev.srcType, name: ev.title, uri: '', date: '' }}
                      />
                      {ev.title}
                    </div>
                    <blockquote className="evidence-quote" dangerouslySetInnerHTML={{ __html: ev.quote }} />
                    <div className="evidence-meta">
                      {ev.meta.map((m, j) => <span key={j}>{m}{j < ev.meta.length - 1 ? ' · ' : ''}</span>)}
                    </div>
                  </div>
                  <div className="evidence-actions">
                    <ConfBadge level={ev.conf} />
                    <button className="action-btn" style={{ padding: '4px 8px', fontSize: 11, width: 'auto', background: 'transparent', border: 'none', color: 'var(--text-secondary)' }}>
                      <Icon name="eye" size={12} /> Open
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Referenced entities */}
          <div style={{ marginTop: 28 }}>
            <div className="panel-eyebrow" style={{ marginBottom: 10 }}>Entities referenced</div>
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
              {REFERENCED_ENTITIES.map((e) => (
                <EntityPill key={e.id} entity={e} />
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
