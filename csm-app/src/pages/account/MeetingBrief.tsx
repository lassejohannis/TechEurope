import type { AccountCard } from '@/types'

interface MeetingBriefProps {
  account: AccountCard
}

export default function MeetingBrief({ account }: MeetingBriefProps) {
  const { facts, open_tickets, recent_communications, health } = account

  // Know before you go — key facts
  const renewalFact = facts.find((f) => f.predicate === 'renewal_date')
  const contractValueFact = facts.find(
    (f) => f.predicate === 'contract_value_eur' || f.predicate === 'annual_recurring_revenue_eur'
  )
  const tierFact = facts.find((f) => f.predicate === 'subscription_tier')
  const disputedFacts = facts.filter((f) => f.status === 'disputed')

  // Talking points — filter by positive sentiment from API data
  // ONLY reads sentiment from API — never derives it
  const positiveCommunications = recent_communications.filter(
    (c) => c.sentiment?.sentiment_label === 'positive'
  )

  return (
    <>
      <div className="brief-card">
        <div className="brief-section-title">Know before you go</div>

        {renewalFact && (
          <div className="brief-item">
            <span className="brief-bullet">·</span>
            <span>
              <strong>Renewal date:</strong>{' '}
              {String(renewalFact.object)}
              {renewalFact.status === 'disputed' && (
                <span style={{ color: 'var(--conf-conflict)', marginLeft: 6, fontSize: 11, fontWeight: 600 }}>
                  ⚠ Disputed
                </span>
              )}
            </span>
          </div>
        )}

        {contractValueFact && (
          <div className="brief-item">
            <span className="brief-bullet">·</span>
            <span>
              <strong>Contract value:</strong>{' '}
              €{Number(contractValueFact.object).toLocaleString('de-DE')}
            </span>
          </div>
        )}

        {tierFact && (
          <div className="brief-item">
            <span className="brief-bullet">·</span>
            <span>
              <strong>Tier:</strong> {String(tierFact.object)}
            </span>
          </div>
        )}

        <div className="brief-item">
          <span className="brief-bullet">·</span>
          <span>
            <strong>Health:</strong> {health.score}/100 —{' '}
            {health.tier === 'red' ? 'At Risk' : health.tier === 'yellow' ? 'Needs Attention' : 'Healthy'}
          </span>
        </div>
      </div>

      {(open_tickets.length > 0 || disputedFacts.length > 0) && (
        <div className="brief-card">
          <div className="brief-section-title">Open items</div>

          {open_tickets.map((ticket) => (
            <div key={ticket.id} className="brief-item">
              <span className="brief-bullet">·</span>
              <span>
                <span className="mono" style={{ color: 'var(--text-tertiary)', marginRight: 6 }}>
                  {ticket.external_id}
                </span>
                {ticket.title}
                <span className={`ticket-status ${ticket.status}`} style={{ marginLeft: 8 }}>
                  {ticket.status.replace('_', ' ')}
                </span>
              </span>
            </div>
          ))}

          {disputedFacts.map((fact) => (
            <div key={fact.id} className="brief-item">
              <span className="brief-bullet">·</span>
              <span style={{ color: 'var(--conf-conflict)' }}>
                <strong>Disputed:</strong> {fact.predicate.replace(/_/g, ' ')} — value{' '}
                {String(fact.object)} is contested
              </span>
            </div>
          ))}
        </div>
      )}

      {positiveCommunications.length > 0 && (
        <div className="brief-card">
          <div className="brief-section-title">Talking points</div>

          {positiveCommunications.map((comm) => (
            <div key={comm.id} className="brief-item">
              <span className="brief-bullet">·</span>
              <span>
                {comm.subject}
                <span style={{ color: 'var(--text-tertiary)', marginLeft: 6, fontSize: 11 }}>
                  — positive signal
                  {comm.sentiment !== null && ` (+${comm.sentiment.sentiment_score.toFixed(2)})`}
                </span>
              </span>
            </div>
          ))}
        </div>
      )}
    </>
  )
}
