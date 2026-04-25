import { Shield } from 'lucide-react'

import { useTrustWeights } from '@/hooks/useConflicts'

/**
 * Read-only display of source_trust_weights.yaml. Used as a sidebar reference
 * so reviewers can see why the auto-resolution cascade picked one source over
 * another (Authority tier).
 */
export default function TrustWeightsPanel() {
  const { data, isPending } = useTrustWeights()
  const weights = data?.weights ?? {}
  const entries = Object.entries(weights).sort(([, a], [, b]) => b - a)

  return (
    <div className="border-t bg-muted/20 p-4">
      <div className="mb-3 flex items-center gap-2">
        <Shield className="size-4 text-muted-foreground" />
        <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
          Source trust weights
        </p>
      </div>

      {isPending && (
        <p className="text-xs text-muted-foreground">Loading…</p>
      )}

      {!isPending && entries.length === 0 && (
        <p className="text-xs text-muted-foreground">
          No weights configured. Defaults to 0.5 for unknown sources.
        </p>
      )}

      {!isPending && entries.length > 0 && (
        <ul className="flex flex-col gap-1.5">
          {entries.map(([source, weight]) => (
            <li key={source} className="flex items-center gap-2 text-xs">
              <span className="w-28 truncate font-mono">{source}</span>
              <div className="flex-1 h-1.5 rounded-full bg-muted overflow-hidden">
                <div
                  className="h-full bg-foreground/70"
                  style={{ width: `${weight * 100}%` }}
                />
              </div>
              <span className="w-10 text-right tabular-nums text-muted-foreground">
                {weight.toFixed(2)}
              </span>
            </li>
          ))}
        </ul>
      )}

      <p className="mt-3 text-[10px] text-muted-foreground">
        Higher weight ⇒ source wins ties in the authority tier of auto-resolution.
        Configured in <code className="font-mono">config/source_trust_weights.yaml</code>.
      </p>
    </div>
  )
}
