interface HealthBadgeProps {
  tier: 'red' | 'yellow' | 'green'
}

const TIER_LABELS: Record<'red' | 'yellow' | 'green', string> = {
  red: 'At Risk',
  yellow: 'Needs Attention',
  green: 'Healthy',
}

export default function HealthBadge({ tier }: HealthBadgeProps) {
  return (
    <span className={`health-badge ${tier}`}>
      <span
        style={{
          width: 6,
          height: 6,
          borderRadius: '50%',
          background: 'currentColor',
          display: 'inline-block',
          flexShrink: 0,
        }}
      />
      {TIER_LABELS[tier]}
    </span>
  )
}
