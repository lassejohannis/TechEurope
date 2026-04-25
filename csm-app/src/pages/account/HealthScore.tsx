import { useState } from 'react'
import type { AccountHealth } from '@/types'
import HealthBadge from '@/components/common/HealthBadge'

interface HealthScoreProps {
  health: AccountHealth
}

function factorScore(value: string | number): number {
  if (typeof value === 'number') return Math.min(Math.max(value, 0), 100)
  const n = parseFloat(value)
  return isNaN(n) ? 50 : Math.min(Math.max(n, 0), 100)
}

export default function HealthScore({ health }: HealthScoreProps) {
  const [expanded, setExpanded] = useState(false)

  // Sort by weight desc so the most impactful factors lead
  const sorted = [...health.factors].sort((a, b) => b.weight - a.weight)
  const top3 = sorted.slice(0, 3)
  const rest = sorted.slice(3)
  const shown = expanded ? sorted : top3

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
        {shown.map((factor) => {
          const pct = factorScore(factor.value)
          return (
            <div key={factor.name} className="health-factor">
              <span className="health-factor-name">{factor.name}</span>
              <div className="hf-bar-track">
                <div
                  className={`hf-bar-fill ${factor.trend}`}
                  style={{ width: `${pct}%` }}
                />
              </div>
              <span className="hf-value">{typeof factor.value === 'number' ? factor.value : factor.value}</span>
            </div>
          )
        })}
      </div>

      {rest.length > 0 && (
        <button
          className="hf-expand-btn"
          onClick={() => setExpanded((v) => !v)}
        >
          {expanded ? 'Show less' : `+ ${rest.length} more`}
        </button>
      )}
    </div>
  )
}
