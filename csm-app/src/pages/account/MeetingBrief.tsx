import { CheckCircle2, AlertTriangle, XCircle } from 'lucide-react'
import type { AccountCard } from '@/types'

const STATUS_ICONS: Record<string, React.ReactNode> = {
  green:  <CheckCircle2 size={15} style={{ color: 'var(--conf-high)', flexShrink: 0, marginTop: 1 }} />,
  yellow: <AlertTriangle size={15} style={{ color: 'var(--conf-med)', flexShrink: 0, marginTop: 1 }} />,
  red:    <XCircle size={15} style={{ color: 'var(--conf-conflict)', flexShrink: 0, marginTop: 1 }} />,
}

// Predicates to show as "quick facts" with clean display labels
const FACT_LABELS: Record<string, string> = {
  annual_recurring_revenue_eur: 'ARR',
  renewal_date:                 'Renewal',
  subscription_tier:            'Tier',
  industry:                     'Industry',
  has_industry:                 'Industry',
  has_business_type:            'Business type',
  has_email:                    'Contact email',
  has_phone_number:             'Phone',
  has_registered_address:       'Address',
  has_external_id:              'CRM ID',
}

// Predicates to skip (internal / not useful for humans)
const SKIP = new Set(['has_contact_person', 'has_document', 'has_communication', 'participant_in'])

function formatFactValue(predicate: string, value: unknown): string {
  if (predicate === 'annual_recurring_revenue_eur' && typeof value === 'number') {
    if (value >= 1_000_000) return `€${(value / 1_000_000).toFixed(1)}M`
    if (value >= 1_000) return `€${Math.round(value / 1_000)}k`
    return `€${value}`
  }
  if (predicate === 'renewal_date' && typeof value === 'string') {
    return new Date(value).toLocaleDateString('en-GB', { day: 'numeric', month: 'long', year: 'numeric' })
  }
  return String(value ?? '—')
}

function renewalDaysLeft(renewalDateStr: string | undefined): number | null {
  if (!renewalDateStr) return null
  return Math.ceil((new Date(renewalDateStr).getTime() - Date.now()) / 86_400_000)
}

interface Props {
  account: AccountCard
}

export default function MeetingBrief({ account }: Props) {
  const { entity, facts, recent_communications, executive_summary } = account

  // ── Collect the best display facts (dedup by label) ──────────────────────
  const seenLabels = new Set<string>()
  const displayFacts: Array<{ label: string; value: string; disputed: boolean }> = []

  for (const f of facts) {
    if (SKIP.has(f.predicate)) continue
    const label = FACT_LABELS[f.predicate]
    if (!label || seenLabels.has(label)) continue
    seenLabels.add(label)
    displayFacts.push({
      label,
      value: formatFactValue(f.predicate, f.object),
      disputed: f.status === 'disputed',
    })
  }

  // Fill in from attrs if facts didn't cover it
  const attrs = entity.attributes
  if (!seenLabels.has('ARR') && attrs['arr_eur']) {
    const n = Number(attrs['arr_eur'])
    displayFacts.unshift({ label: 'ARR', value: n >= 1_000_000 ? `€${(n / 1_000_000).toFixed(1)}M` : `€${Math.round(n / 1_000)}k`, disputed: false })
  }
  if (!seenLabels.has('Renewal') && attrs['renewal_date']) {
    const d = renewalDaysLeft(String(attrs['renewal_date']))
    const label = d !== null && d >= 0 ? `${formatFactValue('renewal_date', attrs['renewal_date'])} (${d}d)` : formatFactValue('renewal_date', attrs['renewal_date'])
    displayFacts.splice(1, 0, { label: 'Renewal', value: label, disputed: false })
  }
  if (!seenLabels.has('Industry') && attrs['industry']) {
    displayFacts.push({ label: 'Industry', value: String(attrs['industry']), disputed: false })
  }
  if (attrs['current_product']) {
    displayFacts.push({ label: 'Product', value: String(attrs['current_product']), disputed: false })
  }
  if (attrs['poc_status']) {
    displayFacts.push({ label: 'PoC status', value: String(attrs['poc_status']), disputed: false })
  }

  const disputedFacts = facts.filter((f) => f.status === 'disputed')
  const hasOpenItems = disputedFacts.length > 0 || executive_summary.cta_type !== 'none'

  return (
    <>
      {/* ── Executive status ─────────────────────────────── */}
      <div className={`brief-status-card ${account.health.tier}`}>
        <div className="brief-status-header">
          {STATUS_ICONS[account.health.tier] ?? null}
          <div className="brief-status-label">{executive_summary.status_label}</div>
        </div>
        <div className="brief-status-why">{executive_summary.why}</div>
        <div className="brief-status-impact">{executive_summary.impact}</div>
      </div>

      {/* ── Know before you go ───────────────────────────── */}
      {displayFacts.length > 0 && (
        <div className="brief-card">
          <div className="brief-section-title">Know before you go</div>
          {displayFacts.map((f) => (
            <div key={f.label} className="brief-item">
              <span className="brief-fact-label">{f.label}</span>
              <span className={`brief-fact-value${f.disputed ? ' disputed' : ''}`}>
                {f.value}
                {f.disputed && <span className="brief-disputed-badge">⚠ Disputed</span>}
              </span>
            </div>
          ))}
        </div>
      )}

      {/* ── Open items ───────────────────────────────────── */}
      {hasOpenItems && (
        <div className="brief-card">
          <div className="brief-section-title">Open items</div>

          {/* Recommended next action */}
          <div className="brief-item brief-action-item">
            <span className="brief-action-dot" />
            <span className="brief-action-text">{executive_summary.next_action}</span>
          </div>

          {/* Disputed facts */}
          {disputedFacts.map((f) => (
            <div key={f.id} className="brief-item">
              <span className="brief-bullet">·</span>
              <span style={{ color: 'var(--conf-conflict)' }}>
                <strong>Disputed:</strong> {f.predicate.replace(/has_|_/g, ' ').trim()} — value{' '}
                <em>{String(f.object)}</em> is contested
              </span>
            </div>
          ))}
        </div>
      )}

      {/* ── Talking points (communications) ─────────────── */}
      {recent_communications.length > 0 && (
        <div className="brief-card">
          <div className="brief-section-title">Context & talking points</div>
          {recent_communications.map((c) => (
            <div key={c.id} className="brief-item">
              <span className="brief-bullet">·</span>
              <span className="brief-comm-text">{c.subject}</span>
            </div>
          ))}
        </div>
      )}
    </>
  )
}
