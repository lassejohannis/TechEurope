import type { SentimentAnnotation } from '@/types'

interface SentimentChipProps {
  sentiment: SentimentAnnotation | null
}

// This component ONLY reads sentiment from props — it never computes or derives
// sentiment values. If sentiment is null (pipeline hasn't run), renders nothing.
export default function SentimentChip({ sentiment }: SentimentChipProps) {
  if (sentiment === null) return null

  const { sentiment_label, sentiment_score } = sentiment
  const label = sentiment_label.charAt(0).toUpperCase() + sentiment_label.slice(1)
  const sign = sentiment_score >= 0 ? '+' : ''
  const scoreText = `(${sign}${sentiment_score.toFixed(2)})`

  return (
    <span className={`sentiment-chip ${sentiment_label}`}>
      {label}
      <span style={{ opacity: 0.65, fontWeight: 400, marginLeft: 2 }}>{scoreText}</span>
    </span>
  )
}
