import { useNavigate } from 'react-router-dom'
import { ArrowRight } from 'lucide-react'
import type { BriefingItem } from '@/types'

interface PriorityCardProps {
  item: BriefingItem
}

export default function PriorityCard({ item }: PriorityCardProps) {
  const navigate = useNavigate()

  function handleClick() {
    navigate(`/accounts/${encodeURIComponent(item.account_id)}`)
  }

  return (
    <div
      className={`priority-card ${item.priority}`}
      onClick={handleClick}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') handleClick() }}
    >
      <div className={`priority-dot ${item.priority}`} />

      <div className="priority-card-body">
        <div className="row" style={{ marginBottom: 6 }}>
          <div className="priority-account">{item.account_name}</div>
          <span className={`signal-chip ${item.signal_type}`}>
            {item.signal_type.replace(/_/g, ' ')}
          </span>
        </div>

        <div className="priority-headline">{item.headline}</div>
        <div className="priority-detail">{item.detail}</div>

        <div className="priority-action">
          <ArrowRight size={11} />
          {item.recommended_action}
        </div>
      </div>
    </div>
  )
}
