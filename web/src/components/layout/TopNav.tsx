import { NavLink } from 'react-router-dom'
import Icon from '@/components/qontext/icon'
import { INAZUMA } from '@/lib/inazuma-mock'

const MODES = [
  { to: '/browse', label: 'Browse',  icon: 'folder' as const,  kbd: 'B' },
  { to: '/search', label: 'Search',  icon: 'search' as const,  kbd: 'S' },
  { to: '/review', label: 'Review',  icon: 'review' as const,  kbd: 'R', badge: INAZUMA.conflicts.filter(c => c.unread).length },
]

export default function TopNav() {
  return (
    <div className="topbar">
      <div className="topbar-brand">
        <div className="brand-mark">Q</div>
        <div className="brand-name">Qontext</div>
        <div className="brand-sub">Context Layer</div>
      </div>

      <nav className="topnav">
        {MODES.map(({ to, label, icon, kbd, badge }) => (
          <NavLink key={to} to={to} className={({ isActive }) => `topnav-tab${isActive ? ' active' : ''}`}>
            <Icon name={icon} size={14} />
            {label}
            {badge != null && badge > 0 && (
              <span className="count-pill">{badge}</span>
            )}
            <span className="kbd">{kbd}</span>
          </NavLink>
        ))}
      </nav>

      <div className="topbar-meta">
        <span className="sync-dot">Live · 2 min ago</span>
        <span className="chip outline" style={{ fontSize: 11 }}>192 facts</span>
        <div className="user-chip">AK</div>
      </div>
    </div>
  )
}
