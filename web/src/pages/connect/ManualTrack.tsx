import { useMemo, useState } from 'react'
import { ChevronRight } from 'lucide-react'
import {
  CONNECTORS,
  TIER_BLURB,
  TIER_LABEL,
  TIER_ORDER,
  type Connector,
  type Tier,
} from './connectors'
import CodeBlock from './CodeBlock'

type Props = {
  token: string | null
  substitute: (s: string) => string
}

export default function ManualTrack({ token, substitute }: Props) {
  const byTier = useMemo(() => groupByTier(), [])

  // Per tier: which connector is currently selected
  const [selectedByTier, setSelectedByTier] = useState<Record<Tier, string>>(
    () => Object.fromEntries(TIER_ORDER.map((t) => [t, byTier[t][0]?.id])) as Record<Tier, string>,
  )
  // Per tier: open/closed
  const [openTiers, setOpenTiers] = useState<Record<Tier, boolean>>({
    'mcp-clients': true,
    'agent-sdks': false,
    automation: false,
    raw: false,
  })

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
      {!token && <NoTokenBanner />}

      {TIER_ORDER.map((tier) => {
        const open = openTiers[tier]
        const connectors = byTier[tier]
        const selectedId = selectedByTier[tier]
        const selected = connectors.find((c) => c.id === selectedId) ?? connectors[0]

        return (
          <section
            key={tier}
            style={{
              background: 'white',
              border: '1px solid #e5e5e5',
              borderRadius: 12,
              overflow: 'hidden',
            }}
          >
            <button
              type="button"
              onClick={() => setOpenTiers((o) => ({ ...o, [tier]: !o[tier] }))}
              style={{
                width: '100%',
                background: 'transparent',
                border: 'none',
                cursor: 'pointer',
                padding: '14px 18px',
                display: 'flex',
                alignItems: 'center',
                gap: 10,
                textAlign: 'left',
              }}
            >
              <ChevronRight
                size={16}
                style={{
                  transform: open ? 'rotate(90deg)' : 'rotate(0deg)',
                  transition: 'transform 0.15s ease',
                  color: '#6b7280',
                  flexShrink: 0,
                }}
              />
              <div style={{ flex: 1, minWidth: 0 }}>
                <div
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 10,
                    flexWrap: 'wrap',
                  }}
                >
                  <h3 style={{ fontSize: 15, fontWeight: 600, margin: 0 }}>
                    {TIER_LABEL[tier]}
                  </h3>
                  <span style={{ fontSize: 11.5, color: '#9ca3af' }}>
                    {connectors.length} option{connectors.length === 1 ? '' : 's'}
                  </span>
                </div>
                <p
                  style={{
                    margin: '2px 0 0',
                    color: '#6b7280',
                    fontSize: 12.5,
                    lineHeight: 1.45,
                  }}
                >
                  {TIER_BLURB[tier]}
                </p>
              </div>
            </button>

            {open && (
              <div style={{ padding: '0 18px 18px', minWidth: 0 }}>
                <ConnectorRow
                  connectors={connectors}
                  selectedId={selectedId}
                  onSelect={(id) => setSelectedByTier((s) => ({ ...s, [tier]: id }))}
                />

                <ConnectorDetail
                  connector={selected}
                  token={token}
                  substitute={substitute}
                />
              </div>
            )}
          </section>
        )
      })}
    </div>
  )
}

function ConnectorRow({
  connectors,
  selectedId,
  onSelect,
}: {
  connectors: Connector[]
  selectedId?: string
  onSelect: (id: string) => void
}) {
  return (
    <div
      style={{
        display: 'flex',
        gap: 8,
        flexWrap: 'wrap',
        marginBottom: 16,
      }}
    >
      {connectors.map((c) => {
        const active = c.id === selectedId
        return (
          <button
            key={c.id}
            type="button"
            onClick={() => onSelect(c.id)}
            style={{
              padding: '6px 12px',
              borderRadius: 999,
              fontSize: 12.5,
              fontWeight: active ? 600 : 500,
              cursor: 'pointer',
              background: active ? '#eef2ff' : '#f9fafb',
              color: active ? '#4338ca' : '#374151',
              border: active ? '1.5px solid #6366f1' : '1px solid #e5e7eb',
              display: 'inline-flex',
              alignItems: 'center',
              gap: 6,
            }}
          >
            <span>{c.name}</span>
          </button>
        )
      })}
    </div>
  )
}

function ConnectorDetail({
  connector,
  token: _token,
  substitute,
}: {
  connector: Connector
  token: string | null
  substitute: (s: string) => string
}) {
  const [langIdx, setLangIdx] = useState(0)
  // Reset language when switching connector — guard against out-of-range
  const safeIdx = langIdx >= connector.languages.length ? 0 : langIdx
  const variant = connector.languages[safeIdx]
  const showLangPicker = connector.languages.length > 1

  return (
    <div
      style={{
        borderTop: '1px solid #f3f4f6',
        paddingTop: 16,
        minWidth: 0,
        overflow: 'hidden',
      }}
    >
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: 12,
          flexWrap: 'wrap',
          marginBottom: 14,
        }}
      >
        <div style={{ minWidth: 0 }}>
          <h4 style={{ fontSize: 15, fontWeight: 600, margin: 0 }}>
            {connector.name}
          </h4>
          <p style={{ color: '#6b7280', fontSize: 12.5, margin: '2px 0 0' }}>
            {connector.blurb}
          </p>
        </div>

        {showLangPicker && (
          <div style={{ display: 'flex', gap: 4 }}>
            {connector.languages.map((v, i) => {
              const active = i === safeIdx
              return (
                <button
                  key={v.language + i}
                  type="button"
                  onClick={() => setLangIdx(i)}
                  style={{
                    padding: '4px 10px',
                    borderRadius: 6,
                    fontSize: 11.5,
                    fontWeight: active ? 600 : 500,
                    cursor: 'pointer',
                    background: active ? '#1f2937' : 'transparent',
                    color: active ? 'white' : '#374151',
                    border: '1px solid ' + (active ? '#1f2937' : '#e5e7eb'),
                  }}
                >
                  {v.label}
                </button>
              )
            })}
          </div>
        )}
      </div>

      <ol style={{ paddingLeft: 20, margin: 0, minWidth: 0 }}>
        {variant.steps.map((step, i) => (
          <li key={i} style={{ marginBottom: 18, minWidth: 0 }}>
            <div style={{ fontWeight: 600, fontSize: 13.5, marginBottom: 6 }}>{step.title}</div>
            {step.snippet && (
              <CodeBlock code={substitute(step.snippet)} language={step.language} />
            )}
            {step.note && (
              <p style={{ color: '#6b7280', fontSize: 12.5, marginTop: 6, lineHeight: 1.5 }}>
                {step.note}
              </p>
            )}
          </li>
        ))}
      </ol>

      {variant.testCommand && (
        <div style={{ marginTop: 6, paddingTop: 14, borderTop: '1px solid #f3f4f6' }}>
          <div style={{ fontWeight: 600, fontSize: 13.5, marginBottom: 6 }}>
            Verify it works
          </div>
          <CodeBlock code={substitute(variant.testCommand)} language="bash" />
        </div>
      )}
    </div>
  )
}

function NoTokenBanner() {
  return (
    <div
      style={{
        padding: '10px 14px',
        background: '#fffbeb',
        border: '1px solid #fde68a',
        borderRadius: 8,
        color: '#92400e',
        fontSize: 12.5,
      }}
    >
      Generate a token in Step 1 first — snippets below will be filled with{' '}
      <code style={{ fontFamily: 'ui-monospace, monospace' }}>&lt;paste your token here&gt;</code>{' '}
      until then.
    </div>
  )
}

function groupByTier(): Record<Tier, Connector[]> {
  const out = { 'mcp-clients': [], 'agent-sdks': [], automation: [], raw: [] } as Record<
    Tier,
    Connector[]
  >
  for (const c of CONNECTORS) out[c.tier].push(c)
  return out
}
