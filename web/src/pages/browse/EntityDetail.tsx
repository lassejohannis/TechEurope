import { Network } from 'lucide-react'
import { Card, CardContent, CardHeader } from '@/components/ui/card'
import { Separator } from '@/components/ui/separator'
import { Skeleton } from '@/components/ui/skeleton'
import { EntityTypeBadge } from '@/components/entity/EntityTypeBadge'
import { FactRow } from '@/components/entity/FactRow'
import { useEntity } from '@/hooks/useEntity'

interface Props {
  entityId: string | null
}

const UUIDISH_PATTERN =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i

function isUuidish(value: string): boolean {
  return UUIDISH_PATTERN.test(value.trim())
}

function readString(value: unknown): string | null {
  if (typeof value === 'string' && value.trim()) return value.trim()
  if (typeof value === 'number' || typeof value === 'boolean') return String(value)
  if (value && typeof value === 'object') {
    const obj = value as Record<string, unknown>
    for (const key of ['canonical_name', 'name', 'title', 'label', 'value', 'subject']) {
      const nested = obj[key]
      if (typeof nested === 'string' && nested.trim()) return nested.trim()
    }
  }
  return null
}

function LoadingSkeleton() {
  return (
    <div className="flex flex-col gap-4 p-4">
      <div className="flex items-center gap-2">
        <Skeleton className="h-5 w-16" />
        <Skeleton className="h-6 w-48" />
      </div>
      <Skeleton className="h-px w-full" />
      {[1, 2, 3, 4].map((i) => (
        <div key={i} className="flex items-center justify-between">
          <Skeleton className="h-4 w-32" />
          <Skeleton className="h-5 w-12" />
        </div>
      ))}
    </div>
  )
}

export default function EntityDetail({ entityId }: Props) {
  const { data, isLoading, isError } = useEntity(entityId)

  if (!entityId) {
    return (
      <div className="flex flex-1 flex-col items-center justify-center gap-3 p-8 text-center">
        <Network className="size-8 text-muted-foreground/40" />
        <p className="text-sm text-muted-foreground">
          Select an entity from the tree on the left to inspect its facts, provenance, and related
          entities.
        </p>
      </div>
    )
  }

  if (isLoading) return <LoadingSkeleton />

  if (isError || !data) {
    return (
      <div className="flex flex-col gap-4 p-4">
        <p className="text-sm text-muted-foreground">
          Backend not yet available. This panel will show full entity details once the API is live.
        </p>
        <Card>
          <CardContent className="pt-4">
            <p className="font-mono text-xs text-muted-foreground break-all">{entityId}</p>
          </CardContent>
        </Card>
      </div>
    )
  }

  const liveFacts = data.facts.filter(
    (f) => f.status === 'live' || f.status === 'active' || f.status === 'disputed',
  )
  const disputedCount = data.facts.filter((f) => f.status === 'disputed').length
  const subjectFromAttrs = readString(data.attrs?.subject)
  const subjectFromFacts =
    data.facts
      .filter((f) => {
        const predicate = String(f.predicate ?? '')
          .toLowerCase()
          .replace(/[_\s-]+/g, '')
        return predicate === 'subject' || predicate === 'hassubject'
      })
      .map((f) => readString(f.object_literal) ?? readString(f.object_id))
      .find(Boolean) ?? null
  const displayName =
    String(data.entity_type).toLowerCase() === 'communication' && isUuidish(data.canonical_name)
      ? (subjectFromAttrs ?? subjectFromFacts ?? data.canonical_name)
      : data.canonical_name
  const visibleAliases = data.aliases.filter((alias) => alias && alias !== displayName)

  return (
    <div className="flex flex-col gap-4 p-4">
      <Card>
        <CardHeader className="pb-3">
          <div className="flex items-start justify-between gap-2">
            <div className="flex flex-col gap-1.5">
              <EntityTypeBadge type={data.entity_type} />
              <h2 className="text-lg font-semibold leading-tight">{displayName}</h2>
              {visibleAliases.length > 0 && (
                <p className="text-xs text-muted-foreground">
                  Also known as: {visibleAliases.join(', ')}
                </p>
              )}
            </div>
            {disputedCount > 0 && (
              <span className="shrink-0 rounded-full bg-destructive/10 px-2 py-0.5 text-xs font-medium text-destructive">
                {disputedCount} conflict{disputedCount > 1 ? 's' : ''}
              </span>
            )}
          </div>
        </CardHeader>

        <CardContent className="flex flex-col gap-0">
          <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
            Facts
          </p>
          {liveFacts.length === 0 ? (
            <p className="py-4 text-sm text-muted-foreground">
              This entity has no live facts yet.
            </p>
          ) : (
            liveFacts.map((fact, i) => (
              <div key={fact.id}>
                <FactRow fact={fact} />
                {i < liveFacts.length - 1 && <Separator />}
              </div>
            ))
          )}
        </CardContent>
      </Card>

      <p className="text-xs text-muted-foreground">
        Path: <span className="font-mono">{String(data.attrs?.vfs_path ?? `/entities/${data.id}`)}</span>
      </p>
    </div>
  )
}
