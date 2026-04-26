import { NavLink, useMatch } from 'react-router-dom'
import { CheckSquare, Building2 } from 'lucide-react'
import { useAccount } from '@/hooks/useAccount'

export default function TopBar() {
  const accountMatch = useMatch('/accounts/:accountId')
  const accountId = accountMatch?.params.accountId
    ? decodeURIComponent(accountMatch.params.accountId)
    : null
  const { data: account } = useAccount(accountId)

  return (
    <header className="topbar">
      <NavLink to="/accounts" style={{ textDecoration: 'none', display: 'flex', alignItems: 'center', gap: 6 }}>
        <div className="brand-mark">Q</div>
        <span className="brand-name">Qontext</span>
        <span className="brand-sub">CSM</span>
      </NavLink>

      <div className="topbar-divider" />

      <nav className="topnav">
        <NavLink
          to="/tasks"
          className={({ isActive }) => `topnav-tab${isActive ? ' active' : ''}`}
        >
          <CheckSquare size={13} />
          Tasks
        </NavLink>

        <NavLink
          to="/accounts"
          className={({ isActive }) => `topnav-tab${isActive || accountId !== null ? ' active' : ''}`}
        >
          <Building2 size={13} />
          Accounts
        </NavLink>

        {account && (
          <>
            <span className="topnav-sep">›</span>
            <span className="topnav-context">{account.entity.canonical_name}</span>
          </>
        )}
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
