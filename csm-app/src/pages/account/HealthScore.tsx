import type { AccountHealth } from '@/types'
import HealthBadge from '@/components/common/HealthBadge'

interface HealthScoreProps {
  health: AccountHealth
}

const TREND_ICON: Record<'up' | 'down' | 'flat', string> = {
  up: '↑',
  down: '↓',
  flat: '→',
}

const TREND_COLOR: Record<'up' | 'down' | 'flat', string> = {
  up: 'var(--conf-high)',
  down: 'var(--conf-conflict)',
  flat: 'var(--text-tertiary)',
}

export default function HealthScore({ health }: HealthScoreProps) {
  return (
    <div className="health-card">
      <div className="health-score-row">
        <div>
          <div className={`health-score-num ${health.tier}`}>{health.score}</div>
          <div className="health-score-label">Health Score</div>
        </div>
        <HealthBadge tier={health.tier} />
      </div>

      <div className="health-factors">
        {health.factors.map((factor) => (
          <div key={factor.name} className="health-factor">
            <span className="health-factor-name">{factor.name}</span>
            <span className="health-factor-value">
              {typeof factor.value === 'number' ? factor.value : factor.value}
            </span>
            <span
              className="health-factor-trend"
              style={{ color: TREND_COLOR[factor.trend] }}
            >
              {TREND_ICON[factor.trend]}
            </span>
          </div>
        ))}
      </div>
    </div>
  )
}
