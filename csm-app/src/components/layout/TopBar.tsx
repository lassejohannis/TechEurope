import { NavLink } from 'react-router-dom'
import { LayoutDashboard, Building2 } from 'lucide-react'
import { useAccounts } from '@/hooks/useAccounts'

export default function TopBar() {
  const { data: accounts } = useAccounts()

  return (
    <header className="topbar">
      <div className="brand-mark">Q</div>
      <span className="brand-name">Qontext</span>
      <span className="brand-sub">CSM</span>

      <div className="topbar-divider" />

      <nav className="topnav">
        <NavLink
          to="/briefing"
          className={({ isActive }) => `topnav-tab${isActive ? ' active' : ''}`}
        >
          <LayoutDashboard size={13} />
          Daily Briefing
        </NavLink>

        {accounts?.map((account) => (
          <NavLink
            key={account.id}
            to={`/accounts/${encodeURIComponent(account.id)}`}
            className={({ isActive }) => `topnav-tab${isActive ? ' active' : ''}`}
          >
            <Building2 size={13} />
            {account.name}
          </NavLink>
        ))}
      </nav>

      <div className="topbar-spacer" />

      <div className="topbar-chip">
        <span style={{ fontSize: 10, color: 'var(--conf-high)' }}>●</span>
        Live
      </div>

      <div className="user-chip">AK</div>
    </header>
  )
}
