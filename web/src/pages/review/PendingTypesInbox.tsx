import { useState } from 'react'
import { Sparkles, CheckCircle, XCircle, Network, FileText, GitBranch } from 'lucide-react'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  useDecidePendingType,
  usePendingTypes,
} from '@/hooks/useConflicts'
import type { PendingTypeItem } from '@/lib/api'

type Kind = 'entity' | 'edge' | 'source_mapping'

const TAB_LABELS: Record<Kind, string> = {
  entity: 'Entity types',
  edge: 'Edge types',
  source_mapping: 'Source mappings',
}

function KindIcon({ kind }: { kind: Kind }) {
  if (kind === 'entity') return <Network className="size-3" />
  if (kind === 'edge') return <GitBranch className="size-3" />
  return <FileText className="size-3" />
}

function ItemCard({
  item,
  onDecide,
}: {
  item: PendingTypeItem
  onDecide: (decision: 'approved' | 'rejected') => void
}) {
  const kind = item.kind
  const distance =
    typeof item.similarity_to_nearest === 'number'
      ? `${item.similarity_to_nearest.toFixed(2)}`
      : null

  return (
    <div className="rounded-lg border bg-card p-4">
      <div className="flex items-start justify-between gap-3">
        <div className="flex flex-col gap-1">
          <div className="flex items-center gap-2">
            <Badge variant="outline" className="gap-1">
              <KindIcon kind={kind} />
              {TAB_LABELS[kind]}
            </Badge>
            {item.auto_proposed && (
              <Badge variant="secondary" className="gap-1">
                <Sparkles className="size-3" />
                AI proposed
              </Badge>
            )}
          </div>
          <p className="font-mono text-base font-medium">{item.id}</p>
          {kind === 'edge' && (item.from_type || item.to_type) && (
            <p className="text-xs text-muted-foreground">
              {item.from_type ?? '?'} → {item.to_type ?? '?'}
            </p>
          )}
          {kind === 'source_mapping' && (
            <p className="text-xs text-muted-foreground">
              source_type: {item.source_type} (v{item.mapping_version})
            </p>
          )}
        </div>
        {distance !== null && (
          <Badge variant="outline" className="text-xs">
            distance {distance}
          </Badge>
        )}
      </div>

      {(item.proposal_rationale || item.rationale) && (
        <p className="mt-3 rounded-md border border-muted bg-muted/30 p-2 text-xs italic text-muted-foreground">
          {item.proposal_rationale ?? item.rationale}
        </p>
      )}

      {item.validation_stats && (
        <div className="mt-2 flex flex-wrap gap-2 text-xs text-muted-foreground">
          {Object.entries(item.validation_stats as Record<string, unknown>).map(([k, v]) => (
            <span key={k} className="rounded-sm bg-muted/50 px-2 py-0.5 font-mono">
              {k}: {String(v)}
            </span>
          ))}
        </div>
      )}

      {item.config && (
        <details className="mt-3">
          <summary className="cursor-pointer text-xs text-muted-foreground">Config</summary>
          <pre className="mt-2 max-h-48 overflow-auto rounded-md bg-muted/40 p-2 text-[10px]">
            {JSON.stringify(item.config, null, 2)}
          </pre>
        </details>
      )}

      <div className="mt-4 flex items-center gap-2">
        <Button
          size="sm"
          variant="default"
          className="gap-1"
          onClick={() => onDecide('approved')}
        >
          <CheckCircle className="size-3" />
          Approve
        </Button>
        <Button
          size="sm"
          variant="outline"
          className="gap-1 text-destructive hover:text-destructive"
          onClick={() => onDecide('rejected')}
        >
          <XCircle className="size-3" />
          Reject
        </Button>
      </div>
    </div>
  )
}

export default function PendingTypesInbox() {
  const [tab, setTab] = useState<Kind>('source_mapping')
  const { data, isPending } = usePendingTypes(tab)
  const decide = useDecidePendingType()

  const items = data?.items ?? []

  return (
    <div className="flex flex-col gap-4 p-4">
      <div>
        <h2 className="text-base font-semibold">Pending types & mappings</h2>
        <p className="text-sm text-muted-foreground">
          New entity/edge types and source-type mappings the AI proposed but
          flagged for human review. Approve to make them part of the live
          schema; reject to discard.
        </p>
      </div>

      <div className="flex items-center gap-1 border-b">
        {(Object.keys(TAB_LABELS) as Kind[]).map((k) => (
          <button
            key={k}
            onClick={() => setTab(k)}
            className={`-mb-px border-b-2 px-3 py-2 text-sm font-medium transition-colors ${
              tab === k
                ? 'border-foreground text-foreground'
                : 'border-transparent text-muted-foreground hover:text-foreground'
            }`}
          >
            {TAB_LABELS[k]}
          </button>
        ))}
      </div>

      {isPending && <p className="text-sm text-muted-foreground">Loading…</p>}

      {!isPending && items.length === 0 && (
        <div className="rounded-md border border-dashed p-6 text-center text-sm text-muted-foreground">
          No pending {TAB_LABELS[tab].toLowerCase()}. The system will populate
          this list as new sources are ingested.
        </div>
      )}

      {!isPending && items.length > 0 && (
        <div className="flex flex-col gap-3">
          {items.map((item) => (
            <ItemCard
              key={`${item.kind}:${item.id}`}
              item={item}
              onDecide={(decision) =>
                decide.mutate({ pendingId: item.id, kind: item.kind, decision })
              }
            />
          ))}
        </div>
      )}

      {decide.isError && (
        <p className="text-xs text-destructive">
          Decision failed. Check API logs.
        </p>
      )}
    </div>
  )
}
