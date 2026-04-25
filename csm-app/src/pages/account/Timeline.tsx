import { Mail, MessageSquare, Ticket } from 'lucide-react'
import type { Communication, Ticket as TicketType } from '@/types'
import SentimentChip from '@/components/common/SentimentChip'

interface TimelineProps {
  communications: Communication[]
  tickets: TicketType[]
}

type TimelineEntry =
  | { kind: 'communication'; date: string; item: Communication }
  | { kind: 'ticket'; date: string; item: TicketType }

function formatDate(iso: string) {
  return new Date(iso).toLocaleDateString('en-GB', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
  })
}

function truncate(text: string, maxLen: number) {
  if (text.length <= maxLen) return text
  return text.slice(0, maxLen) + '…'
}

export default function Timeline({ communications, tickets }: TimelineProps) {
  const entries: TimelineEntry[] = [
    ...communications.map((c): TimelineEntry => ({ kind: 'communication', date: c.date, item: c })),
    ...tickets.map((t): TimelineEntry => ({ kind: 'ticket', date: t.updated_at, item: t })),
  ].sort((a, b) => new Date(b.date).getTime() - new Date(a.date).getTime())

  if (entries.length === 0) {
    return <div className="empty-state">No activity recorded yet.</div>
  }

  return (
    <div className="timeline">
      {entries.map((entry) => {
        if (entry.kind === 'communication') {
          const comm = entry.item
          const dotClass = comm.source_type === 'email' ? 'email' : 'crm'

          return (
            <div key={comm.id} className="timeline-item">
              <div className={`timeline-dot ${dotClass}`}>
                {comm.source_type === 'email' ? (
                  <Mail size={13} />
                ) : (
                  <MessageSquare size={13} />
                )}
              </div>
              <div className="timeline-content">
                <div className="timeline-title">{comm.subject}</div>
                <div className="timeline-snippet">
                  {truncate(comm.body_snippet, 100)}
                </div>
                <div className="timeline-meta">
                  <span>{comm.from_address}</span>
                  <span>{formatDate(comm.date)}</span>
                  {/* Sentiment is read from API data — never computed here */}
                  <SentimentChip sentiment={comm.sentiment} />
                </div>
              </div>
            </div>
          )
        }

        const ticket = entry.item
        return (
          <div key={ticket.id} className="timeline-item">
            <div className="timeline-dot ticket">
              <Ticket size={13} />
            </div>
            <div className="timeline-content">
              <div className="timeline-title">
                <span className="mono" style={{ fontSize: 11, marginRight: 6, color: 'var(--text-tertiary)' }}>
                  {ticket.external_id}
                </span>
                {ticket.title}
              </div>
              <div className="timeline-meta">
                <span className={`ticket-status ${ticket.status}`}>
                  {ticket.status.replace('_', ' ')}
                </span>
                <span>Updated {formatDate(ticket.updated_at)}</span>
                {/* Sentiment is read from API data — never computed here */}
                <SentimentChip sentiment={ticket.sentiment} />
              </div>
            </div>
          </div>
        )
      })}
    </div>
  )
}
