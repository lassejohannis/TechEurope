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
    <div
      style={{
        background: 'white',
        borderRadius: 12,
        border: '1px solid #e5e5e5',
        padding: '14px 18px',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
        <KeyRound size={14} style={{ color: '#6366f1' }} />
        <h2 style={{ fontSize: 13, fontWeight: 600, margin: 0, letterSpacing: 0.2 }}>
          STEP 1 — AGENT TOKEN
        </h2>
      </div>

      {!token ? (
        <div style={{ display: 'flex', alignItems: 'flex-end', gap: 12, flexWrap: 'wrap' }}>
          <div style={{ flex: '1 1 220px', minWidth: 0 }}>
            <label style={{ display: 'block', fontSize: 11, color: '#6b7280', marginBottom: 3 }}>
              Name
            </label>
            <Input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="my-claude-desktop"
              style={{ height: 34 }}
            />
          </div>

          <div>
            <label style={{ display: 'block', fontSize: 11, color: '#6b7280', marginBottom: 3 }}>
              Scopes
            </label>
            <div style={{ display: 'flex', gap: 6 }}>
              {ALL_SCOPES.map((s) => {
                const active = scopes.includes(s)
                return (
                  <button
                    key={s}
                    type="button"
                    onClick={() => toggleScope(s)}
                    style={{
                      padding: '6px 12px',
                      height: 34,
                      borderRadius: 999,
                      border: active ? '1.5px solid #6366f1' : '1px solid #e5e5e5',
                      background: active ? '#eef2ff' : 'white',
                      color: active ? '#4338ca' : '#374151',
                      fontSize: 12.5,
                      fontWeight: active ? 600 : 500,
                      cursor: 'pointer',
                    }}
                  >
                    {s}
                  </button>
                )
              })}
            </div>
          </div>

          <Button onClick={handleIssue} disabled={loading || scopes.length === 0}>
            {loading && <Loader2 size={14} className="animate-spin" style={{ marginRight: 6 }} />}
            Generate token
          </Button>
        </div>
      ) : (
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 8,
              padding: '6px 12px',
              borderRadius: 999,
              background: '#f3f4f6',
              border: '1px solid #e5e7eb',
              fontSize: 12.5,
              fontFamily: 'ui-monospace, SFMono-Regular, Menlo, monospace',
              minWidth: 0,
              flex: '1 1 auto',
              overflow: 'hidden',
            }}
          >
            <span style={{ fontWeight: 600, color: '#111827' }}>{token.name}</span>
            <span style={{ color: '#9ca3af' }}>·</span>
            <span style={{ color: '#6b7280' }}>{token.scopes.join(', ')}</span>
            <span style={{ color: '#9ca3af' }}>·</span>
            <span
              style={{
                color: '#374151',
                whiteSpace: 'nowrap',
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                minWidth: 0,
              }}
            >
              {token.token}
            </span>
          </div>

          <Button size="sm" variant="outline" onClick={handleCopy}>
            {copied ? <Check size={13} /> : <Copy size={13} />}
            <span style={{ marginLeft: 4 }}>{copied ? 'Copied' : 'Copy'}</span>
          </Button>
          <Button size="sm" variant="outline" onClick={() => onIssued(null)}>
            <RotateCcw size={13} />
            <span style={{ marginLeft: 4 }}>Re-issue</span>
          </Button>
        </div>
      )}

      <p
        style={{
          marginTop: 8,
          marginBottom: 0,
          fontSize: 11.5,
          color: token ? '#dc2626' : '#9ca3af',
          display: 'flex',
          alignItems: 'center',
          gap: 5,
        }}
      >
        {token && <AlertTriangle size={11} />}
        {token
          ? 'Save this token now — it will not be shown again. Page reload clears it.'
          : 'Bearer credentials. Stored hashed on the server, returned plain only once.'}
      </p>

      {error && (
        <p style={{ marginTop: 6, color: '#dc2626', fontSize: 12 }}>Error: {error}</p>
      )}
    </div>
  )
}
