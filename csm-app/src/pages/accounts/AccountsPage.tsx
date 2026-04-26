import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Search } from 'lucide-react'
import { useAccounts } from '@/hooks/useAccounts'
import { segmentLabel, riskBadge, renewalDaysLeft } from '@/lib/signals'
import type { AccountCard } from '@/types'

function formatArr(n: number): string {
  if (n >= 1_000_000) return `€${(n / 1_000_000).toFixed(1)}M`
  if (n >= 1_000) return `€${Math.round(n / 1_000)}k`
  return `€${n}`
}

function getArr(account: AccountCard): number {
  const fact = account.facts.find((f) => f.predicate === 'annual_recurring_revenue_eur')
  if (fact && typeof fact.object === 'number') return fact.object
  const attr = account.entity.attributes['arr_eur']
  return typeof attr === 'number' ? attr : 0
}

function getSubscriptionTier(account: AccountCard): string {
  const fact = account.facts.find((f) => f.predicate === 'subscription_tier')
  return typeof fact?.object === 'string' ? fact.object : ''
}

function getRenewalDate(account: AccountCard): string | null {
  const fact = account.facts.find((f) => f.predicate === 'renewal_date')
  return typeof fact?.object === 'string' ? fact.object : null
}

function formatRenewalDate(iso: string): string {
  return new Date(iso).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' })
}

function healthTrend(account: AccountCard): 'up' | 'down' | 'flat' {
  const top = [...account.health.factors].sort((a, b) => b.weight - a.weight)[0]
  return top?.trend ?? 'flat'
}

const TREND_ARROW: Record<'up' | 'down' | 'flat', string> = { up: '↑', down: '↓', flat: '→' }
const TREND_COLOR: Record<'up' | 'down' | 'flat', string> = {
  up: 'var(--conf-high)',
  down: 'var(--conf-conflict)',
  flat: 'var(--text-tertiary)',
}

type TrackingStatus = 'done' | 'current' | 'upcoming'

interface TrackingEvent {
  id: string
  timestamp: string
  station: string
  title: string
  detail: string
  status: TrackingStatus
}

function formatTrackingTime(iso: string): string {
  const date = new Date(iso)
  return date.toLocaleDateString('de-DE', {
    weekday: 'short',
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
  }) + ', ' + date.toLocaleTimeString('de-DE', { hour: '2-digit', minute: '2-digit' })
}

function asValidDate(iso: string | null | undefined): Date | null {
  if (!iso) return null
  const d = new Date(iso)
  return Number.isNaN(d.getTime()) ? null : d
}

function buildTrackingEvents(account: AccountCard): TrackingEvent[] {
  const now = new Date()
  const renewalIso = getRenewalDate(account)
  const renewal = asValidDate(renewalIso)
  const updated = asValidDate(account.entity.updated_at) ?? new Date(now.getTime() - 60 * 60 * 1000)
  const created = asValidDate(account.entity.created_at) ?? new Date(now.getTime() - 14 * 24 * 60 * 60 * 1000)
  const badge = riskBadge(account)

  const events: TrackingEvent[] = []
  events.push({
    id: `${account.entity.id}:health`,
    timestamp: updated.toISOString(),
    station: 'Health Engine',
    title: `Status aktualisiert: ${badge}`,
    detail: account.executive_summary.why,
    status: 'current',
  })

  if (renewal) {
    events.push({
      id: `${account.entity.id}:renewal`,
      timestamp: renewal.toISOString(),
      station: 'Contract Station',
      title: 'Renewal-Datum im Account-Kontext',
      detail: `Verlängerungstermin ${renewal.toLocaleDateString('de-DE')}`,
      status: renewal.getTime() > now.getTime() ? 'upcoming' : 'done',
    })
  }

  events.push({
    id: `${account.entity.id}:action`,
    timestamp: new Date(updated.getTime() - 2 * 60 * 60 * 1000).toISOString(),
    station: 'CSM Action Queue',
    title: 'Nächster Schritt eingeplant',
    detail: account.executive_summary.next_action,
    status: 'done',
  })

  events.push({
    id: `${account.entity.id}:onboard`,
    timestamp: created.toISOString(),
    station: 'Context Ingestion',
    title: 'Account im Core Layer angelegt',
    detail: `Entity ${account.entity.type} mit ${account.facts.length} Facts`,
    status: 'done',
  })

  return events.sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime())
}

function priorityRank(account: AccountCard): number {
  const badge = riskBadge(account)
  if (badge === 'At Risk') return 0
  if (badge === 'Renewing') return 1
  if (badge === 'Expansion') return 2
  return 3
}

export default function AccountsPage() {
  const navigate = useNavigate()
  const { data: accounts, isLoading } = useAccounts()
  const [query, setQuery] = useState('')

  const filtered = (accounts ?? []).filter((a) =>
    a.entity.canonical_name.toLowerCase().includes(query.toLowerCase())
  )
  const totalArr = filtered.reduce((sum, account) => sum + getArr(account), 0)
  const atRisk = filtered.filter((a) => riskBadge(a) === 'At Risk').length
  const renewalsIn90d = filtered.filter((a) => {
    const days = renewalDaysLeft(a)
    return days !== null && days >= 0 && days <= 90
  }).length
  const avgHealth = filtered.length > 0
    ? Math.round(filtered.reduce((sum, account) => sum + account.health.score, 0) / filtered.length)
    : 0

  const focusAccount = [...filtered].sort((a, b) => {
    const p = priorityRank(a) - priorityRank(b)
    if (p !== 0) return p
    const ra = renewalDaysLeft(a)
    const rb = renewalDaysLeft(b)
    if (ra === null && rb === null) return 0
    if (ra === null) return 1
    if (rb === null) return -1
    return ra - rb
  })[0] ?? null
  const trackingEvents = focusAccount ? buildTrackingEvents(focusAccount) : []

  return (
    <div className="accounts-page accounts-overview-page">
      <div className="accounts-layout">
        <section className="accounts-main-column">
          <div className="accounts-header">
            <div className="accounts-title">Account-Übersicht</div>
          </div>

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

          <div className="accounts-metrics-grid">
            <div className="metric-card">
              <div className="metric-label">Accounts</div>
              <div className="metric-value">{filtered.length}</div>
            </div>
            <div className="metric-card">
              <div className="metric-label">Total ARR</div>
              <div className="metric-value">{formatArr(totalArr)}</div>
            </div>
            <div className="metric-card">
              <div className="metric-label">At Risk</div>
              <div className="metric-value">{atRisk}</div>
            </div>
            <div className="metric-card">
              <div className="metric-label">Renewals ≤ 90d</div>
              <div className="metric-value">{renewalsIn90d}</div>
            </div>
            <div className="metric-card">
              <div className="metric-label">Avg Health</div>
              <div className="metric-value">{avgHealth}</div>
            </div>
          </div>

          <div className="accounts-table-wrap">
            {isLoading ? (
              <div className="empty-state">Loading accounts…</div>
            ) : filtered.length === 0 ? (
              <div className="empty-state">No accounts match your search.</div>
            ) : (
              <table className="accounts-table">
                <thead>
                  <tr>
                    <th>Account</th>
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
                    const renewalDate = getRenewalDate(account)
                    const daysLeft = renewalDaysLeft(account)
                    const trend = healthTrend(account)
                    const badge = riskBadge(account)

                    return (
                      <tr
                        key={account.entity.id}
                        className="accounts-row"
                        onClick={() => navigate(`/accounts/${encodeURIComponent(account.entity.id)}`)}
                      >
                        <td>
                          <div className="accounts-name">{account.entity.canonical_name}</div>
                          <span className="segment-chip">{segment}</span>
                        </td>
                        <td className="col-right accounts-arr">{formatArr(arr)}</td>
                        <td className="col-center">
                          <span className={`health-score-badge ${account.health.tier}`}>
                            {account.health.score}
                          </span>
                          <span style={{ marginLeft: 4, fontSize: 12, color: TREND_COLOR[trend] }}>
                            {TREND_ARROW[trend]}
                          </span>
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
        </section>

        <aside className="accounts-right-column">
          <div className="activity-panel">
            <div className="activity-panel-title">Detaillierter Aktivitätsverlauf</div>
            <div className="activity-panel-subtitle">
              {focusAccount ? focusAccount.entity.canonical_name : 'Kein Account ausgewählt'}
            </div>
            {trackingEvents.length === 0 ? (
              <div className="empty-state" style={{ height: 180 }}>Keine Verlaufsschritte vorhanden.</div>
            ) : (
              <div className="tracking-timeline">
                {trackingEvents.map((event, i) => (
                  <div key={event.id} className={`tracking-item ${event.status}`}>
                    <div className="tracking-rail">
                      <span className={`tracking-dot ${event.status}`} />
                      {i < trackingEvents.length - 1 && <span className="tracking-line" />}
                    </div>
                    <div className="tracking-body">
                      <div className="tracking-time">{formatTrackingTime(event.timestamp)}</div>
                      <div className="tracking-title">{event.title}</div>
                      <div className="tracking-station">{event.station}</div>
                      <div className="tracking-detail">{event.detail}</div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </aside>
      </div>
    </div>
  )
}
