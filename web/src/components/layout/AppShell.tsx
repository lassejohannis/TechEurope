import { useState } from 'react'
import { Outlet, NavLink } from 'react-router-dom'
import {
  House,
  Folder,
  Orbit,
  PanelLeftClose,
  PanelLeftOpen,
  EllipsisVertical,
  Plug,
} from 'lucide-react'

const NAV_ITEMS = [
  { to: '/review', label: 'Overview', Icon: House },
  { to: '/browse', label: 'Context vaults', Icon: Folder },
  { to: '/workflow', label: 'Data sources', Icon: Orbit },
  { to: '/connect', label: 'Connect', Icon: Plug },
] as const

export default function AppShell() {
  const [collapsed, setCollapsed] = useState(false)

  return (
    <div style={{ display: 'flex', height: '100vh', overflow: 'hidden', background: '#f5f5f7' }}>

      {/* ── Sidebar ── */}
      <aside style={{
        width: collapsed ? 0 : 310,
        flexShrink: 0,
        display: 'flex',
        flexDirection: 'column',
        borderRight: collapsed ? 'none' : '1px solid #e5e5e5',
        background: '#f8f8fa',
        height: '100%',
        padding: collapsed ? 0 : 22,
        overflow: 'hidden',
        transition: 'width .2s ease, padding .2s ease',
      }}>

        {/* Logo row */}
        <div style={{
          height: 40,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          marginBottom: 20,
          flexShrink: 0,
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <img
              src="/logo-mark.svg"
              alt="The Layer"
              width={28}
              height={28}
              style={{ flexShrink: 0 }}
            />
            <span style={{ fontSize: 15, fontWeight: 700, letterSpacing: '-0.02em', color: '#0a0a0a', whiteSpace: 'nowrap' }}>
              The Layer
            </span>
          </div>
          <button
            type="button"
            onClick={() => setCollapsed(true)}
            style={{
              width: 28, height: 28, borderRadius: 8,
              border: '1px solid #d6d6da', background: '#f8f8fa',
              color: '#666', display: 'flex', alignItems: 'center',
              justifyContent: 'center', cursor: 'pointer', flexShrink: 0,
            }}
          >
            <PanelLeftClose size={15} />
          </button>
        </div>

        {/* Nav */}
        <nav style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {NAV_ITEMS.map(({ to, label, Icon }) => (
            <NavLink key={to} to={to}>
              {({ isActive }) => (
                <div style={{
                  display: 'flex', alignItems: 'center', gap: 12,
                  padding: '12px 14px', borderRadius: 12, fontSize: 33 / 2,
                  background: isActive ? '#e9e9ed' : 'transparent',
                  color: isActive ? '#4f46e5' : '#52525b',
                  fontWeight: isActive ? 500 : 400,
                  cursor: 'pointer', transition: 'background .12s, color .12s',
                  whiteSpace: 'nowrap',
                }}>
                  <Icon size={21} strokeWidth={isActive ? 2.1 : 1.9} />
                  {label}
                </div>
              )}
            </NavLink>
          ))}
        </nav>

        {/* Footer: user row only */}
        <div style={{ marginTop: 'auto', borderTop: '1px solid #e4e4e7', paddingTop: 14 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <div style={{
              width: 40, height: 40, borderRadius: '50%', flexShrink: 0,
              background: 'linear-gradient(135deg, #c7d2fe, #818cf8)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontSize: 13, fontWeight: 700, color: '#3730a3',
            }}>
              NK
            </div>
            <div style={{ minWidth: 0, flex: 1 }}>
              <p style={{
                margin: 0, fontSize: 14, lineHeight: 1.2, color: '#3f3f46',
                fontWeight: 500, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
              }}>
                Nikita Kowalski
              </p>
              <p style={{
                margin: '2px 0 0', fontSize: 12, color: '#71717a',
                whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
              }}>
                nikita.kowalski@qontext.ai
              </p>
            </div>
            <button
              type="button"
              style={{
                width: 28, height: 28, borderRadius: 8, border: 'none',
                background: 'transparent', color: '#6b7280',
                display: 'flex', alignItems: 'center', justifyContent: 'center', cursor: 'pointer',
              }}
            >
              <EllipsisVertical size={17} />
            </button>
          </div>
        </div>
      </aside>

      {/* ── Collapsed toggle strip ── */}
      {collapsed && (
        <div style={{
          width: 48, flexShrink: 0, display: 'flex', flexDirection: 'column',
          alignItems: 'center', paddingTop: 12, gap: 12,
          borderRight: '1px solid #e5e5e5', background: '#f8f8fa',
        }}>
          <button
            type="button"
            onClick={() => setCollapsed(false)}
            style={{
              width: 30, height: 30, borderRadius: 8,
              border: '1px solid #d6d6da', background: '#f8f8fa',
              color: '#666', display: 'flex', alignItems: 'center',
              justifyContent: 'center', cursor: 'pointer',
            }}
          >
            <PanelLeftOpen size={15} />
          </button>
        </div>
      )}

      <main style={{ flex: 1, display: 'flex', overflow: 'hidden' }}>
        <Outlet />
      </main>
    </div>
  )
}
