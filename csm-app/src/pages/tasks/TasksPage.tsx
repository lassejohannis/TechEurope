import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Building2, Mail, AlertTriangle, Save } from 'lucide-react'
import { useBriefing } from '@/hooks/useBriefing'
import { useUiStore } from '@/store/ui'
import TaskCard from '@/components/common/TaskCard'
import RecoveryEmailModal from '@/components/cta/RecoveryEmailModal'
import EscalationModal from '@/components/cta/EscalationModal'
import type { BriefingItem } from '@/types'

type FilterKey = 'all' | 'impact-sorted' | 'at-risk' | 'renewals' | 'low-engagement'

const FILTERS: { key: FilterKey; label: string }[] = [
  { key: 'all',            label: 'All' },
  { key: 'impact-sorted',  label: 'Impact (high → low)' },
  { key: 'at-risk',        label: 'At Risk' },
  { key: 'renewals',       label: 'Renewals (next 90d)' },
  { key: 'low-engagement', label: 'Low Engagement' },
]

const PRIORITY_ORDER = { red: 0, yellow: 1, green: 2 } as const

function sortByImpact(items: BriefingItem[]): BriefingItem[] {
  return [...items].sort((a, b) => {
    if (b.revenue_impact_eur !== a.revenue_impact_eur) {
      return b.revenue_impact_eur - a.revenue_impact_eur
    }
    return PRIORITY_ORDER[a.priority] - PRIORITY_ORDER[b.priority]
  })
}

function sortByPriority(items: BriefingItem[]): BriefingItem[] {
  return [...items].sort((a, b) => {
    const p = PRIORITY_ORDER[a.priority] - PRIORITY_ORDER[b.priority]
    if (p !== 0) return p
    return b.revenue_impact_eur - a.revenue_impact_eur
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
  return items
}

function formatDate(d: Date): string {
  return d.toLocaleDateString('en-GB', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' })
}

export default function TasksPage() {
  const navigate = useNavigate()
  const { data: briefing, isLoading, error } = useBriefing()
  const handledItems = useUiStore((s) => s.handledItems)
  const taskNotes = useUiStore((s) => s.taskNotes)
  const setTaskNote = useUiStore((s) => s.setTaskNote)
  const addToast = useUiStore((s) => s.addToast)
  const [activeFilter, setActiveFilter] = useState<FilterKey>('all')
  const [recoveryTarget, setRecoveryTarget] = useState<string | null>(null)
  const [escalationTarget, setEscalationTarget] = useState<{ id: string; name: string } | null>(null)
  const [selectedTaskId, setSelectedTaskId] = useState<string | null>(null)
  const [draftNote, setDraftNote] = useState('')

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
  const baseSorted = activeFilter === 'impact-sorted' ? sortByImpact(visible) : sortByPriority(visible)
  const filtered = applyFilter(baseSorted, activeFilter)
  const selectedTask = selectedTaskId ? (filtered.find((i) => i.id === selectedTaskId) ?? null) : null

  function openTaskDetail(taskId: string) {
    const item = filtered.find((t) => t.id === taskId)
    setSelectedTaskId(taskId)
    setDraftNote(item ? (taskNotes[item.id] ?? '') : '')
  }

  function saveNote() {
    if (!selectedTask) return
    setTaskNote(selectedTask.id, draftNote.trim())
    addToast('Task note saved', 'success')
  }

  return (
    <div className="tasks-layout">
      <div className="tasks-page">
        <div className="tasks-header">
          <div className="tasks-title">Tasks</div>
          <div className="tasks-date">{formatDate(new Date())}</div>
        </div>

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
                onOpenDetail={openTaskDetail}
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
      </div>

      <aside className="tasks-sidebar">
        {!selectedTask ? (
          <div className="empty-state" style={{ height: 180 }}>Klicke auf eine Task für Details.</div>
        ) : (
          <div className="task-detail">
            <div className="panel-eyebrow" style={{ marginBottom: 10 }}>Task Detail</div>
            <div className="task-detail-title">{selectedTask.headline}</div>
            <div className="task-detail-account">{selectedTask.account_name}</div>

            <div className="task-detail-chip-row">
              <span className={`risk-badge ${selectedTask.priority === 'red' ? 'at-risk' : selectedTask.priority === 'yellow' ? 'renewing' : 'healthy'}`}>
                {selectedTask.priority.toUpperCase()}
              </span>
              <span className="segment-chip">{selectedTask.segment}</span>
            </div>

            <div className="task-detail-block">
              <div className="task-detail-label">Impact</div>
              <div className="task-detail-value">{selectedTask.revenue_impact}</div>
            </div>

            <div className="task-detail-block">
              <div className="task-detail-label">Recommended Action</div>
              <div className="task-detail-text">{selectedTask.recommended_action}</div>
            </div>

            <div className="task-detail-block">
              <div className="task-detail-label">Note</div>
              <textarea
                className="task-note-input"
                placeholder="Write a note for this task..."
                value={draftNote}
                onChange={(e) => setDraftNote(e.target.value)}
              />
              <button className="btn-cta-primary task-note-save" onClick={saveNote}>
                <Save size={13} /> Save Note
              </button>
            </div>

            <div className="task-detail-actions">
              <button
                className="btn-cta-secondary"
                onClick={() => navigate(`/accounts/${encodeURIComponent(selectedTask.account_id)}`)}
              >
                <Building2 size={13} /> Open Account
              </button>
              {(selectedTask.signal_type === 'sentiment_drop' ||
                selectedTask.signal_type === 'renewal_risk' ||
                selectedTask.signal_type === 'engagement_gap') && (
                <button className="btn-cta-secondary" onClick={() => setRecoveryTarget(selectedTask.account_id)}>
                  <Mail size={13} /> Recovery Email
                </button>
              )}
              {selectedTask.priority === 'red' && (
                <button
                  className="btn-cta-secondary btn-cta-danger"
                  onClick={() => setEscalationTarget({ id: selectedTask.account_id, name: selectedTask.account_name })}
                >
                  <AlertTriangle size={13} /> Escalate
                </button>
              )}
            </div>
          </div>
        )}
      </aside>

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
