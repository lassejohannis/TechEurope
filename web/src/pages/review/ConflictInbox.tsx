import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import Icon from '@/components/qontext/icon'
import { SourceBadge } from '@/components/qontext/badges'
import { INAZUMA, type MockConflict } from '@/lib/inazuma-mock'

const SOURCE_MAP: Record<string, [string, string]> = {
  'conf:1': ['src:crm:acme',      'src:email:2'],
  'conf:2': ['src:crm:meridian',  'src:email:3'],
  'conf:3': ['src:hr:E0203',      'src:hr:roster'],
  'conf:4': ['src:crm:northstar', 'src:email:1'],
  'conf:5': ['src:crm:acme',      'src:doc:onepage'],
}

interface Props {
  activeId: string | null
}

function InboxItem({ c, activeId, onClick }: { c: MockConflict; activeId: string | null; onClick: () => void }) {
  const [srcA, srcB] = SOURCE_MAP[c.id] ?? []
  const sources = INAZUMA.sources
  const isActive = c.id === activeId

  return (
    <div
      className={`inbox-item${isActive ? ' active' : ''}${c.unread ? ' unread' : ''}`}
      onClick={onClick}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => e.key === 'Enter' && onClick()}
    >
      <div className="inbox-row1">
        <span className="conf-badge conflict" style={{ padding: '1px 6px' }}>{c.severity}</span>
        <span className="inbox-subject">{c.subject}</span>
        <span className="inbox-time">{c.time}</span>
      </div>
      <div className="inbox-pred">predicate: <span style={{ color: 'var(--text-primary)' }}>{c.pred}</span></div>
      <div className="inbox-sources">
        {srcA && sources[srcA] && <SourceBadge src={sources[srcA]} mini />}
        {srcA && srcB && <span>vs</span>}
        {srcB && sources[srcB] && <SourceBadge src={sources[srcB]} mini />}
        <span style={{ marginLeft: 'auto' }}>2 candidate values</span>
      </div>
    </div>
  )
}

export default function ConflictInbox({ activeId }: Props) {
  const navigate = useNavigate()
  const [filter, setFilter] = useState<'pending' | 'resolved' | 'all'>('pending')
  const conflicts = INAZUMA.conflicts

  return (
    <div className="col">
      <div className="panel-header sticky">
        <Icon name="inbox" size={14} className="muted" />
        <span className="panel-title">Conflicts inbox</span>
        <span className="spacer" />
        <span className="chip" style={{ background: 'var(--conf-conflict-soft)', color: 'var(--conf-conflict)', fontWeight: 700 }}>
          {conflicts.length} pending
        </span>
      </div>

      <div className="inbox-filter">
        {(['pending', 'resolved', 'all'] as const).map((f) => (
          <button key={f} className={filter === f ? 'active' : ''} onClick={() => setFilter(f)}>
            {f.charAt(0).toUpperCase() + f.slice(1)}{' '}
            <span className="count">{f === 'pending' ? conflicts.length : f === 'resolved' ? 312 : 317}</span>
          </button>
        ))}
      </div>

      <div className="inbox-list">
        {conflicts.map((c) => (
          <InboxItem
            key={c.id}
            c={c}
            activeId={activeId}
            onClick={() => navigate(`/review/${encodeURIComponent(c.id)}`)}
          />
        ))}
        <div style={{ padding: '16px 14px', textAlign: 'center', color: 'var(--text-tertiary)', fontSize: 12 }}>
          End of pending queue · auto-resolved 312 conflicts in last 24h
        </div>
      </div>
    </div>
  )
}
