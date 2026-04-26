import { useState } from 'react'
import { AlertTriangle, Check, Copy, KeyRound, Loader2, RotateCcw } from 'lucide-react'
import { issueAgentToken, type IssuedToken, ApiError } from '@/lib/api'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'

const ALL_SCOPES = ['read', 'write', 'admin'] as const

type Props = {
  token: IssuedToken | null
  onIssued: (t: IssuedToken | null) => void
}

export default function TokenBar({ token, onIssued }: Props) {
  const [name, setName] = useState('my-agent')
  const [scopes, setScopes] = useState<string[]>(['read'])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [copied, setCopied] = useState(false)

  async function handleIssue() {
    setLoading(true)
    setError(null)
    try {
      const issued = await issueAgentToken(name.trim() || 'my-agent', scopes)
      onIssued(issued)
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e))
    } finally {
      setLoading(false)
    }
  }

  function toggleScope(s: string) {
    setScopes((prev) => (prev.includes(s) ? prev.filter((x) => x !== s) : [...prev, s]))
  }

  async function handleCopy() {
    if (!token) return
    try {
      await navigator.clipboard.writeText(token.token)
      setCopied(true)
      setTimeout(() => setCopied(false), 1800)
    } catch {
      /* noop */
    }
  }

  return (
    <div className="rounded-lg border bg-background p-3 flex flex-col gap-2">
      <div className="flex items-center gap-2">
        <KeyRound size={13} className="text-indigo-500 shrink-0" />
        <span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Step 1 — Agent Token</span>
      </div>

      {!token ? (
        <div className="flex flex-wrap items-end gap-3">
          <div className="flex flex-col gap-1 min-w-0 flex-1" style={{ flexBasis: 200 }}>
            <label className="text-xs text-muted-foreground">Name</label>
            <Input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="my-claude-desktop"
              className="h-8 text-sm"
            />
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-xs text-muted-foreground">Scopes</label>
            <div className="flex gap-1.5">
              {ALL_SCOPES.map((s) => {
                const active = scopes.includes(s)
                return (
                  <button
                    key={s}
                    type="button"
                    onClick={() => toggleScope(s)}
                    className={[
                      'h-8 px-3 rounded-full text-xs font-medium border transition-colors',
                      active
                        ? 'border-indigo-400 bg-indigo-50 text-indigo-700'
                        : 'border-border bg-background text-foreground hover:bg-muted',
                    ].join(' ')}
                  >
                    {s}
                  </button>
                )
              })}
            </div>
          </div>
          <Button size="sm" onClick={handleIssue} disabled={loading || scopes.length === 0}>
            {loading && <Loader2 size={13} className="animate-spin mr-1" />}
            Generate token
          </Button>
        </div>
      ) : (
        <div className="flex flex-wrap items-center gap-2">
          <div className="flex items-center gap-2 rounded-full bg-muted px-3 py-1.5 text-xs font-mono flex-1 min-w-0 overflow-hidden border">
            <span className="font-semibold text-foreground shrink-0">{token.name}</span>
            <span className="text-muted-foreground shrink-0">·</span>
            <span className="text-muted-foreground shrink-0">{token.scopes.join(', ')}</span>
            <span className="text-muted-foreground shrink-0">·</span>
            <span className="truncate text-foreground">{token.token}</span>
          </div>
          <Button size="sm" variant="outline" onClick={handleCopy}>
            {copied ? <Check size={13} /> : <Copy size={13} />}
            <span className="ml-1">{copied ? 'Copied' : 'Copy'}</span>
          </Button>
          <Button size="sm" variant="outline" onClick={() => onIssued(null)}>
            <RotateCcw size={13} />
            <span className="ml-1">Re-issue</span>
          </Button>
        </div>
      )}

      {token && (
        <p className="flex items-center gap-1 text-xs text-destructive">
          <AlertTriangle size={11} />
          Save this token now — it will not be shown again.
        </p>
      )}
      {error && <p className="text-xs text-destructive">Error: {error}</p>}
    </div>
  )
}
