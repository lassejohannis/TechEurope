import Icon from '@/components/qontext/icon'
import { SourceBadge } from '@/components/qontext/badges'
import { INAZUMA } from '@/lib/inazuma-mock'

interface Props {
  entityId: string | null
}

export default function ActionPanel({ entityId }: Props) {
  if (!entityId) {
    return (
      <div className="col">
        <div className="panel-header sticky">
          <span className="panel-title">Actions</span>
        </div>
        <div className="empty">
          <div className="empty-card">
            <div className="empty-text" style={{ color: 'var(--text-tertiary)', fontSize: 13 }}>
              Actions appear here once you select an entity — propose facts, flag disputes, or trace provenance.
            </div>
          </div>
        </div>
      </div>
    )
  }

  const e = INAZUMA.acme
  const sources = INAZUMA.sources

  return (
    <div className="col">
      <div className="panel-header sticky">
        <span className="panel-title">Actions</span>
        <span className="spacer" />
        <span className="panel-sub">{e.canonical_name}</span>
      </div>
      <div className="panel-body action-panel">

        <div className="action-section">
          <h4>Quick actions</h4>
          <div className="action-list">
            <button className="action-btn primary">
              <span className="icon"><Icon name="scale" size={14} /></span>
              <span className="label">Resolve disputed fact</span>
              <span className="kbd">R</span>
            </button>
            <button className="action-btn">
              <span className="icon"><Icon name="edit" size={14} /></span>
              <span className="label">Edit entity</span>
              <span className="kbd">E</span>
            </button>
            <button className="action-btn">
              <span className="icon"><Icon name="merge" size={14} /></span>
              <span className="label">Merge with…</span>
            </button>
            <button className="action-btn">
              <span className="icon"><Icon name="plus" size={14} /></span>
              <span className="label">Propose new fact</span>
            </button>
          </div>
        </div>

        <div className="action-section">
          <h4>Memory</h4>
          <div className="stat-row">
            <div className="stat">
              <div className="stat-label">Facts</div>
              <div className="stat-value">{e.stats.facts}</div>
              <div className="stat-trend">+3 this wk</div>
            </div>
            <div className="stat">
              <div className="stat-label">Sources</div>
              <div className="stat-value">{e.stats.sources}</div>
              <div className="stat-trend">+1 today</div>
            </div>
            <div className="stat">
              <div className="stat-label">Derived</div>
              <div className="stat-value">{e.stats.derived}</div>
              <div className="stat-trend">auto</div>
            </div>
            <div className="stat">
              <div className="stat-label">Disputed</div>
              <div className="stat-value" style={{ color: 'var(--conf-conflict)' }}>1</div>
              <div className="stat-trend warn">needs review</div>
            </div>
          </div>
        </div>

        <div className="action-section">
          <h4>Recent activity</h4>
          <div className="timeline">
            {e.activity.map((a, i) => (
              <div className="timeline-item" key={i}>
                <span className="timeline-icon"><Icon name={a.icon} size={11} /></span>
                <div>
                  <div className="timeline-content" dangerouslySetInnerHTML={{ __html: a.text }} />
                  <div className="timeline-time">{a.ts}</div>
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="action-section">
          <h4>Source attribution</h4>
          <div className="sources-list">
            {e.sourceRecords.slice(0, 3).map((sr, i) => {
              const s = sources[sr.id]
              if (!s) return null
              return (
                <div className="source-row" key={i} style={{ gridTemplateColumns: '20px 1fr auto' }}>
                  <span className="src-icon-wrap"><SourceBadge src={s} mini /></span>
                  <div className="source-info">
                    <div className="source-title">{s.name.split('—')[0].trim()}</div>
                    <div className="source-meta"><span className="uri">{s.date}</span></div>
                  </div>
                  <div className="source-derived">{sr.facts}f</div>
                </div>
              )
            })}
          </div>
        </div>

        <div className="action-section">
          <h4>Agent / API</h4>
          <div className="action-list">
            <button className="action-btn">
              <span className="icon"><Icon name="code" size={14} /></span>
              <span className="label">Open in MCP inspector</span>
            </button>
            <button className="action-btn">
              <span className="icon"><Icon name="copy" size={14} /></span>
              <span className="label">Copy entity ID</span>
            </button>
            <button className="action-btn">
              <span className="icon"><Icon name="share" size={14} /></span>
              <span className="label">Share view</span>
            </button>
          </div>
        </div>

      </div>
    </div>
  )
}
