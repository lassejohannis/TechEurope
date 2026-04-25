import { useParams } from 'react-router-dom'
import { useAccount } from '@/hooks/useAccount'
import HealthScore from './HealthScore'
import Timeline from './Timeline'
import MeetingBrief from './MeetingBrief'

export default function AccountPage() {
  const { accountId } = useParams<{ accountId: string }>()
  const { data: account, isLoading, error } = useAccount(accountId ?? null)

  if (isLoading) {
    return (
      <div className="account-page">
        <div className="account-main">
          <div className="empty-state">Loading account…</div>
        </div>
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

  const industrAttr = account.entity.attributes['industry']
  const regionAttr = account.entity.attributes['region']
  const industryStr = typeof industrAttr === 'string' ? industrAttr : ''
  const regionStr = typeof regionAttr === 'string' ? regionAttr : ''

  return (
    <div className="account-page">
      {/* Main column */}
      <div className="account-main">
        <div className="account-header">
          <div className="account-avatar">{initials}</div>
          <div className="account-name">{account.entity.canonical_name}</div>
          <div className="account-meta">
            {[industryStr, regionStr].filter(Boolean).join(' · ')}
            {account.entity.aliases.length > 0 && (
              <span style={{ marginLeft: 8, opacity: 0.6 }}>
                aka {account.entity.aliases[0]}
              </span>
            )}
          </div>
        </div>

        <HealthScore health={account.health} />

        <div
          style={{
            marginBottom: 12,
          }}
        >
          <div className="panel-eyebrow" style={{ marginBottom: 16 }}>
            Meeting Brief
          </div>
          <MeetingBrief account={account} />
        </div>

        <div>
          <div className="panel-eyebrow" style={{ marginBottom: 16 }}>
            Activity Timeline
          </div>
          <Timeline
            communications={account.recent_communications}
            tickets={account.open_tickets}
          />
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

              return (
                <div key={entity.id} className="contact-row">
                  <div className="contact-avatar">{contactInitials}</div>
                  <div>
                    <div className="contact-name">{entity.canonical_name}</div>
                    <div className="contact-role">{role}</div>
                  </div>
                </div>
              )
            })}
          </div>
        )}

        {account.open_tickets.length > 0 && (
          <div className="sidebar-section">
            <div className="sidebar-title">
              Open Tickets ({account.open_tickets.length})
            </div>
            {account.open_tickets.map((ticket) => (
              <div key={ticket.id} className="ticket-row">
                <span className="ticket-id">{ticket.external_id}</span>
                <span className="ticket-title">{ticket.title}</span>
                <span className={`ticket-status ${ticket.status}`}>
                  {ticket.status.replace('_', ' ')}
                </span>
              </div>
            ))}
          </div>
        )}

        {account.open_tickets.length === 0 && (
          <div className="sidebar-section">
            <div className="sidebar-title">Open Tickets</div>
            <div style={{ fontSize: 12, color: 'var(--text-tertiary)' }}>No open tickets</div>
          </div>
        )}

        <div className="sidebar-section">
          <div className="sidebar-title">Account Facts</div>
          {account.facts.slice(0, 6).map((fact) => (
            <div
              key={fact.id}
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                padding: '6px 0',
                borderBottom: '1px solid var(--border-hair)',
                fontSize: 12,
              }}
            >
              <span style={{ color: 'var(--text-tertiary)' }}>
                {fact.predicate.replace(/_/g, ' ')}
              </span>
              <span
                style={{
                  color: fact.status === 'disputed' ? 'var(--conf-conflict)' : 'var(--text-primary)',
                  fontWeight: 600,
                  maxWidth: '55%',
                  textAlign: 'right',
                  wordBreak: 'break-word',
                }}
              >
                {String(fact.object)}
                {fact.status === 'disputed' && ' ⚠'}
              </span>
            </div>
          ))}
        </div>
      </aside>
    </div>
  )
}
