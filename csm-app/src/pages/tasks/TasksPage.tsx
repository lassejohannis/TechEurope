import { useState } from 'react'
import { useBriefing } from '@/hooks/useBriefing'
import { useUiStore } from '@/store/ui'
import TaskCard from '@/components/common/TaskCard'
import TaskDetailSidebar from '@/components/common/TaskDetailSidebar'
import RecoveryEmailModal from '@/components/cta/RecoveryEmailModal'
import EscalationModal from '@/components/cta/EscalationModal'
import type { BriefingItem } from '@/types'

type FilterKey = 'all' | 'at-risk' | 'renewals' | 'low-engagement' | 'high-impact'

const FILTERS: { key: FilterKey; label: string }[] = [
  { key: 'all',           label: 'All' },
  { key: 'at-risk',       label: 'At Risk' },
  { key: 'renewals',      label: 'Renewals (next 90d)' },
  { key: 'low-engagement',label: 'Low Engagement' },
  { key: 'high-impact',   label: 'High Impact' },
]

const PRIORITY_ORDER = { red: 0, yellow: 1, green: 2 } as const

function sortTasks(items: BriefingItem[]): BriefingItem[] {
  return [...items].sort((a, b) => {
    if (b.revenue_impact_eur !== a.revenue_impact_eur) return b.revenue_impact_eur - a.revenue_impact_eur
    return PRIORITY_ORDER[a.priority] - PRIORITY_ORDER[b.priority]
  })
}

function applyFilter(items: BriefingItem[], filter: FilterKey): BriefingItem[] {
  if (filter === 'all') return items
  if (filter === 'at-risk') return items.filter((i) => i.priority === 'red')
  if (filter === 'renewals') {
    return items.filter((i) => {
      if (!i.renewal_date) return false
      const daysLeft = Math.ceil((new Date(i.renewal_date).getTime() - Date.now()) / 86_400_000)
      return daysLeft >= 0 && daysLeft <= 90
    })
  }
  if (filter === 'low-engagement') return items.filter((i) => i.signal_type === 'engagement_gap')
  if (filter === 'high-impact') {
    const sorted = sortTasks(items)
    const threshold = sorted.length > 0 ? sorted[Math.min(4, sorted.length - 1)].revenue_impact_eur : 0
    return sorted.filter((i) => i.revenue_impact_eur >= threshold && i.revenue_impact_eur > 0)
  }
  return items
}

function formatDate(d: Date): string {
  return d.toLocaleDateString('en-GB', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' })
}

export default function TasksPage() {
  const { data: briefing, isLoading, error } = useBriefing()
  const handledItems = useUiStore((s) => s.handledItems)
  const markHandled = useUiStore((s) => s.markHandled)
  const [activeFilter, setActiveFilter] = useState<FilterKey>('all')
  const [selectedTask, setSelectedTask] = useState<BriefingItem | null>(null)
  const [recoveryTarget, setRecoveryTarget] = useState<string | null>(null)
  const [escalationTarget, setEscalationTarget] = useState<{ id: string; name: string } | null>(null)

  if (isLoading) {
    return (
      <div className="tasks-page">
        <div className="empty-state">Loading tasks…</div>
      </div>
    )
  }

  if (error || !briefing) {
    return (
      <div className="tasks-page">
        <div className="empty-state">Failed to load tasks. Please try again.</div>
      </div>
    )
  }

  const visible = briefing.items.filter((i) => !handledItems.has(i.id))
  const filtered = applyFilter(sortTasks(visible), activeFilter)

  function closeSidebar() {
    setSelectedTask(null)
  }

  function handleMarkHandled(id: string) {
    markHandled(id)
    setSelectedTask(null)
  }

  return (
    <div className="tasks-page">
      <div className="tasks-header">
        <div className="tasks-title">Tasks</div>
        <div className="tasks-date">{formatDate(new Date())}</div>
      </div>

      <div className="tasks-controls">
        <div className="filter-pills">
          {FILTERS.map((f) => (
            <button
              key={f.key}
              className={`filter-pill${activeFilter === f.key ? ' active' : ''}`}
              onClick={() => setActiveFilter(f.key)}
            >
              {f.label}
            </button>
          ))}
        </div>
        <div className="tasks-sort-indicator">
          Impact ↓
        </div>
      </div>

      {filtered.length === 0 ? (
        <div className="empty-state" style={{ height: 240, flexDirection: 'column', gap: 8 }}>
          <span style={{ fontSize: 22 }}>✓</span>
          <span style={{ fontWeight: 600, color: 'var(--text-primary)' }}>
            {activeFilter === 'all' ? 'All caught up' : 'Nothing here'}
          </span>
          <span>
            {activeFilter === 'all'
              ? 'Next proactive check in 4 hours.'
              : 'Try a different filter or check back later.'}
          </span>
        </div>
      ) : (
        <div className="task-feed">
          {filtered.map((item) => (
            <TaskCard
              key={item.id}
              item={item}
              onSelect={() => setSelectedTask(item)}
              onSendEmail={
                item.signal_type === 'sentiment_drop' ||
                item.signal_type === 'renewal_risk' ||
                item.signal_type === 'engagement_gap'
                  ? () => setRecoveryTarget(item.account_id)
                  : undefined
              }
              onEscalate={
                item.priority === 'red'
                  ? () => setEscalationTarget({ id: item.account_id, name: item.account_name })
                  : undefined
              }
            />
          ))}
        </div>
      )}

      <TaskDetailSidebar
        item={selectedTask}
        onClose={closeSidebar}
        onSendEmail={
          selectedTask &&
          (selectedTask.signal_type === 'sentiment_drop' ||
            selectedTask.signal_type === 'renewal_risk' ||
            selectedTask.signal_type === 'engagement_gap')
            ? () => {
                setRecoveryTarget(selectedTask.account_id)
                closeSidebar()
              }
            : undefined
        }
        onEscalate={
          selectedTask?.priority === 'red'
            ? () => {
                setEscalationTarget({ id: selectedTask.account_id, name: selectedTask.account_name })
                closeSidebar()
              }
            : undefined
        }
        onMarkHandled={selectedTask ? () => handleMarkHandled(selectedTask.id) : undefined}
      />

      {recoveryTarget !== null && (
        <RecoveryEmailModal accountId={recoveryTarget} onClose={() => setRecoveryTarget(null)} />
      )}
      {escalationTarget !== null && (
        <EscalationModal
          accountId={escalationTarget.id}
          accountName={escalationTarget.name}
          onClose={() => setEscalationTarget(null)}
        />
      )}
    </div>
  )
}
