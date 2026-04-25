import Icon from '@/components/qontext/icon'
import { ConfBadge, SourceBadge, SourceMiniStack, EntityPill } from '@/components/qontext/badges'
import { INAZUMA } from '@/lib/inazuma-mock'

interface Props {
  entityId: string | null
}

export default function EntityDetail({ entityId }: Props) {
  if (!entityId) {
    return (
      <div className="col col-center" style={{ alignItems: 'center', justifyContent: 'center' }}>
        <div className="empty">
          <div className="empty-card">
            <div className="empty-icon"><Icon name="compass" size={26} /></div>
            <div className="empty-title">Select an entity</div>
            <div className="empty-text">Select an entity from the tree on the left to inspect its facts, provenance, and related entities.</div>
          </div>
        </div>
      </div>
    )
  }

  const e = INAZUMA.acme
  const sources = INAZUMA.sources

  return (
    <div className="col col-center">
      <div className="panel-body">
        <div className="detail">
          <div className="detail-crumbs">
            {e.crumbs.map((c, i) => (
              <span key={i} style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
                <a href="#">{c}</a>
                {i < e.crumbs.length - 1 && <Icon name="chevron-right" size={11} className="sep" />}
              </span>
            ))}
            <span className="spacer" />
            <span className="mono">{e.id}</span>
          </div>

          <div className="detail-head">
            <div className="detail-avatar brand">{e.avatar}</div>
            <div className="detail-title-block">
              <div className="detail-eyebrow">{e.eyebrow}</div>
              <h1 className="detail-title">{e.canonical_name}</h1>
              <div className="detail-aliases">
                <em>aka</em>
                {e.aliases.map((a, i) => (
                  <span key={i}>{a}{i < e.aliases.length - 1 ? ', ' : ''}</span>
                ))}
              </div>
              <div className="detail-meta">
                <span className="chip"><Icon name="check-circle" size={12} /> {e.status}</span>
                <span className="chip outline">{e.stats.facts} facts · {e.stats.sources} sources</span>
                <span className="chip outline">Last sync {e.stats.lastSync}</span>
                <span className="chip" style={{ background: 'var(--conf-conflict-soft)', color: 'var(--conf-conflict)', fontWeight: 600 }}>
                  <Icon name="alert" size={12} /> 1 disputed fact
                </span>
              </div>
            </div>
          </div>

          {/* Properties */}
          <div className="detail-section">
            <div className="detail-section-head">
              <span className="detail-section-title">Properties</span>
              <span className="detail-section-count">{e.facts.length}</span>
              <span className="spacer" />
              <div className="detail-section-actions">
                <button className="action-btn" style={{ padding: '4px 8px', background: 'transparent', border: 'none', color: 'var(--text-secondary)', width: 'auto' }}>
                  <Icon name="filter" size={13} /> Filter
                </button>
                <button className="action-btn" style={{ padding: '4px 8px', background: 'transparent', border: 'none', color: 'var(--text-secondary)', width: 'auto' }}>
                  <Icon name="plus" size={13} /> Add fact
                </button>
              </div>
            </div>
            <div className="facts">
              {e.facts.map((f, i) => (
                <div className="fact-row" key={i}>
                  <div className="fact-key">{f.key}</div>
                  <div className={`fact-val${f.disputed ? ' disputed' : ''}`}>
                    {f.link
                      ? <a href="#" className="val-link">{f.val}</a>
                      : <span className="val-text" style={f.mono ? { fontFamily: 'var(--font-mono)', fontSize: 12 } : {}}>{f.val}</span>
                    }
                    <ConfBadge level={f.conf} />
                    <SourceMiniStack srcs={f.srcs} sources={sources} max={3} />
                    {f.disputed && (
                      <span className="chip" style={{ background: 'var(--conf-conflict)', color: 'white', fontWeight: 700, marginLeft: 'auto', cursor: 'pointer' }}>
                        <Icon name="scale" size={11} /> Resolve →
                      </span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Relationships */}
          <div className="detail-section">
            <div className="detail-section-head">
              <span className="detail-section-title">Relationships</span>
              <span className="detail-section-count">{e.relations.length}</span>
              <span className="spacer" />
              <button className="action-btn" style={{ padding: '4px 8px', background: 'transparent', border: 'none', color: 'var(--text-secondary)', width: 'auto' }}>
                <Icon name="graph" size={13} /> View graph
              </button>
            </div>
            <div className="relations">
              {e.relations.map((r, i) => (
                <div className="relation-row" key={i}>
                  <span className="relation-pred">{r.pred}</span>
                  <span className="relation-target">
                    <EntityPill entity={r.target} />
                  </span>
                  <span className="relation-meta">
                    <ConfBadge level={r.conf} />
                    <SourceMiniStack srcs={r.srcs} sources={sources} max={2} />
                  </span>
                </div>
              ))}
            </div>
          </div>

          {/* Source attribution */}
          <div className="detail-section">
            <div className="detail-section-head">
              <span className="detail-section-title">Source attribution</span>
              <span className="detail-section-count">{e.sourceRecords.length}</span>
              <span className="spacer" />
              <span className="panel-sub">Provenance at fact level — every claim re-derived on hash change</span>
            </div>
            <div className="sources-list">
              {e.sourceRecords.map((sr, i) => {
                const s = sources[sr.id]
                if (!s) return null
                return (
                  <div className="source-row" key={i}>
                    <span className="src-icon-wrap">
                      <SourceBadge src={s} mini />
                    </span>
                    <div className="source-info">
                      <div className="source-title">{s.name}</div>
                      <div className="source-meta">
                        <span className="uri">{s.uri}</span>
                        <span>·</span>
                        <span>{s.date}</span>
                      </div>
                    </div>
                    <div className="source-derived">{sr.facts} facts derived</div>
                  </div>
                )
              })}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
