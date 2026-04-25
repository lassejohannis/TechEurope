import { useBriefing } from '@/hooks/useBriefing'
import PriorityCard from '@/components/common/PriorityCard'
import type { BriefingItem } from '@/types'

function formatDate(iso: string) {
  return new Date(iso).toLocaleString('en-GB', {
    dateStyle: 'long',
    timeStyle: 'short',
  })
}

export default function BriefingPage() {
  const { data: briefing, isLoading, error } = useBriefing()

  if (isLoading) {
    return (
      <div className="briefing-page">
        <div className="empty-state">Loading briefing…</div>
      </div>
    )
  }

  if (error || !briefing) {
    return (
      <div className="briefing-page">
        <div className="empty-state">Failed to load briefing. Please try again.</div>
      </div>
    )
  }

  const red = briefing.items.filter((i) => i.priority === 'red')
  const yellow = briefing.items.filter((i) => i.priority === 'yellow')
  const green = briefing.items.filter((i) => i.priority === 'green')

  return (
    <div className="briefing-page">
      <div className="briefing-header">
        <div className="briefing-title">Daily Briefing</div>
        <div className="briefing-sub">
          Generated {formatDate(briefing.generated_at)} · {briefing.items.length} items
        </div>
        {briefing.summary && (
          <div
            style={{
              marginTop: 12,
              padding: '12px 14px',
              background: 'var(--surface-panel)',
              border: '1px solid var(--border-hair)',
              borderRadius: 8,
              fontSize: 13,
              color: 'var(--text-secondary)',
              lineHeight: 1.6,
            }}
          >
            {briefing.summary}
          </div>
        )}
      </div>

      {red.length > 0 && (
        <BriefingSection label="Critical" items={red} />
      )}
      {yellow.length > 0 && (
        <BriefingSection label="Attention" items={yellow} />
      )}
      {green.length > 0 && (
        <BriefingSection label="Opportunities" items={green} />
      )}
    </div>
  )
}

function BriefingSection({ label, items }: { label: string; items: BriefingItem[] }) {
  return (
    <div className="briefing-section">
      <div className="section-label">{label}</div>
      {items.map((item) => (
        <PriorityCard key={item.id} item={item} />
      ))}
    </div>
  )
}
