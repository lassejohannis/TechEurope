import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { Mail, AlertTriangle, UserPlus } from 'lucide-react'
import { useAccount } from '@/hooks/useAccount'
import { shouldShowRecoveryEmail, shouldShowEscalation, primaryContactId } from '@/lib/signals'
import HealthScore from './HealthScore'
import MeetingBrief from './MeetingBrief'
import RecoveryEmailModal from '@/components/cta/RecoveryEmailModal'
import StakeholderIntroModal from '@/components/cta/StakeholderIntroModal'
import EscalationModal from '@/components/cta/EscalationModal'
import type { AccountCard } from '@/types'

type ActiveModal = 'recovery-email' | 'stakeholder-intro' | 'escalation' | null
type TrackingStatus = 'done' | 'current' | 'upcoming'

interface TrackingEvent {
  id: string
  timestamp: string
  station: string
  title: string
  detail: string
  status: TrackingStatus
}

function asValidDate(iso: string | null | undefined): Date | null {
  if (!iso) return null
  const d = new Date(iso)
  return Number.isNaN(d.getTime()) ? null : d
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

function renewalDate(account: AccountCard): Date | null {
  const fact = account.facts.find((f) => f.predicate === 'renewal_date')
  if (typeof fact?.object === 'string') return asValidDate(fact.object)
  return asValidDate(account.entity.attributes['renewal_date'] as string | undefined)
}

function buildTrackingEvents(account: AccountCard): TrackingEvent[] {
  const now = new Date()
  const renewal = renewalDate(account)
  const updated = asValidDate(account.entity.updated_at) ?? new Date(now.getTime() - 60 * 60 * 1000)
  const created = asValidDate(account.entity.created_at) ?? new Date(now.getTime() - 14 * 24 * 60 * 60 * 1000)

  const events: TrackingEvent[] = [
    {
      id: `${account.entity.id}:health`,
      timestamp: updated.toISOString(),
      station: 'Health Engine',
      title: `Status aktualisiert: ${account.executive_summary.status_label}`,
      detail: account.executive_summary.why,
      status: 'current',
    },
    {
      id: `${account.entity.id}:action`,
      timestamp: new Date(updated.getTime() - 2 * 60 * 60 * 1000).toISOString(),
      station: 'CSM Action Queue',
      title: 'Nächster Schritt eingeplant',
      detail: account.executive_summary.next_action,
      status: 'done',
    },
    {
      id: `${account.entity.id}:onboard`,
      timestamp: created.toISOString(),
      station: 'Context Ingestion',
      title: 'Account im Core Layer angelegt',
      detail: `Entity ${account.entity.type} mit ${account.facts.length} Facts`,
      status: 'done',
    },
  ]

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

  return events.sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime())
}

export default function AccountPage() {
  const { accountId } = useParams<{ accountId: string }>()
  const { data: account, isLoading, error } = useAccount(accountId ?? null)
  const [activeModal, setActiveModal] = useState<ActiveModal>(null)
  const [stakeholderTarget, setStakeholderTarget] = useState<{ id: string; name: string } | null>(null)

  if (isLoading) {
    return (
      <div className="account-page">
        <div className="account-main"><div className="empty-state">Loading account…</div></div>
      </div>
    )
  }

  if (error || !account) {
    return (
      <div className="account-page">
        <div className="account-main">
          <div className="empty-state">
            {error instanceof Error ? error.message : 'Account not found.'}
          </div>
        </div>
      </div>
    )
  }

  const initials = account.entity.canonical_name
    .split(' ')
    .map((w) => w[0])
    .join('')
    .slice(0, 2)
    .toUpperCase()

  const industryAttr = account.entity.attributes['industry']
  const regionAttr = account.entity.attributes['region']
  const industryStr = typeof industryAttr === 'string' ? industryAttr : ''
  const regionStr = typeof regionAttr === 'string' ? regionAttr : ''

  const showRecovery = shouldShowRecoveryEmail(account)
  const showEscalation = shouldShowEscalation(account)
  const primaryId = primaryContactId(account)
  const trackingEvents = buildTrackingEvents(account)

  function openStakeholderIntro(contactId: string, contactName: string) {
    setStakeholderTarget({ id: contactId, name: contactName })
    setActiveModal('stakeholder-intro')
  }

  return (
    <div className="account-page">
      <div className="account-main">
        {/* Header */}
        <div className="account-header">
          <div className="account-avatar">{initials}</div>
          <div style={{ flex: 1 }}>
            <div className="account-name">{account.entity.canonical_name}</div>
            <div className="account-meta">
              {[industryStr, regionStr].filter(Boolean).join(' · ')}
              {account.entity.aliases.length > 0 && (
                <span style={{ marginLeft: 8, opacity: 0.6 }}>aka {account.entity.aliases[0]}</span>
              )}
            </div>
          </div>
        </div>

        {/* CTA bar — visibility driven purely by API data via signals.ts */}
        {(showRecovery || showEscalation) && (
          <div className="cta-bar">
            {showRecovery && (
              <button className="btn-cta-primary" onClick={() => setActiveModal('recovery-email')}>
                <Mail size={13} /> Send Recovery Email
              </button>
            )}
            {showEscalation && (
              <button className="btn-cta-secondary btn-cta-danger" onClick={() => setActiveModal('escalation')}>
                <AlertTriangle size={13} /> Escalate to Account Team
              </button>
            )}
          </div>
        )}

        <HealthScore health={account.health} />

        <div style={{ marginBottom: 12 }}>
          <div className="panel-eyebrow" style={{ marginBottom: 16 }}>Meeting Brief</div>
          <MeetingBrief account={account} />
        </div>
      </div>

      {/* Sidebar */}
      <aside className="account-sidebar">
        {account.key_contacts.length > 0 && (
          <div className="sidebar-section">
            <div className="sidebar-title">Key Contacts</div>
            {account.key_contacts.map(({ entity, role }) => {
              const contactInitials = entity.canonical_name
                .split(' ')
                .map((w) => w[0])
                .join('')
                .slice(0, 2)
                .toUpperCase()

              const isNew = account.stakeholder_change_detected &&
                account.new_stakeholders.some((s) => s.name === entity.canonical_name)

              return (
                <div key={entity.id} className="contact-row">
                  <div className="contact-avatar">{contactInitials}</div>
                  <div style={{ flex: 1 }}>
                    <div className="contact-name">
                      {entity.canonical_name}
                      {isNew && (
                        <span className="new-stakeholder-badge">New</span>
                      )}
                    </div>
                    <div className="contact-role">{role}</div>
                  </div>
                  {isNew && (
                    <button
                      className="card-action-btn quick-email-btn"
                      onClick={() => openStakeholderIntro(entity.id, entity.canonical_name)}
                      title="Send intro email"
                    >
                      <UserPlus size={11} /> Intro
                    </button>
                  )}
                </div>
              )
            })}
          </div>
        )}

        <div className="sidebar-section">
          <div className="sidebar-title">Quick Facts</div>
          <div className="quick-facts">
            {(['arr', 'renewal_date', 'tier'] as const).map((key) => {
              const fact = account.facts.find((f) => f.predicate.toLowerCase() === key)
              if (!fact) return null
              return (
                <div key={key} className="fact-chip-row">
                  <span className="fact-chip-label">{fact.predicate.replace(/_/g, ' ')}</span>
                  <span className={`fact-chip-value${fact.status === 'disputed' ? ' disputed' : ''}`}>
                    {String(fact.object)}{fact.status === 'disputed' && ' ⚠'}
                  </span>
                </div>
              )
            })}
          </div>
        </div>

        <div className="sidebar-section">
          <div className="sidebar-title">Detaillierter Aktivitätsverlauf</div>
          {trackingEvents.length === 0 ? (
            <div className="empty-state" style={{ height: 160 }}>Keine Verlaufsschritte vorhanden.</div>
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

      {/* Modals */}
      {activeModal === 'recovery-email' && accountId && (
        <RecoveryEmailModal
          accountId={decodeURIComponent(accountId)}
          onClose={() => setActiveModal(null)}
        />
      )}
      {activeModal === 'stakeholder-intro' && accountId && stakeholderTarget && (
        <StakeholderIntroModal
          accountId={decodeURIComponent(accountId)}
          contactId={stakeholderTarget.id}
          contactName={stakeholderTarget.name}
          onClose={() => { setActiveModal(null); setStakeholderTarget(null) }}
        />
      )}
      {activeModal === 'escalation' && accountId && (
        <EscalationModal
          accountId={decodeURIComponent(accountId)}
          accountName={account.entity.canonical_name}
          onClose={() => setActiveModal(null)}
        />
      )}

      {/* CTA 2 for accounts without stakeholder change — primaryContactId used as fallback */}
      {account.stakeholder_change_detected && activeModal === null && primaryId && (
        <div style={{ display: 'none' }} aria-hidden>
          {/* stakeholder-intro trigger is in sidebar contact rows above */}
        </div>
      )}
    </div>
  )
}
