import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { motion, AnimatePresence } from 'motion/react'
import {
  X, ExternalLink, Mail, AlertTriangle, Check,
  TrendingDown, RefreshCw, Users, Ticket, TrendingUp, Zap,
} from 'lucide-react'
import type { BriefingItem, SignalType } from '@/types'
import { useUiStore } from '@/store/ui'

const SIGNAL_ICONS: Record<SignalType, React.ReactNode> = {
  sentiment_drop:     <TrendingDown size={16} />,
  renewal_risk:       <RefreshCw size={16} />,
  stakeholder_change: <Users size={16} />,
  ticket_spike:       <Ticket size={16} />,
  engagement_gap:     <Zap size={16} />,
  upsell_signal:      <TrendingUp size={16} />,
}

const SIGNAL_LABELS: Record<SignalType, string> = {
  sentiment_drop:     'Sentiment Drop',
  renewal_risk:       'Renewal Risk',
  stakeholder_change: 'Stakeholder Change',
  ticket_spike:       'Ticket Spike',
  engagement_gap:     'Engagement Gap',
  upsell_signal:      'Upsell Signal',
}

interface Props {
  item: BriefingItem | null
  onClose: () => void
  onSendEmail?: () => void
  onEscalate?: () => void
  onMarkHandled?: () => void
}

export default function TaskDetailSidebar({ item, onClose, onSendEmail, onEscalate, onMarkHandled }: Props) {
  const navigate = useNavigate()
  const taskNotes = useUiStore((s) => s.taskNotes)
  const setTaskNote = useUiStore((s) => s.setTaskNote)
  const [noteText, setNoteText] = useState('')
  const [noteSaved, setNoteSaved] = useState(false)

  const itemId = item?.id
  useEffect(() => {
    if (itemId) {
      setNoteText(taskNotes[itemId] ?? '')
      setNoteSaved(false)
    }
  }, [itemId]) // taskNotes intentionally excluded — only sync on task switch

  function saveNote() {
    if (!item) return
    setTaskNote(item.id, noteText)
    setNoteSaved(true)
    setTimeout(() => setNoteSaved(false), 2000)
  }

  return (
    <AnimatePresence>
      {item && (
        <>
          <motion.div
            key="backdrop"
            className="tds-backdrop"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.18 }}
            onClick={onClose}
          />
          <motion.aside
            key="panel"
            className="task-detail-sidebar"
            initial={{ x: '100%' }}
            animate={{ x: 0 }}
            exit={{ x: '100%' }}
            transition={{ type: 'spring', stiffness: 300, damping: 30 }}
          >
            {/* ── Header ─────────────────────────────── */}
            <div className="tds-header">
              <div className={`signal-icon-wrap ${item.priority}`}>
                {SIGNAL_ICONS[item.signal_type]}
              </div>
              <div className="tds-title">
                <span className="tds-account">{item.account_name}</span>
                <span className="segment-chip">{item.segment}</span>
              </div>
              <button className="tds-close" onClick={onClose} aria-label="Close">
                <X size={15} />
              </button>
            </div>

            {/* ── Signal + priority row ───────────────── */}
            <div className="tds-signal-row">
              <span className={`tds-priority-dot ${item.priority}`} />
              <span className="tds-signal-label">{SIGNAL_LABELS[item.signal_type]}</span>
              <span className={`tds-priority-badge ${item.priority}`}>
                {item.priority.toUpperCase()}
              </span>
            </div>

            {/* ── Revenue ────────────────────────────── */}
            <div className="tds-revenue">{item.revenue_impact}</div>

            {/* ── Signal detail ──────────────────────── */}
            <div className="tds-section">
              <div className="tds-section-label">Signal</div>
              <div className="tds-headline">{item.headline}</div>
              {item.detail && <div className="tds-detail">{item.detail}</div>}
            </div>

            {/* ── Recommended action ─────────────────── */}
            <div className="tds-section">
              <div className="tds-section-label">Recommended Action</div>
              <div className="tds-action-text">{item.recommended_action}</div>
            </div>

            {/* ── CTAs ───────────────────────────────── */}
            <div className="tds-ctas">
              {onSendEmail && (
                <button className="tds-cta email" onClick={onSendEmail}>
                  <Mail size={12} /> Send Recovery Email
                </button>
              )}
              {onEscalate && (
                <button className="tds-cta escalate" onClick={onEscalate}>
                  <AlertTriangle size={12} /> Escalate to Team
                </button>
              )}
              {onMarkHandled && (
                <button className="tds-cta handled" onClick={onMarkHandled}>
                  <Check size={12} /> Mark Handled
                </button>
              )}
            </div>

            {/* ── Note ───────────────────────────────── */}
            <div className="tds-section tds-note-section">
              <div className="tds-section-label">Note</div>
              <textarea
                className="tds-note-textarea"
                placeholder="Add a note for this task…"
                value={noteText}
                onChange={(e) => { setNoteText(e.target.value); setNoteSaved(false) }}
                rows={4}
              />
              <button
                className={`tds-note-save${noteSaved ? ' saved' : ''}`}
                onClick={saveNote}
              >
                {noteSaved ? '✓ Saved' : 'Save note'}
              </button>
            </div>

            {/* ── Footer ─────────────────────────────── */}
            <div className="tds-footer">
              <button
                className="tds-view-account"
                onClick={() => {
                  navigate(`/accounts/${encodeURIComponent(item.account_id)}`)
                  onClose()
                }}
              >
                <ExternalLink size={12} /> View Account
              </button>
            </div>
          </motion.aside>
        </>
      )}
    </AnimatePresence>
  )
}
