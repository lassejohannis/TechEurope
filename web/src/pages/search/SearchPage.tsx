import { useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { searchMemory } from '@/lib/api'
import type { SearchResultItem } from '@/types'
import {
  cascadeFilter,
  describeResult,
  getConnectionCount,
  getTicketCount,
  parseInterpretation,
} from './searchLogic'

type Role = 'user' | 'assistant'

interface AssistantPayload {
  text: string
  steps: string[]
  matches: SearchResultItem[]
}

interface ChatMessage {
  id: string
  role: Role
  content: string
  payload?: AssistantPayload
}

function buildAssistantPayload(query: string, results: SearchResultItem[]): AssistantPayload {
  const intent = parseInterpretation(query)
  const { filtered, steps } = cascadeFilter(results, intent)

  if (filtered.length === 0) {
    return {
      text: 'Ich habe den Graph/RAG durchsucht, aber für diese Constraints nichts Passendes gefunden. Versuche mehr Kontext oder lockerere Bedingungen.',
      steps,
      matches: [],
    }
  }

  const top = filtered.slice(0, 6)
  const summary = top.map((r) => `• ${describeResult(r.entity)}`).join('\n')

  return {
    text: `Ich habe deine Anfrage kaskadierend über den Graph-RAG ausgewertet.\n\nTop Treffer:\n${summary}`,
    steps,
    matches: top,
  }
}

export default function SearchPage() {
  const navigate = useNavigate()
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: 'init',
      role: 'assistant',
      content:
        'Ask me anything based on the company context.',
    },
  ])
  const [input, setInput] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const endRef = useRef<HTMLDivElement | null>(null)

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, isLoading])

  const canSend = useMemo(() => input.trim().length > 0 && !isLoading, [input, isLoading])

  async function handleSend() {
    const query = input.trim()
    if (!query || isLoading) return
    const intent = parseInterpretation(query)
    const needsBroaderWindow = Boolean(
      intent.titleTerms.length > 0 ||
      intent.ticketConstraint ||
      intent.connectionConstraint ||
      intent.wantsConnections,
    )

    const userMessage: ChatMessage = {
      id: `u-${Date.now()}`,
      role: 'user',
      content: query,
    }

    setMessages((prev) => [...prev, userMessage])
    setInput('')
    setIsLoading(true)

    try {
      const response = await searchMemory({ query, k: needsBroaderWindow ? 120 : 40 })
      const payload = buildAssistantPayload(query, response.results)

      setMessages((prev) => [
        ...prev,
        {
          id: `a-${Date.now()}`,
          role: 'assistant',
          content: payload.text,
          payload,
        },
      ])
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        {
          id: `e-${Date.now()}`,
          role: 'assistant',
          content: `Search-Fehler: ${(err as Error).message}`,
        },
      ])
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div
      className="flex h-full flex-col text-slate-900"
      style={{
        background:
          'radial-gradient(ellipse 90% 60% at 0% 0%, #E8F1FE 0%, transparent 55%), radial-gradient(ellipse 70% 50% at 100% 0%, #FDE8E8 0%, transparent 50%), radial-gradient(ellipse 80% 70% at 50% 100%, #EFE5FE 0%, transparent 55%), #F7F3FB',
      }}
    >
      <header className="flex items-center px-8 py-5">
        <h1 className="text-[28px] font-semibold tracking-tight text-slate-900">Search Assistant</h1>
        <span className="ml-3 inline-flex items-center rounded-full bg-blue-100 px-2.5 py-0.5 text-[11px] font-semibold text-blue-700">
          Graph-RAG
        </span>
      </header>

      <main className="flex flex-1 flex-col overflow-hidden px-8 pb-8">
        <div className="mx-auto flex w-full max-w-4xl flex-1 flex-col overflow-hidden">
          <div className="flex-1 space-y-4 overflow-y-auto pb-6 pr-1">
            {messages.map((message) => (
              <div key={message.id} className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                <div
                  className={`max-w-[85%] whitespace-pre-wrap rounded-2xl px-4 py-3 text-sm ${
                    message.role === 'user'
                      ? 'bg-slate-900 text-white'
                      : 'border border-white/60 bg-white/70 text-slate-900 shadow-[0_2px_24px_rgba(15,23,42,0.04)] backdrop-blur-xl'
                  }`}
                >
                  {message.content}

                  {message.payload && (
                    <>
                      <div className="mt-3 rounded-2xl border border-white/60 bg-white/65 p-3 text-xs text-slate-600">
                        <p className="mb-1 font-semibold text-slate-800">Kaskade</p>
                        {message.payload.steps.map((step, idx) => (
                          <p key={`${message.id}-step-${idx}`}>{idx + 1}. {step}</p>
                        ))}
                      </div>

                      {message.payload.matches.length > 0 && (
                        <div className="mt-3 grid gap-2">
                          {message.payload.matches.map((match) => (
                            <button
                              key={match.entity.id}
                              onClick={() => navigate(`/browse/${encodeURIComponent(match.entity.id)}`)}
                              className="rounded-2xl border border-white/60 bg-white/80 px-3 py-2 text-left transition-colors hover:bg-white"
                            >
                              <p className="text-sm font-semibold text-slate-900">{match.entity.canonical_name}</p>
                              <p className="text-xs text-slate-600">
                                {String(match.entity.entity_type)} · Score {(match.score * 100).toFixed(1)} · Connections {getConnectionCount(match.entity)} · Tickets {getTicketCount(match.entity)}
                              </p>
                            </button>
                          ))}
                        </div>
                      )}
                    </>
                  )}
                </div>
              </div>
            ))}

            {isLoading && (
              <div className="flex justify-start">
                <div className="rounded-2xl border border-white/60 bg-white/70 px-4 py-3 text-sm text-slate-400 shadow-[0_2px_24px_rgba(15,23,42,0.04)] backdrop-blur-xl">
                  <span className="animate-pulse">Thinking…</span>
                </div>
              </div>
            )}

            <div ref={endRef} />
          </div>

          <div className="sticky bottom-0">
            <div className="flex items-center gap-3 rounded-full border border-white/60 bg-white/70 p-2 shadow-[0_2px_24px_rgba(15,23,42,0.04)] backdrop-blur-xl">
              <input
                type="text"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') {
                    e.preventDefault()
                    void handleSend()
                  }
                }}
                placeholder='z. B. "Senior Engineer mit mehr als 3 Tickets" oder "welche Workstreams sind offen?"'
                className="flex-1 bg-transparent px-4 text-sm text-slate-900 placeholder:text-slate-400 focus:outline-none"
              />
              <button
                onClick={() => void handleSend()}
                disabled={!canSend}
                className="grid size-9 shrink-0 place-items-center rounded-full bg-slate-900 text-white transition-colors hover:bg-slate-800 disabled:opacity-40"
                title="Send"
              >
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <line x1="22" y1="2" x2="11" y2="13" />
                  <polygon points="22 2 15 22 11 13 2 9 22 2" />
                </svg>
              </button>
            </div>
          </div>
        </div>
      </main>
    </div>
  )
}
