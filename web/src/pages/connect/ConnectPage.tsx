import { useCallback, useState, type ReactNode } from 'react'
import { Plug, Wrench, Cpu } from 'lucide-react'
import type { IssuedToken } from '@/lib/api'
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
    <div className="flex h-full flex-col overflow-auto">
      {/* Header */}
      <div className="flex items-center gap-2 border-b px-4 py-3">
        <Plug size={15} className="text-indigo-500 shrink-0" />
        <h1 className="text-sm font-semibold">Connect your agent</h1>
      </div>

      <div className="flex flex-col gap-4 p-4 w-full">
        {/* Token */}
        <TokenBar token={token} onIssued={setToken} />

        {/* Track tabs */}
        <div className="flex border-b">
          <TrackTab
            id="vibe"
            label="Let an AI agent do it"
            icon={<Cpu size={13} />}
            active={track === 'vibe'}
            onSelect={() => setTrack('vibe')}
          />
          <TrackTab
            id="manual"
            label="Wire it up manually"
            icon={<Wrench size={13} />}
            active={track === 'manual'}
            onSelect={() => setTrack('manual')}
          />
        </div>

        {/* Track body */}
        <div>
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
  icon: ReactNode
  active: boolean
  onSelect: () => void
}) {
  return (
    <button
      type="button"
      onClick={onSelect}
      data-track={id}
      className={[
        'inline-flex items-center gap-1.5 px-4 py-2 text-sm font-medium -mb-px border-b-2 transition-colors',
        active
          ? 'border-indigo-500 text-indigo-600'
          : 'border-transparent text-muted-foreground hover:text-foreground',
      ].join(' ')}
    >
      {icon}
      {label}
    </button>
  )
}
