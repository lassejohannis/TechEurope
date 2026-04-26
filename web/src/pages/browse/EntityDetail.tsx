import Icon from '@/components/qontext/icon'
import { useEntity } from '@/hooks/useEntity'

interface Props { entityId: string | null }

export default function EntityDetail({ entityId }: Props) {
  if (!entityId) {
    return (
      <div className="col col-center" style={{ alignItems: 'center', justifyContent: 'center' }}>
        <div className="empty">
          <div className="empty-card">
            <div className="empty-icon"><Icon name="compass" size={26} /></div>
            <div className="empty-title">Select an entity</div>
            <div className="empty-text">Select an entity from the tree on the left to inspect its facts and provenance.</div>
          </div>
        </div>
      </div>
    )
  }

  const { data, isLoading, isError } = useEntity(entityId)
  if (isLoading) return <div className="col"><div className="panel-body">Loading…</div></div>
  if (isError || !data) return <div className="col"><div className="panel-body">Failed to load entity.</div></div>

  const e = data

  return (
    <div className="col col-center">
      <div className="panel-body">
        <div className="detail">
          <div className="detail-crumbs">
            <a href="#">{e.entity_type}</a>
            <span className="spacer" />
            <span className="mono">{e.id}</span>
          </div>

          <div className="detail-head">
            <div className="detail-avatar brand">{e.canonical_name.charAt(0).toUpperCase()}</div>
            <div className="detail-title-block">
              <div className="detail-eyebrow">{e.entity_type}</div>
              <h1 className="detail-title">{e.canonical_name}</h1>
              {e.aliases.length > 0 && (
                <div className="detail-aliases">
                  <em>aka</em> {e.aliases.join(', ')}
                </div>
              )}
              <div className="detail-meta">
                <span className="chip">live</span>
                <span className="chip outline">{e.fact_count} facts · diversity {e.source_diversity}</span>
              </div>
            </div>
          </div>

          {/* Properties */}
          <div className="detail-section">
            <div className="detail-section-head">
              <span className="detail-section-title">Properties</span>
              <span className="detail-section-count">{e.facts.length}</span>
              <span className="spacer" />
            </div>
            <div className="facts">
              {e.facts.map((f) => (
                <div className="fact-row" key={f.id}>
                  <div className="fact-key">{f.predicate.replace(/_/g, ' ')}</div>
                  <div className={`fact-val${f.status === 'disputed' ? ' disputed' : ''}`}>
                    <span className="val-text" style={{ fontFamily: 'var(--font-mono)', fontSize: 12 }}>
                      {f.object_literal != null ? String(f.object_literal) : (f.object_id ?? '—')}
                    </span>
                    <span className="chip outline" style={{ marginLeft: 8 }}>{(f.confidence ?? 0).toFixed(2)}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
