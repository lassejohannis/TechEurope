import { Mail, MessageSquare, Ticket, Database } from 'lucide-react'
import type { Communication, Fact, Ticket as TicketType } from '@/types'
import SentimentChip from '@/components/common/SentimentChip'

interface TimelineProps {
  communications: Communication[]
  tickets: TicketType[]
  facts?: Fact[]
}

type TimelineEntry =
  | { kind: 'communication'; date: string; item: Communication }
  | { kind: 'ticket'; date: string; item: TicketType }
  | { kind: 'fact'; date: string; item: Fact }

function relativeDate(iso: string): string {
  if (!iso) return ''
  const diff = Date.now() - new Date(iso).getTime()
  const days = Math.floor(diff / 86_400_000)
  if (days === 0) return 'Today'
  if (days === 1) return 'Yesterday'
  if (days < 7) return `${days}d ago`
  if (days < 30) return `${Math.floor(days / 7)}w ago`
  if (days < 365) return `${Math.floor(days / 30)}mo ago`
  return `${Math.floor(days / 365)}y ago`
}

function formatFactLabel(predicate: string): string {
  return predicate.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())
}

function formatFactValue(fact: Fact): string {
  const val = fact.object
  if (val === null || val === undefined) return '—'
  if (typeof val === 'number') {
    if (fact.predicate.includes('revenue') || fact.predicate.includes('arr')) {
      return val >= 1000 ? `€${Math.round(val / 1000)}k` : `€${val}`
    }
  }
  return String(val)
}

export default function Timeline({ communications, tickets, facts = [] }: TimelineProps) {
  const entries: TimelineEntry[] = [
    ...communications.map((c): TimelineEntry => ({ kind: 'communication', date: c.date, item: c })),
    ...tickets.map((t): TimelineEntry => ({ kind: 'ticket', date: t.updated_at, item: t })),
    ...facts
      .filter((f) => f.status === 'live' && f.created_at)
      .map((f): TimelineEntry => ({ kind: 'fact', date: f.created_at, item: f })),
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

        if (entry.kind === 'ticket') {
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
        }

        const fact = entry.item
        const label = formatFactLabel(fact.predicate)
        const value = formatFactValue(fact)
        const conf = Math.round(fact.confidence * 100)
        return (
          <div key={fact.id} className="timeline-row">
            <span className="timeline-src-icon" style={{ background: 'var(--surface-hover)', color: 'var(--text-tertiary)' }} title="Fact indexed">
              <Database size={12} />
            </span>
            <span className="timeline-row-title">
              <span style={{ color: 'var(--text-secondary)' }}>{label}:</span>{' '}
              <strong>{value}</strong>
            </span>
            <span style={{ fontSize: 11, color: conf >= 70 ? 'var(--conf-high)' : conf >= 40 ? '#B08000' : 'var(--conf-conflict)', marginLeft: 'auto' }}>
              {conf}% conf
            </span>
            <div className="timeline-row-right">
              <span className="timeline-reldate">{relativeDate(fact.created_at)}</span>
            </div>
          </div>
        )
      })}
    </div>
  )
}
