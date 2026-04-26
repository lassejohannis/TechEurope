import { useEffect, useMemo, useRef, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { searchMemory } from '@/lib/api'
import type { SearchResultItem } from '@/types'
import {
  cascadeFilter,
  getConnectionCount,
  getTicketCount,
  parseInterpretation,
} from '../search/searchLogic'
import VfsTree from './VfsTree'
import EntityDetail from './EntityDetail'
import ActionPanel from './ActionPanel'

// ── Chat types ───────────────────────────────────────────────────────────────

interface AssistantPayload {
  text: string
  steps: string[]
  matches: SearchResultItem[]
}
interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  payload?: AssistantPayload
}

function buildPayload(query: string, results: SearchResultItem[]): AssistantPayload {
  const intent = parseInterpretation(query)
  const { filtered, steps } = cascadeFilter(results, intent)
  if (filtered.length === 0) {
    return { text: 'Nichts Passendes gefunden. Versuche andere Suchbegriffe.', steps, matches: [] }
  }
  const top = filtered.slice(0, 6)
  return { text: `${top.length} Treffer gefunden:`, steps, matches: top }
}

const NAME_STOP_WORDS = new Set([
  'wo', 'ist', 'wer', 'zeig', 'zeige', 'mir', 'find', 'finde', 'suche',
  'where', 'is', 'show', 'me', 'der', 'die', 'das', 'den', 'in', 'zu',
  'the', 'a', 'an', 'and', 'oder', 'und',
])
const EMAIL_PATTERN = /[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}/i

function normalizeEmail(raw: string): string {
  return raw
    .trim()
    .replace(/^mailto:/i, '')
    .replace(/[)>.,;:!?]+$/g, '')
    .toLowerCase()
}

function extractEmailFromQuery(query: string): string | null {
  const match = query.match(EMAIL_PATTERN)
  if (!match?.[0]) return null
  return normalizeEmail(match[0])
}

function textContainsEmail(value: unknown, email: string): boolean {
  if (value == null) return false
  if (typeof value === 'string') return normalizeEmail(value) === email
  if (typeof value === 'number' || typeof value === 'boolean') return false
  if (Array.isArray(value)) return value.some((v) => textContainsEmail(v, email))
  if (typeof value === 'object') return Object.values(value as Record<string, unknown>).some((v) => textContainsEmail(v, email))
  return false
}

function entityMatchesEmail(result: SearchResultItem, email: string): boolean {
  const entity = result.entity
  if (normalizeEmail(entity.canonical_name) === email) return true
  if (entity.aliases.some((alias) => normalizeEmail(alias) === email)) return true
  if (textContainsEmail(entity.attrs, email)) return true

  return entity.facts.some((fact) => {
    const predicate = String(fact.predicate ?? '').toLowerCase()
    if (!predicate.includes('email')) return false
    const literal = typeof fact.object_literal === 'string' ? normalizeEmail(fact.object_literal) : null
    const objectId = typeof fact.object_id === 'string' ? normalizeEmail(fact.object_id) : null
    return literal === email || objectId === email
  })
}

function findEmailMatch(query: string, results: SearchResultItem[]): SearchResultItem | null {
  const email = extractEmailFromQuery(query)
  if (!email) return null

  return results.find((r) => String(r.entity.entity_type).toLowerCase() === 'person' && entityMatchesEmail(r, email))
    ?? results.find((r) => entityMatchesEmail(r, email))
    ?? null
}

function findNameMatch(query: string, results: SearchResultItem[]): SearchResultItem | null {
  const tokens = query.toLowerCase()
    .replace(/[?!.,;:]/g, '')
    .split(/\s+/)
    .filter(t => t.length > 1 && !NAME_STOP_WORDS.has(t))
  if (tokens.length === 0 || tokens.length > 4) return null

  const matches = (r: SearchResultItem) => {
    const name = r.entity.canonical_name.toLowerCase()
    return tokens.every(t => name.includes(t))
  }
  return results.find(r => r.entity.entity_type === 'person' && matches(r))
    ?? results.find(r => matches(r))
    ?? null
}

// ── Resizable chat panel ─────────────────────────────────────────────────────

const MIN_H = 74   // handle + input bar, without empty bottom strip
const MAX_H = 480

function BrowseChat() {
  const navigate = useNavigate()
  const [messages, setMessages] = useState<ChatMessage[]>([
    { id: 'init', role: 'assistant', content: 'Frag mich etwas — z. B. "Wo ist Anna Müller?" oder "Senior Engineers mit Tickets".' },
  ])
  const [input, setInput] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [chatHeight, setChatHeight] = useState(MIN_H)
  const endRef = useRef<HTMLDivElement>(null)

  const showMessages = chatHeight > MIN_H + 10

  useEffect(() => {
    if (showMessages) endRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, showMessages])

  const canSend = useMemo(() => input.trim().length > 0 && !isLoading, [input, isLoading])

  // Drag-to-resize handle
  function startResize(e: React.MouseEvent) {
    e.preventDefault()
    const startY = e.clientY
    const startH = chatHeight

    function onMove(ev: MouseEvent) {
      const delta = startY - ev.clientY
      setChatHeight(Math.max(MIN_H, Math.min(MAX_H, startH + delta)))
    }
    function onUp() {
      document.removeEventListener('mousemove', onMove)
      document.removeEventListener('mouseup', onUp)
    }
    document.addEventListener('mousemove', onMove)
    document.addEventListener('mouseup', onUp)
  }

  async function handleSend() {
    const query = input.trim()
    if (!canSend || !query) return
    const intent = parseInterpretation(query)
    const needsWider = Boolean(
      intent.titleTerms.length > 0 || intent.ticketConstraint ||
      intent.connectionConstraint || intent.wantsConnections,
    )
    setMessages(prev => [...prev, { id: `u-${Date.now()}`, role: 'user', content: query }])
    setInput('')
    setIsLoading(true)
    if (!showMessages) setChatHeight(240)

    try {
      const res = await searchMemory({ query, k: needsWider ? 50 : 40 })

      const emailHit = findEmailMatch(query, res.results)
      if (emailHit) {
        navigate(`/browse/${encodeURIComponent(emailHit.entity.id)}`)
        setMessages(prev => [...prev, {
          id: `a-${Date.now()}`, role: 'assistant',
          content: `→ E-Mail „${extractEmailFromQuery(query)}" gefunden bei „${emailHit.entity.canonical_name}" — direkt geöffnet.`,
        }])
        return
      }

      // ── Name-match: find entity whose canonical_name matches all query tokens ──
      const nameHit = findNameMatch(query, res.results)
      if (nameHit) {
        navigate(`/browse/${encodeURIComponent(nameHit.entity.id)}`)
        setMessages(prev => [...prev, {
          id: `a-${Date.now()}`, role: 'assistant',
          content: `→ „${nameHit.entity.canonical_name}" gefunden — direkt geöffnet.`,
        }])
        return
      }

      const payload = buildPayload(query, res.results)

      // ── Unique result → navigate directly, no card list ──
      if (payload.matches.length === 1) {
        const single = payload.matches[0]
        navigate(`/browse/${encodeURIComponent(single.entity.id)}`)
        setMessages(prev => [...prev, {
          id: `a-${Date.now()}`, role: 'assistant',
          content: `→ „${single.entity.canonical_name}" gefunden — direkt geöffnet.`,
        }])
        return
      }

      // ── Multiple results → show list ──
      setMessages(prev => [...prev, { id: `a-${Date.now()}`, role: 'assistant', content: payload.text, payload }])
    } catch (err) {
      setMessages(prev => [...prev, { id: `e-${Date.now()}`, role: 'assistant', content: `Fehler: ${(err as Error).message}` }])
    } finally {
      setIsLoading(false)
    }
  }

  const extraMessages = messages.length - 1

  return (
    <div style={{
      flexShrink: 0, height: chatHeight,
      display: 'flex', flexDirection: 'column',
      borderTop: '1px solid #e5e5e5', background: '#fff', overflow: 'hidden',
    }}>

      {/* ── Drag handle ── */}
      <div
        onMouseDown={startResize}
        style={{
          height: 16, flexShrink: 0, display: 'flex', alignItems: 'center',
          justifyContent: 'center', cursor: 'ns-resize', userSelect: 'none',
        }}
      >
        <div style={{ width: 32, height: 3, borderRadius: 2, background: '#e0e0e0' }} />
      </div>

      {/* ── Message history ── */}
      {showMessages && (
        <div style={{ flex: 1, overflowY: 'auto', padding: '4px 16px 0' }}>
          {messages.map(msg => (
            <div key={msg.id}
              style={{ marginBottom: 8, display: 'flex', justifyContent: msg.role === 'user' ? 'flex-end' : 'flex-start' }}>
              <div style={{
                maxWidth: '88%',
                background: msg.role === 'user' ? '#0a0a0a' : '#f3f3f3',
                color: msg.role === 'user' ? '#fff' : '#0a0a0a',
                borderRadius: 12, padding: '7px 12px',
                fontSize: 13, whiteSpace: 'pre-wrap', lineHeight: 1.45,
              }}>
                {msg.content}
                {msg.payload && msg.payload.matches.length > 1 && (
                  <div style={{ marginTop: 8, display: 'flex', flexDirection: 'column', gap: 4 }}>
                    {msg.payload.matches.map(match => (
                      <button
                        key={match.entity.id}
                        onClick={() => navigate(`/browse/${encodeURIComponent(match.entity.id)}`)}
                        style={{
                          background: '#fff', border: '1px solid #e5e5e5', borderRadius: 8,
                          padding: '6px 10px', textAlign: 'left', cursor: 'pointer',
                        }}
                        onMouseEnter={e => (e.currentTarget.style.background = '#f7f7f7')}
                        onMouseLeave={e => (e.currentTarget.style.background = '#fff')}
                      >
                        <p style={{ fontWeight: 600, color: '#0a0a0a', fontSize: 12.5, marginBottom: 1 }}>
                          {match.entity.canonical_name}
                        </p>
                        <p style={{ color: '#aaa', fontSize: 11 }}>
                          {String(match.entity.entity_type)}
                          {' · '}Score {(match.score * 100).toFixed(0)}
                          {' · '}{getConnectionCount(match.entity)} Connections
                          {' · '}{getTicketCount(match.entity)} Tickets
                        </p>
                      </button>
                    ))}
                  </div>
                )}
              </div>
            </div>
          ))}
          {isLoading && (
            <div style={{ marginBottom: 8 }}>
              <div style={{ display: 'inline-block', background: '#f3f3f3', borderRadius: 12, padding: '7px 12px', fontSize: 13, color: '#aaa' }}>
                Thinking…
              </div>
            </div>
          )}
          <div ref={endRef} />
        </div>
      )}

      {/* ── Input bar ── */}
      <div style={{ padding: '6px 14px 10px', flexShrink: 0 }}>
        <div style={{
          display: 'flex', alignItems: 'center', gap: 8,
          background: '#f7f7f7', border: '1px solid #e5e5e5',
          borderRadius: 22, padding: '7px 8px 7px 14px',
        }}>
          {extraMessages > 0 && (
            <button
              onClick={() => setChatHeight(h => h <= MIN_H + 10 ? 240 : MIN_H)}
              style={{
                background: showMessages ? '#0a0a0a' : '#ebebeb',
                color: showMessages ? '#fff' : '#888',
                border: 'none', borderRadius: 10, padding: '2px 8px',
                fontSize: 11, fontWeight: 600, cursor: 'pointer', flexShrink: 0,
              }}
            >
              {showMessages ? '▾' : '▴'} {extraMessages}
            </button>
          )}
          <input
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={e => { if (e.key === 'Enter') { e.preventDefault(); void handleSend() } }}
            placeholder='z. B. "Wo ist Anna Müller?" oder "Senior Engineers mit Tickets"'
            style={{ flex: 1, background: 'transparent', border: 'none', outline: 'none', fontSize: 13, color: '#0a0a0a' }}
          />
          <button
            onClick={() => void handleSend()}
            disabled={!canSend}
            style={{
              width: 30, height: 30, borderRadius: '50%', border: 'none', flexShrink: 0,
              background: canSend ? '#0a0a0a' : '#e8e8e8',
              cursor: canSend ? 'pointer' : 'default',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              transition: 'background .15s',
            }}
          >
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none"
              stroke={canSend ? '#fff' : '#bbb'} strokeWidth="2.5"
              strokeLinecap="round" strokeLinejoin="round">
              <line x1="22" y1="2" x2="11" y2="13"/>
              <polygon points="22 2 15 22 11 13 2 9 22 2"/>
            </svg>
          </button>
        </div>
      </div>
    </div>
  )
}

// ── Page ─────────────────────────────────────────────────────────────────────

export default function BrowsePage() {
  const { entityId } = useParams<{ entityId: string }>()
  const navigate = useNavigate()
  const activeId = entityId ? decodeURIComponent(entityId) : null

  return (
    <div style={{ display: 'flex', height: '100%', width: '100%', overflow: 'hidden' }}>

      {/* ── Center: folder/file browser + chat ── */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden', minWidth: 0 }}>
        <VfsTree selectedEntityId={activeId} />
        <BrowseChat />
      </div>

      {/* ── Right: info panel (only when selected) ── */}
      {activeId && (
        <aside style={{
          width: 460, flexShrink: 0,
          borderLeft: '1px solid #e5e5e5', background: '#fff',
          display: 'flex', flexDirection: 'column', overflow: 'hidden',
        }}>
          <div style={{
            height: 52, flexShrink: 0, display: 'flex', alignItems: 'center',
            justifyContent: 'space-between', padding: '0 16px',
            borderBottom: '1px solid #e5e5e5',
          }}>
            <span style={{ fontSize: 11, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em', color: '#ccc' }}>
              Info
            </span>
            <button
              onClick={() => navigate('/browse')}
              style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#ccc', padding: 3, borderRadius: 5 }}
            >
              <svg width="13" height="13" viewBox="0 0 13 13" fill="none">
                <path d="M1.5 1.5l10 10M11.5 1.5l-10 10" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
              </svg>
            </button>
          </div>

          <div style={{ flex: 1, overflowY: 'auto' }}>
            <EntityDetail entityId={activeId} />
            <ActionPanel entityId={activeId} />
          </div>
        </aside>
      )}
    </div>
  )
}
