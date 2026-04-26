import type { AccountCard } from '@/types'

export function segmentLabel(subscriptionTier: string): 'Enterprise' | 'Mid-Market' | 'SMB' {
  if (subscriptionTier === 'Enterprise') return 'Enterprise'
  if (subscriptionTier === 'Growth') return 'Mid-Market'
  return 'SMB'
}

export function riskBadge(account: AccountCard): 'At Risk' | 'Renewing' | 'Healthy' | 'Expansion' {
  if (account.health.tier === 'red') return 'At Risk'
  const hasExpansion = account.facts.some(
    (f) => f.predicate === 'expansion_seats_requested' || f.predicate === 'expansion_interest'
  )
  if (account.health.tier === 'green' && hasExpansion) return 'Expansion'
  if (account.health.tier === 'yellow') return 'Renewing'
  return 'Healthy'
}

export function renewalDaysLeft(account: AccountCard): number | null {
  const fact = account.facts.find((f) => f.predicate === 'renewal_date')
  if (!fact || typeof fact.object !== 'string') return null
  return Math.ceil((new Date(fact.object).getTime() - Date.now()) / 86_400_000)
}

// Returns the ISO date of the most recent communication involving this contact
export function lastContactDate(account: AccountCard, contactEmail: string): string | null {
  const match = account.recent_communications
    .filter((c) => c.from_address === contactEmail || c.to_addresses.includes(contactEmail))
    .sort((a, b) => new Date(b.date).getTime() - new Date(a.date).getTime())
  return match[0]?.date ?? null
}

// Pure functions over API response data — no hardcoded thresholds beyond the
// spec-defined rules. These run client-side so the UI can show/hide CTAs.

const SEVEN_DAYS_MS = 7 * 24 * 60 * 60 * 1000
const THIRTY_DAYS_MS = 30 * 24 * 60 * 60 * 1000

export function shouldShowRecoveryEmail(account: AccountCard): boolean {
  if (account.health.score < 60) return true

  const hasOldHighTicket = account.open_tickets.some(
    (t) => t.priority === 'high' && Date.now() - new Date(t.created_at).getTime() > SEVEN_DAYS_MS
  )
  if (hasOldHighTicket) return true

  const cutoff = new Date(Date.now() - THIRTY_DAYS_MS)
  const recentNegative = account.recent_communications.filter(
    (c) => c.sentiment?.sentiment_label === 'negative' && new Date(c.date) > cutoff
  )
  return recentNegative.length >= 2
}

export function shouldShowEscalation(account: AccountCard): boolean {
  if (account.health.score < 50) return true

  const hasHighOpenTicket = account.open_tickets.some(
    (t) => t.priority === 'high' && t.status !== 'resolved' && t.status !== 'closed'
  )
  const hasNegativeSentiment = account.recent_communications.some(
    (c) => (c.sentiment?.sentiment_score ?? 0) < -0.3
  )
  const criticals = [hasHighOpenTicket, hasNegativeSentiment, account.stakeholder_change_detected].filter(Boolean).length
  return criticals >= 2
}

export function primaryContactId(account: AccountCard): string {
  return account.key_contacts[0]?.entity.id ?? ''
}

export function primaryContactEmail(account: AccountCard): string {
  const email = account.key_contacts[0]?.entity.attributes['email']
  return typeof email === 'string' ? email : ''
}
