export function SentimentBadge({ label, confidence }: { label?: string | null; confidence?: number | null }) {
  if (!label) return null
  const norm = String(label).toLowerCase()
  const color = norm === 'positive' ? '#16a34a' : norm === 'negative' ? '#dc2626' : '#6b7280'
  const bg = `${color}20`
  const conf = typeof confidence === 'number' ? ` • ${(confidence * 100).toFixed(0)}%` : ''
  return (
    <span
      title={`Sentiment: ${norm}${conf}`}
      style={{
        display: 'inline-flex', alignItems: 'center', gap: 6,
        padding: '2px 8px', borderRadius: 999, background: bg,
        color, fontSize: 12, fontWeight: 600, lineHeight: '18px',
      }}
    >
      Sentiment: {norm}{conf && <span style={{ opacity: 0.7 }}>{conf}</span>}
    </span>
  )
}

