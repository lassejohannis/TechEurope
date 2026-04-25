import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { motion, AnimatePresence } from 'motion/react'
import {
  Mail, AlertTriangle, Check,
  TrendingDown, RefreshCw, Users, Ticket, TrendingUp, Zap,
} from 'lucide-react'
import type { BriefingItem, SignalType } from '@/types'
import { useUiStore } from '@/store/ui'

const SIGNAL_ICONS: Record<SignalType, React.ReactNode> = {
  sentiment_drop:    <TrendingDown size={15} />,
  renewal_risk:      <RefreshCw size={15} />,
  stakeholder_change:<Users size={15} />,
  ticket_spike:      <Ticket size={15} />,
  engagement_gap:    <Zap size={15} />,
  upsell_signal:     <TrendingUp size={15} />,
}

interface TaskCardProps {
  item: BriefingItem
  onSendEmail?: () => void
  onEscalate?: () => void
}

export default function TaskCard({ item, onSendEmail, onEscalate }: TaskCardProps) {
  const navigate = useNavigate()
  const markHandled = useUiStore((s) => s.markHandled)
  const handledItems = useUiStore((s) => s.handledItems)
  const [exiting, setExiting] = useState(false)

  const isHandled = handledItems.has(item.id)

  function handleCardClick(e: React.MouseEvent) {
    if ((e.target as HTMLElement).closest('.priority-icon-btn')) return
    navigate(`/accounts/${encodeURIComponent(item.account_id)}`)
  }

  function handleMarkHandled(e: React.MouseEvent) {
    e.stopPropagation()
    setExiting(true)
    setTimeout(() => markHandled(item.id), 280)
  }

  return (
    <AnimatePresence>
      {!isHandled && !exiting && (
        <motion.div
          layout
          initial={{ opacity: 0, y: 6 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, x: -20, height: 0, marginBottom: 0, paddingTop: 0, paddingBottom: 0 }}
          transition={{ duration: 0.25, ease: [0.16, 1, 0.3, 1] }}
          className={`task-card ${item.priority}`}
          onClick={handleCardClick}
          role="button"
          tabIndex={0}
          onKeyDown={(e) => {
            if (e.key === 'Enter') navigate(`/accounts/${encodeURIComponent(item.account_id)}`)
          }}
        >
          <div className={`signal-icon-wrap ${item.priority}`}>
            {SIGNAL_ICONS[item.signal_type]}
          </div>

          <div className="priority-card-center">
            <div className="task-meta">
              <span className="priority-account">{item.account_name}</span>
              <span className="segment-chip">{item.segment}</span>
            </div>
            <div className="task-revenue">{item.revenue_impact}</div>
            <div className="task-reason">{item.headline}</div>
            <div className="task-next-action">
              <span className="task-next-action-label">Next: </span>
              {item.recommended_action}
            </div>
          </div>

          <div className="priority-actions">
            {onSendEmail && (
              <button
                className="priority-icon-btn email"
                onClick={(e) => { e.stopPropagation(); onSendEmail() }}
                title="Send recovery email"
                aria-label="Send recovery email"
              >
                <Mail size={13} />
              </button>
            )}
            {onEscalate && (
              <button
                className="priority-icon-btn escalate"
                onClick={(e) => { e.stopPropagation(); onEscalate() }}
                title="Escalate to account team"
                aria-label="Escalate to account team"
              >
                <AlertTriangle size={13} />
              </button>
            )}
            <button
              className="priority-icon-btn handled"
              onClick={handleMarkHandled}
              title="Mark as handled"
              aria-label="Mark as handled"
            >
              <Check size={13} />
            </button>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}
