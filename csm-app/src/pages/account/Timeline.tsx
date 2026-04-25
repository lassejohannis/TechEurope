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

function relativeDate(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime()
  const days = Math.floor(diff / 86_400_000)
  if (days === 0) return 'Today'
  if (days === 1) return 'Yesterday'
  if (days < 7) return `${days}d ago`
  if (days < 30) return `${Math.floor(days / 7)}w ago`
  if (days < 365) return `${Math.floor(days / 30)}mo ago`
  return `${Math.floor(days / 365)}y ago`
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
          const srcClass = comm.source_type === 'email' ? 'email' : 'chat'
          const srcLabel = comm.source_type === 'email' ? comm.from_address : `${comm.from_address} (chat)`

          return (
            <div key={comm.id} className="timeline-row">
              <span className={`timeline-src-icon ${srcClass}`} title={srcLabel}>
                {comm.source_type === 'email' ? <Mail size={12} /> : <MessageSquare size={12} />}
              </span>
              <span className="timeline-row-title">{comm.subject}</span>
              {/* Sentiment is read from API data — never computed here */}
              <SentimentChip sentiment={comm.sentiment} />
              <div className="timeline-row-right">
                <span className="timeline-reldate">{relativeDate(comm.date)}</span>
              </div>
            </div>
          )
        }

        const ticket = entry.item
        return (
          <div key={ticket.id} className="timeline-row">
            <span className="timeline-src-icon ticket" title={`${ticket.external_id} · ${ticket.status.replace('_', ' ')}`}>
              <Ticket size={12} />
            </span>
            <span className="timeline-row-title">{ticket.title}</span>
            {/* Sentiment is read from API data — never computed here */}
            <SentimentChip sentiment={ticket.sentiment} />
            <div className="timeline-row-right">
              <span className="timeline-reldate">{relativeDate(ticket.updated_at)}</span>
            </div>
          </div>
        )
      })}
    </div>
  )
}
