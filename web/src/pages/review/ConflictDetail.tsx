import Icon from '@/components/qontext/icon'
import { ConfBadge, SourceBadge } from '@/components/qontext/badges'
import { INAZUMA, type MockConflict, type MockClaim } from '@/lib/inazuma-mock'

interface Props {
  conflictId: string | null
}

function ClaimCard({ claim, preferred }: { claim: MockClaim; preferred: boolean }) {
  const sources = INAZUMA.sources
  return (
    <div className={`claim${preferred ? ' preferred' : ''}`}>
      <div className="claim-head">
        <div className="claim-letter-tile">{claim.letter}</div>
        <div className="claim-head-text">
          <div className="claim-source-label">{claim.sourceLabel}</div>
          <div className="claim-source-name">{claim.sourceName}</div>
        </div>
        {preferred && <span className="chip accent" style={{ fontSize: 10 }}>AI suggests</span>}
      </div>
      <div className="claim-value">
        {claim.value}{claim.unit && <span className="unit">{claim.unit}</span>}
      </div>
      <blockquote className="claim-quote" dangerouslySetInnerHTML={{ __html: claim.quote }} />
      <dl className="claim-meta">
        {Object.entries(claim.meta).map(([k, v]) => (
          <span key={k} style={{ display: 'contents' }}>
            <dt>{k}</dt>
            <dd>{v}</dd>
          </span>
        ))}
      </dl>
      <div style={{ display: 'flex', gap: 8, marginTop: 'auto', paddingTop: 8, borderTop: '1px solid var(--border-hair)' }}>
        {sources[claim.srcId] && <SourceBadge src={sources[claim.srcId]} />}
        <span className="spacer" />
        <button className="action-btn" style={{ padding: '4px 8px', width: 'auto', background: 'transparent', border: 'none', color: 'var(--text-secondary)', fontSize: 11 }}>
          <Icon name="eye" size={12} /> Open source
        </button>
      </div>
    </div>
  )
}

export default function ConflictDetail({ conflictId }: Props) {
  if (!conflictId) {
    return (
      <div className="col col-center" style={{ alignItems: 'center', justifyContent: 'center' }}>
        <div className="empty">
          <div className="empty-card">
            <div className="empty-icon"><Icon name="inbox" size={26} /></div>
            <div className="empty-title">Select a conflict</div>
            <div className="empty-text">Pick a pending item from the inbox on the left to review the competing claims and evidence.</div>
          </div>
        </div>
      </div>
    )
  }

  const conflict: MockConflict | undefined = INAZUMA.conflicts.find((c) => c.id === conflictId)
  if (!conflict?.claimA || !conflict.claimB) {
    return (
      <div className="col col-center">
        <div className="panel-body">
          <div className="conflict-detail">
            <div className="conflict-head">
              <div className="conflict-tags">
                <span className="chip outline mono">{conflict?.pred ?? conflictId}</span>
                <ConfBadge level="conflict" label="Pending review" />
              </div>
              <div className="conflict-question">Conflict: {conflict?.subject ?? conflictId}</div>
              <div className="conflict-sub">Detailed evidence will appear here once two competing claims are loaded.</div>
            </div>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="col col-center">
      <div className="panel-body">
        <div className="conflict-detail">
          <div className="conflict-head">
            <div className="conflict-tags">
              <span className="chip outline" style={{ fontFamily: 'var(--font-mono)', fontSize: 10 }}>{conflict.entity}</span>
              <span className="chip outline" style={{ fontFamily: 'var(--font-mono)', fontSize: 10 }}>predicate: {conflict.pred}</span>
              <ConfBadge level="conflict" label="Pending review" />
              <span className="chip" style={{ marginLeft: 'auto', color: 'var(--text-tertiary)' }}>
                <Icon name="history" size={11} /> Disputed since {conflict.since}
              </span>
            </div>
            <div className="conflict-question">What is ACME GmbH's renewal date for 2026?</div>
            <div className="conflict-sub">
              Two sources disagree. Resolution writes back as a <span className="mono">human_resolution</span> source record so future re-runs respect the decision.
              <span style={{ display: 'block', marginTop: 6, color: 'var(--conf-low)' }}>
                <Icon name="alert" size={11} style={{ verticalAlign: '-1px' }} /> Stake: {conflict.stake}
              </span>
            </div>
          </div>

          <div className="claim-grid">
            <ClaimCard claim={conflict.claimA} preferred={conflict.preferred === 'A'} />
            <div className="vs"><span>VS</span></div>
            <ClaimCard claim={conflict.claimB} preferred={conflict.preferred === 'B'} />
          </div>

          {/* AI rationale */}
          <div style={{ marginTop: 20, padding: 16, background: 'var(--surface-panel)', border: '1px solid var(--border-hair)', borderRadius: 10 }}>
            <div className="row" style={{ marginBottom: 10 }}>
              <span style={{ width: 22, height: 22, background: 'var(--brand)', color: 'var(--q-accent)', borderRadius: 5, display: 'grid', placeItems: 'center', fontWeight: 900, fontSize: 10 }}>Q</span>
              <span style={{ fontSize: 12, fontWeight: 700, letterSpacing: '0.06em', textTransform: 'uppercase', color: 'var(--text-tertiary)' }}>AI rationale</span>
              <span className="spacer" />
              <span className="conf-badge med">0.78 confidence</span>
            </div>
            <div style={{ fontSize: 13, color: 'var(--text-secondary)', lineHeight: 1.6 }}>
              The <strong>email from j.barros@acme-gmbh.de</strong> (Source B) is dated <strong>4 days after</strong> the CRM record's last update and is authored by ACME's primary contact, who has authority on contract terms. The phrasing ("confirming our internal alignment") suggests this is a final decision, not a draft. Suggest accepting <strong>Source B (2026-08-31)</strong> and adding a qualifier <span className="mono">{`{reason: "fiscal_close_alignment"}`}</span>. CRM record will be flagged for sync.
            </div>
          </div>

          {/* Downstream impact */}
          <div style={{ marginTop: 20 }}>
            <div className="panel-eyebrow" style={{ marginBottom: 10 }}>Downstream impact</div>
            <div className="sources-list">
              <div className="source-row">
                <span className="src-icon-wrap"><Icon name="target" size={16} className="muted" /></span>
                <div className="source-info">
                  <div className="source-title">Project: ACME Renewal 2026</div>
                  <div className="source-meta">trajectory/projects/acme-renewal-2026.md · target_date will be re-derived</div>
                </div>
                <div className="source-derived">2 facts</div>
              </div>
              <div className="source-row">
                <span className="src-icon-wrap"><Icon name="briefcase" size={16} className="muted" /></span>
                <div className="source-info">
                  <div className="source-title">Customer: ACME GmbH</div>
                  <div className="source-meta">static/customers/acme-gmbh.md · renewal_date fact</div>
                </div>
                <div className="source-derived">1 fact</div>
              </div>
              <div className="source-row">
                <span className="src-icon-wrap"><Icon name="ticket" size={16} className="muted" /></span>
                <div className="source-info">
                  <div className="source-title">Sales pipeline forecast</div>
                  <div className="source-meta">downstream view consumed by Revenue Intelligence app</div>
                </div>
                <div className="source-derived">view</div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
