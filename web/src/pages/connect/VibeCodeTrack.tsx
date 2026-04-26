import { useMemo } from 'react'
import { Download, Sparkles } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { VIBE_AGENTS, type VibeAgent } from './connectors'
import { buildAgentPrompt } from './AgentPromptTemplate'
import CodeBlock from './CodeBlock'

type Props = {
  apiBaseUrl: string
  token: string | null
  selectedAgentId: VibeAgent['id']
  onSelectAgent: (id: VibeAgent['id']) => void
}

export default function VibeCodeTrack({
  apiBaseUrl,
  token,
  selectedAgentId,
  onSelectAgent,
}: Props) {
  const selected = useMemo(
    () => VIBE_AGENTS.find((a) => a.id === selectedAgentId) ?? VIBE_AGENTS[0],
    [selectedAgentId],
  )

  const prompt = useMemo(
    () => buildAgentPrompt({ apiBaseUrl, token }),
    [apiBaseUrl, token],
  )

  function handleDownload() {
    const blob = new Blob([prompt], { type: 'text/markdown;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'AGENTS.md'
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    setTimeout(() => URL.revokeObjectURL(url), 0)
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 22 }}>
      {/* Step A — Pick your AI agent */}
      <section>
        <SectionHeader
          step="A"
          title="Pick your AI agent"
          subtitle="The same prompt works in any of these — pick the one you already use."
        />
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(3, minmax(0, 1fr))',
            gap: 10,
          }}
        >
          {VIBE_AGENTS.map((a) => {
            const active = a.id === selectedAgentId
            return (
              <button
                key={a.id}
                type="button"
                onClick={() => onSelectAgent(a.id)}
                style={{
                  textAlign: 'left',
                  background: 'white',
                  border: '1px solid #e5e5e5',
                  outline: active ? '2px solid #6366f1' : '2px solid transparent',
                  outlineOffset: -2,
                  boxShadow: active ? '0 0 0 3px rgba(99,102,241,0.12)' : 'none',
                  borderRadius: 10,
                  padding: '12px 14px',
                  cursor: 'pointer',
                  transition: 'box-shadow 0.15s ease, outline-color 0.15s ease',
                  height: 92,
                  display: 'flex',
                  flexDirection: 'column',
                  justifyContent: 'space-between',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <span style={{ fontSize: 22, lineHeight: 1 }}>{a.emoji}</span>
                  <span style={{ fontWeight: 600, fontSize: 14 }}>{a.name}</span>
                </div>
                <div
                  style={{
                    fontSize: 11.5,
                    color: '#6b7280',
                    lineHeight: 1.35,
                    display: '-webkit-box',
                    WebkitLineClamp: 2,
                    WebkitBoxOrient: 'vertical',
                    overflow: 'hidden',
                  }}
                >
                  {a.invokeSummary}
                </div>
              </button>
            )
          })}
        </div>
      </section>

      {/* Step B — Copy the prompt */}
      <section>
        <SectionHeader
          step="B"
          title="Copy the integration prompt"
          subtitle="Self-contained — embeds your token, the API base URL, and the tool schemas."
        />

        {!token && <NoTokenBanner />}

        <CodeBlock code={prompt} language="markdown" />

        <div style={{ display: 'flex', gap: 8, marginTop: 10, flexWrap: 'wrap' }}>
          <Button onClick={handleDownload} variant="outline">
            <Download size={14} />
            <span style={{ marginLeft: 6 }}>Download as AGENTS.md</span>
          </Button>
          <span
            style={{
              fontSize: 12,
              color: '#6b7280',
              alignSelf: 'center',
              display: 'inline-flex',
              alignItems: 'center',
              gap: 4,
            }}
          >
            <Sparkles size={12} />
            Drop the file at your repo root — most agents will pick it up automatically.
          </span>
        </div>
      </section>

      {/* Step C — How to use it */}
      <section>
        <SectionHeader
          step="C"
          title={`Run it in ${selected.name}`}
          subtitle="Paste the prompt above into the agent — it will scan your project, register the tools, and verify."
        />
        <ol
          style={{
            paddingLeft: 22,
            margin: 0,
            background: 'white',
            border: '1px solid #e5e5e5',
            borderRadius: 10,
            padding: '16px 16px 16px 36px',
          }}
        >
          {selected.invokeSteps.map((step, i) => (
            <li
              key={i}
              style={{
                marginBottom: i === selected.invokeSteps.length - 1 ? 0 : 10,
                fontSize: 13.5,
                color: '#1f2937',
                lineHeight: 1.55,
              }}
            >
              <Inline text={step} />
            </li>
          ))}
        </ol>
      </section>
    </div>
  )
}

function SectionHeader({
  step,
  title,
  subtitle,
}: {
  step: string
  title: string
  subtitle?: string
}) {
  return (
    <div style={{ marginBottom: 12 }}>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 8 }}>
        <span
          style={{
            fontSize: 11,
            color: '#9ca3af',
            fontWeight: 600,
            letterSpacing: 0.5,
            textTransform: 'uppercase',
          }}
        >
          Step 2{step}
        </span>
        <h3 style={{ fontSize: 15, fontWeight: 600, margin: 0 }}>{title}</h3>
      </div>
      {subtitle && (
        <p style={{ color: '#6b7280', fontSize: 12.5, margin: '2px 0 0', lineHeight: 1.5 }}>
          {subtitle}
        </p>
      )}
    </div>
  )
}

function NoTokenBanner() {
  return (
    <div
      style={{
        padding: '8px 12px',
        background: '#fffbeb',
        border: '1px solid #fde68a',
        borderRadius: 8,
        color: '#92400e',
        fontSize: 12.5,
        marginBottom: 10,
      }}
    >
      No token yet — generate one above and the prompt will fill in automatically.
    </div>
  )
}

// Render markdown-style inline code (`like this`) in step text.
function Inline({ text }: { text: string }) {
  const parts = text.split(/(`[^`]+`)/g)
  return (
    <>
      {parts.map((p, i) =>
        p.startsWith('`') && p.endsWith('`') ? (
          <code
            key={i}
            style={{
              fontFamily: 'ui-monospace, SFMono-Regular, Menlo, monospace',
              fontSize: 12.5,
              background: '#f3f4f6',
              padding: '1px 5px',
              borderRadius: 4,
            }}
          >
            {p.slice(1, -1)}
          </code>
        ) : (
          <span key={i}>{p}</span>
        ),
      )}
    </>
  )
}
