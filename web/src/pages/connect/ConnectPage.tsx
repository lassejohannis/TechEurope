import { useCallback, useState } from 'react'
import { Plug, Sparkles, Wrench, MessageSquare } from 'lucide-react'
import type { IssuedToken } from '@/lib/api'
import { Badge } from '@/components/ui/badge'
import type { VibeAgent } from './connectors'
import TokenBar from './TokenBar'
import VibeCodeTrack from './VibeCodeTrack'
import ManualTrack from './ManualTrack'

const API_BASE_FALLBACK = 'http://localhost:8000'
const TOKEN_PLACEHOLDER = '<paste your token here>'

type TrackId = 'vibe' | 'manual'

export default function ConnectPage() {
  const [token, setToken] = useState<IssuedToken | null>(null)
  const [track, setTrack] = useState<TrackId>('vibe')
  const [vibeAgentId, setVibeAgentId] = useState<VibeAgent['id']>('claude-code')

  const apiBaseUrl =
    (typeof window !== 'undefined' ? window.location.origin : '') || API_BASE_FALLBACK

  const substitute = useCallback(
    (s: string) =>
      s
        .replaceAll('{{TOKEN}}', token?.token ?? TOKEN_PLACEHOLDER)
        .replaceAll('{{API_BASE_URL}}', apiBaseUrl),
    [token, apiBaseUrl],
  )

  return (
    <div
      style={{
        height: '100%',
        flex: 1,
        minWidth: 0,
        overflowY: 'scroll',
        overflowX: 'hidden',
        scrollbarGutter: 'stable',
        background: '#f5f5f7',
        padding: '36px 48px',
        boxSizing: 'border-box',
      }}
    >
      <div style={{ maxWidth: 1100, margin: '0 auto', minWidth: 0, width: '100%' }}>
        {/* Hero */}
        <header style={{ marginBottom: 24 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 6 }}>
            <Plug size={22} style={{ color: '#6366f1' }} />
            <h1 style={{ fontSize: 30, fontWeight: 700, margin: 0, letterSpacing: -0.4 }}>
              Connect your agent
            </h1>
          </div>
          <p style={{ color: '#6b7280', fontSize: 15, margin: '4px 0 12px 32px', maxWidth: 640 }}>
            Two ways: hand the integration to your AI agent, or wire it up yourself with snippets.
            Either way — under a minute.
          </p>
          <div style={{ display: 'flex', gap: 6, marginLeft: 32, flexWrap: 'wrap' }}>
            <Badge variant="secondary">
              <Sparkles size={12} style={{ marginRight: 4 }} />
              MCP server live at /mcp/sse
            </Badge>
            <Badge variant="secondary">5 MCP tools</Badge>
            <Badge variant="secondary">50+ REST endpoints</Badge>
            <Badge variant="secondary">3 IDE-agent flows</Badge>
          </div>
        </header>

        {/* Token bar */}
        <div style={{ marginBottom: 22 }}>
          <TokenBar token={token} onIssued={setToken} />
        </div>

        {/* Track tabs */}
        <div
          style={{
            display: 'flex',
            gap: 0,
            marginBottom: 0,
            borderBottom: '1px solid #e5e5e5',
            paddingLeft: 4,
          }}
        >
          <TrackTab
            id="vibe"
            label="Let an AI agent do it"
            icon={<MessageSquare size={14} />}
            active={track === 'vibe'}
            onSelect={() => setTrack('vibe')}
          />
          <TrackTab
            id="manual"
            label="Wire it up manually"
            icon={<Wrench size={14} />}
            active={track === 'manual'}
            onSelect={() => setTrack('manual')}
          />
        </div>

        {/* Track body */}
        <div
          style={{
            paddingTop: 22,
            minWidth: 0,
            // Stable height so switching tracks doesn't reflow the page.
            minHeight: 760,
          }}
        >
          {track === 'vibe' ? (
            <VibeCodeTrack
              apiBaseUrl={apiBaseUrl}
              token={token?.token ?? null}
              selectedAgentId={vibeAgentId}
              onSelectAgent={setVibeAgentId}
            />
          ) : (
            <ManualTrack token={token?.token ?? null} substitute={substitute} />
          )}
        </div>
      </div>
    </div>
  )
}

function TrackTab({
  id,
  label,
  icon,
  active,
  onSelect,
}: {
  id: TrackId
  label: string
  icon: React.ReactNode
  active: boolean
  onSelect: () => void
}) {
  return (
    <button
      type="button"
      onClick={onSelect}
      aria-selected={active}
      style={{
        background: 'transparent',
        border: 'none',
        padding: '10px 18px',
        marginBottom: -1,
        cursor: 'pointer',
        fontSize: 14,
        fontWeight: active ? 600 : 500,
        color: active ? '#4338ca' : '#6b7280',
        borderBottom: active ? '2px solid #6366f1' : '2px solid transparent',
        display: 'inline-flex',
        alignItems: 'center',
        gap: 6,
      }}
      data-track={id}
    >
      {icon}
      {label}
    </button>
  )
}
