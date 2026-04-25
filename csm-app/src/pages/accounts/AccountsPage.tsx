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

export default function AccountsPage() {
  const navigate = useNavigate()
  const { data: accounts, isLoading } = useAccounts()
  const [query, setQuery] = useState('')

  const filtered = (accounts ?? []).filter((a) =>
    a.entity.canonical_name.toLowerCase().includes(query.toLowerCase())
  )

  return (
    <div className="accounts-page">
      <div className="accounts-header">
        <div className="accounts-title">Accounts</div>
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
  )
}
