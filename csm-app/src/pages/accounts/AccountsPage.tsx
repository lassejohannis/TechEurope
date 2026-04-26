import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Search, RefreshCw, AlertTriangle, TrendingUp, Building2 } from 'lucide-react'
import { useAccounts } from '@/hooks/useAccounts'
import { useCountUp } from '@/hooks/useCountUp'
import { segmentLabel, riskBadge, renewalDaysLeft } from '@/lib/signals'
import type { AccountCard } from '@/types'

function HealthDonut({ score, tier }: { score: number; tier: string }) {
  const r = 8
  const circ = 2 * Math.PI * r
  const filled = (score / 100) * circ
  return (
    <span className="health-donut-wrap">
      <svg className="health-donut-svg" width="20" height="20" viewBox="0 0 20 20">
        <circle className="health-donut-track" cx="10" cy="10" r={r} strokeWidth="2.5" />
        <circle
          className={`health-donut-arc ${tier}`}
          cx="10" cy="10" r={r} strokeWidth="2.5"
          strokeDasharray={`${filled} ${circ}`}
          strokeDashoffset={circ * 0.25}
          transform="rotate(-90 10 10)"
        />
      </svg>
      <span className={`health-score-badge ${tier}`}>{score}</span>
    </span>
  )
}

// ── Data helpers ──────────────────────────────────────────────────────────────

function formatArr(n: number): string {
  if (n >= 1_000_000) return `€${(n / 1_000_000).toFixed(1)}M`
  if (n >= 1_000) return `€${Math.round(n / 1_000)}k`
  return n > 0 ? `€${n}` : '—'
}

function getArr(a: AccountCard): number {
  const f = a.facts.find((f) => f.predicate === 'annual_recurring_revenue_eur')
  if (f && typeof f.object === 'number') return f.object
  const attr = a.entity.attributes['arr_eur']
  return typeof attr === 'number' ? attr : 0
}

function getSubscriptionTier(a: AccountCard): string {
  const f = a.facts.find((f) => f.predicate === 'subscription_tier')
  return typeof f?.object === 'string' ? f.object : ''
}

function getIndustry(a: AccountCard): string {
  const f = a.facts.find((f) => f.predicate === 'industry')
  if (f && typeof f.object === 'string') return f.object
  const attr = a.entity.attributes['industry']
  return typeof attr === 'string' ? attr : ''
}

function getCurrentProduct(a: AccountCard): string {
  const attr = a.entity.attributes['current_product']
  return typeof attr === 'string' ? attr : ''
}

function getRenewalDate(a: AccountCard): string | null {
  const f = a.facts.find((f) => f.predicate === 'renewal_date')
  return typeof f?.object === 'string' ? f.object : null
}

function formatRenewalDate(iso: string): string {
  return new Date(iso).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' })
}

function daysUntil(iso: string): number {
  return Math.ceil((new Date(iso).getTime() - Date.now()) / 86_400_000)
}

// ── Metrics ────────────────────────────────────────────────────────────────────

function computeMetrics(accounts: AccountCard[]) {
  let totalArr = 0
  let atRiskCount = 0
  let renewalSoonCount = 0
  for (const a of accounts) {
    totalArr += getArr(a)
    if (a.health.tier === 'red') atRiskCount++
    const rd = getRenewalDate(a)
    if (rd) {
      const d = daysUntil(rd)
      if (d >= 0 && d <= 90) renewalSoonCount++
    }
  }
  return { total: accounts.length, atRiskCount, renewalSoonCount, totalArr }
}

// ── DHL-style activity timeline ────────────────────────────────────────────────

interface ActivityEvent {
  id: string
  account_id: string
  account_name: string
  label: string
  sublabel: string
  priority: 'red' | 'yellow' | 'green'
  sortKey: number // lower = more urgent
}

function deriveActivity(accounts: AccountCard[]): ActivityEvent[] {
  const events: ActivityEvent[] = []

  for (const a of accounts) {
    const tier = a.health.tier as 'red' | 'yellow' | 'green'
    const name = a.entity.canonical_name
    const id = a.entity.id
    const arr = getArr(a)
    const arrLabel = arr > 0 ? ` · ${formatArr(arr)} ARR` : ''
    const rd = getRenewalDate(a)

    // Critical renewal < 30d
    if (rd) {
      const d = daysUntil(rd)
      if (d >= 0 && d <= 30) {
        events.push({
          id: `${id}-renewal-critical`,
          account_id: id,
          account_name: name,
          label: `Renewal in ${d}d`,
          sublabel: formatRenewalDate(rd) + arrLabel,
          priority: 'red',
          sortKey: d, // most urgent first
        })
      } else if (d > 30 && d <= 90) {
        events.push({
          id: `${id}-renewal-soon`,
          account_id: id,
          account_name: name,
          label: `Renewal in ${d}d`,
          sublabel: formatRenewalDate(rd) + arrLabel,
          priority: 'yellow',
          sortKey: 100 + d,
        })
      }
    }

    // At risk (and no imminent renewal already listed)
    if (tier === 'red' && !events.find((e) => e.id === `${id}-renewal-critical`)) {
      events.push({
        id: `${id}-risk`,
        account_id: id,
        account_name: name,
        label: 'Needs Attention',
        sublabel: `Health ${a.health.score}%${arrLabel}`,
        priority: 'red',
        sortKey: 200 - a.health.score, // lowest health first
      })
    }
  }

  return events.sort((a, b) => a.sortKey - b.sortKey).slice(0, 20)
}

function ActivityTimeline({ accounts }: { accounts: AccountCard[] }) {
  const navigate = useNavigate()
  const events = deriveActivity(accounts)

  if (events.length === 0) {
    return <div className="activity-empty">No urgent activity to review.</div>
  }

  return (
    <div className="activity-timeline">
      {events.map((ev, idx) => (
        <div
          key={ev.id}
          className={`activity-event${idx === events.length - 1 ? ' last' : ''}`}
          onClick={() => navigate(`/accounts/${encodeURIComponent(ev.account_id)}`)}
          role="button"
          tabIndex={0}
          onKeyDown={(e) => { if (e.key === 'Enter') navigate(`/accounts/${encodeURIComponent(ev.account_id)}`) }}
        >
          <div className="activity-dot-col">
            <div className={`activity-dot ${ev.priority}`} />
            {idx < events.length - 1 && <div className="activity-line" />}
          </div>
          <div className="activity-content">
            <div className="activity-account-name">{ev.account_name}</div>
            <div className={`activity-label ${ev.priority}`}>{ev.label}</div>
            <div className="activity-sublabel">{ev.sublabel}</div>
          </div>
        </div>
      ))}
    </div>
  )
}

// ── Page ───────────────────────────────────────────────────────────────────────

export default function AccountsPage() {
  const navigate = useNavigate()
  const { data: accounts, isLoading } = useAccounts()
  const [query, setQuery] = useState('')

  const allAccounts = accounts ?? []
  const metrics = computeMetrics(allAccounts)

  const countTotal    = useCountUp(metrics.total, 700, 0)
  const countAtRisk   = useCountUp(metrics.atRiskCount, 700, 80)
  const countRenewal  = useCountUp(metrics.renewalSoonCount, 700, 160)
  const countArr      = useCountUp(metrics.totalArr, 700, 240)

  const filtered = allAccounts
    .filter((a) => a.entity.canonical_name.toLowerCase().includes(query.toLowerCase()))
    .sort((a, b) => getArr(b) - getArr(a)) // sort by ARR desc

  return (
    <div className="accounts-page">
      {/* ── Top bar ─────────────────────────────── */}
      <div className="accounts-top-bar">
        <div className="accounts-title">Accounts</div>
        <div className="accounts-search-wrap">
          <Search size={14} className="accounts-search-icon" />
          <input
            className="accounts-search"
            type="text"
            placeholder="Search accounts…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
        </div>
      </div>

      {/* ── Metric cards ────────────────────────── */}
      <div className="accounts-metrics">
        <div className="accounts-metric-card">
          <div className="metric-icon neutral"><Building2 size={16} /></div>
          <div className="metric-value">{countTotal}</div>
          <div className="metric-label">Total Accounts</div>
        </div>
        <div className="accounts-metric-card danger">
          <div className="metric-icon danger"><AlertTriangle size={16} /></div>
          <div className="metric-value danger">{countAtRisk}</div>
          <div className="metric-label">At Risk</div>
        </div>
        <div className="accounts-metric-card warn">
          <div className="metric-icon warn"><RefreshCw size={16} /></div>
          <div className="metric-value warn">{countRenewal}</div>
          <div className="metric-label">Renewals ≤90d</div>
        </div>
        <div className="accounts-metric-card success">
          <div className="metric-icon success"><TrendingUp size={16} /></div>
          <div className="metric-value success">{formatArr(countArr)}</div>
          <div className="metric-label">Total ARR</div>
        </div>
      </div>

      {/* ── Two-column body ─────────────────────── */}
      {isLoading ? (
        <div className="empty-state">Loading accounts…</div>
      ) : (
        <div className="accounts-body">
          {/* Table */}
          <div className="accounts-table-wrap">
            {filtered.length === 0 ? (
              <div className="empty-state">No accounts match your search.</div>
            ) : (
              <table className="accounts-table">
                <thead>
                  <tr>
                    <th>Account</th>
                    <th>Industry</th>
                    <th className="col-right">ARR</th>
                    <th className="col-center">Health</th>
                    <th>Renewal</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {filtered.map((account) => {
                    const arr = getArr(account)
                    const tier = getSubscriptionTier(account)
                    const segment = segmentLabel(tier)
                    const industry = getIndustry(account)
                    const product = getCurrentProduct(account)
                    const renewalDate = getRenewalDate(account)
                    const daysLeft = renewalDaysLeft(account)
                    const badge = riskBadge(account)

                    return (
                      <tr
                        key={account.entity.id}
                        className="accounts-row"
                        onClick={() => navigate(`/accounts/${encodeURIComponent(account.entity.id)}`)}
                      >
                        <td>
                          <div className="accounts-name">{account.entity.canonical_name}</div>
                          <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap', marginTop: 2 }}>
                            <span className="segment-chip">{segment}</span>
                            {product && <span className="product-chip">{product}</span>}
                          </div>
                        </td>
                        <td>
                          <span className="accounts-industry">{industry || '—'}</span>
                        </td>
                        <td className="col-right accounts-arr">{formatArr(arr)}</td>
                        <td className="col-center">
                          <HealthDonut score={account.health.score} tier={account.health.tier} />
                        </td>
                        <td>
                          {renewalDate ? (
                            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                              <span className="accounts-renewal-date">{formatRenewalDate(renewalDate)}</span>
                              {daysLeft !== null && (
                                <span className={`days-left-chip ${daysLeft < 30 ? 'urgent' : daysLeft < 90 ? 'soon' : 'ok'}`}>
                                  {daysLeft}d
                                </span>
                              )}
                            </div>
                          ) : (
                            <span style={{ color: 'var(--text-tertiary)' }}>—</span>
                          )}
                        </td>
                        <td>
                          <span className={`risk-badge ${badge.toLowerCase().replace(' ', '-')}`}>
                            {badge}
                          </span>
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            )}
          </div>

          {/* Activity timeline — urgent actions only */}
          <div className="activity-panel">
            <div className="activity-panel-header">Urgent Actions</div>
            <ActivityTimeline accounts={allAccounts} />
          </div>
        </div>
      )}
    </div>
  )
}
