import { useMemo, useState } from 'react'
import { Flag, Plus, GitBranch, Activity, CheckCircle2, Info } from 'lucide-react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip'
import { useEntity } from '@/hooks/useEntity'
import { ApiError, proposeFact } from '@/lib/api'

interface Props {
  entityId: string | null
}

export default function ActionPanel({ entityId }: Props) {
  const { data } = useEntity(entityId)
  const qc = useQueryClient()
  const [proposeOpen, setProposeOpen] = useState(false)
  const [predicate, setPredicate] = useState('')
  const [value, setValue] = useState('')
  const [proposeConfidence, setProposeConfidence] = useState(0.8)
  const [statusMsg, setStatusMsg] = useState<string | null>(null)

  const proposeMutation = useMutation({
    mutationFn: async () => {
      if (!entityId) throw new Error('No entity selected')
      return proposeFact({
        subject_id: entityId,
        predicate: predicate.trim(),
        object_literal: value.trim(),
        confidence: proposeConfidence,
        source_system: 'browse_ui',
        source_method: 'human_input',
      })
    },
    onSuccess: () => {
      setStatusMsg('Fact proposed successfully.')
      setProposeOpen(false)
      setPredicate('')
      setValue('')
      setProposeConfidence(0.8)
      qc.invalidateQueries({ queryKey: ['entity', entityId] })
    },
    onError: (error: unknown) => {
      if (error instanceof ApiError) {
        setStatusMsg(`Could not propose fact (${error.status}).`)
        return
      }
      setStatusMsg('Could not propose fact.')
    },
  })

  const facts = data?.facts ?? []
  const liveCount = facts.filter((f) => f.status === 'live' || f.status === 'active').length
  const disputedCount = facts.filter((f) => f.status === 'disputed').length
  const staleCount = facts.filter((f) => f.status === 'needs_refresh' || f.status === 'superseded').length
  const avgConfidence = facts.length
    ? facts.reduce((sum, f) => sum + f.confidence, 0) / facts.length
    : 0

  const topPredicates = useMemo(() => {
    const counts = new Map<string, number>()
    for (const f of facts) {
      counts.set(f.predicate, (counts.get(f.predicate) ?? 0) + 1)
    }
    return [...counts.entries()]
      .sort((a, b) => b[1] - a[1])
      .slice(0, 4)
  }, [facts])

  const attributeCount = useMemo(
    () => Object.values(data?.attrs ?? {}).filter((v) => v != null && String(v).trim() !== '').length,
    [data?.attrs],
  )
  const hasQualityScore = facts.length > 0

  if (!entityId) {
    return (
      <div className="flex flex-1 flex-col items-center justify-center gap-3 p-6 text-center">
        <p className="text-sm text-muted-foreground">
          Select an entity to see insights, key attributes, and quick actions.
        </p>
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-4 p-4">
      <Card size="sm">
        <CardHeader className="pb-2">
          <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
            Insights
          </p>
          {data && <CardTitle className="truncate">{data.canonical_name}</CardTitle>}
          <div className="flex flex-wrap gap-1">
            <Badge variant="secondary">{data?.entity_type}</Badge>
            <Badge variant="outline">{facts.length} facts</Badge>
            <TooltipProvider>
              <Tooltip>
                <TooltipTrigger>
                  <Badge variant="outline" className="inline-flex items-center gap-1">
                    Data Quality {hasQualityScore ? `${Math.round((data?.trust_score ?? 0) * 100)}%` : 'No score yet'}
                    <Info className="size-3" />
                  </Badge>
                </TooltipTrigger>
                <TooltipContent>
                  Score = avg confidence × source diversity × recency.
                </TooltipContent>
              </Tooltip>
            </TooltipProvider>
          </div>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="grid grid-cols-3 gap-2">
            <div className="rounded-md border bg-muted/30 p-2">
              <p className="text-[11px] text-muted-foreground">Live</p>
              <p className="text-sm font-semibold">{liveCount}</p>
            </div>
            <div className="rounded-md border bg-muted/30 p-2">
              <p className="text-[11px] text-muted-foreground">Disputed</p>
              <p className="text-sm font-semibold">{disputedCount}</p>
            </div>
            <div className="rounded-md border bg-muted/30 p-2">
              <p className="text-[11px] text-muted-foreground">Stale</p>
              <p className="text-sm font-semibold">{staleCount}</p>
            </div>
          </div>
          <div className="flex items-center justify-between text-xs text-muted-foreground">
            <span className="inline-flex items-center gap-1">
              <Activity className="size-3.5" /> Avg confidence
            </span>
            <span className="font-medium text-foreground">{Math.round(avgConfidence * 100)}%</span>
          </div>
        </CardContent>
      </Card>

      <Card size="sm">
        <CardHeader className="pb-2">
          <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Quick Actions</p>
        </CardHeader>
        <CardContent className="space-y-2">
          <Button
            variant="outline"
            size="sm"
            className="w-full justify-start gap-2"
            onClick={() => setProposeOpen(true)}
          >
            <Plus className="size-4" />
            Propose fact
          </Button>
          <Button variant="outline" size="sm" className="w-full justify-start gap-2" disabled>
            <Flag className="size-4" />
            Flag a fact
          </Button>
          <Button variant="outline" size="sm" className="w-full justify-start gap-2" disabled>
            <GitBranch className="size-4" />
            View provenance
          </Button>
          {statusMsg && (
            <p className="inline-flex items-center gap-1 text-xs text-muted-foreground">
              <CheckCircle2 className="size-3.5" />
              {statusMsg}
            </p>
          )}
        </CardContent>
      </Card>

      <Card size="sm">
        <CardHeader className="pb-2">
          <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Coverage</p>
        </CardHeader>
        <CardContent className="space-y-2">
          <div className="grid grid-cols-2 gap-2 text-xs">
            <div className="rounded-md border bg-muted/30 p-2">
              <p className="text-muted-foreground">Attributes</p>
              <p className="font-semibold text-foreground">{attributeCount}</p>
            </div>
            <div className="rounded-md border bg-muted/30 p-2">
              <p className="text-muted-foreground">Predicates</p>
              <p className="font-semibold text-foreground">{topPredicates.length}</p>
            </div>
          </div>
          <div>
            <p className="mb-1 text-[11px] font-medium uppercase tracking-wide text-muted-foreground">Top Predicates</p>
            {topPredicates.length === 0 ? (
              <p className="text-xs text-muted-foreground">No facts available.</p>
            ) : (
              <div className="flex flex-wrap gap-1">
                {topPredicates.map(([pred, count]) => (
                  <Badge key={pred} variant="outline">
                    {pred.replace(/_/g, ' ')} ({count})
                  </Badge>
                ))}
              </div>
            )}
          </div>
        </CardContent>
      </Card>

      {disputedCount > 0 && (
        <div className="rounded-md border border-destructive/30 bg-destructive/5 p-3">
          <p className="text-xs font-medium text-destructive">
            {disputedCount} conflict
            {disputedCount > 1 ? 's' : ''} pending
          </p>
          <p className="mt-0.5 text-xs text-muted-foreground">
            Go to Review mode to resolve.
          </p>
        </div>
      )}

      <Dialog open={proposeOpen} onOpenChange={setProposeOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Propose a fact</DialogTitle>
          </DialogHeader>
          <div className="flex flex-col gap-3 py-2">
            <div className="flex flex-col gap-1.5">
              <label className="text-sm font-medium">Subject</label>
              <Input value={entityId} disabled className="font-mono text-xs" />
            </div>
            <div className="flex flex-col gap-1.5">
              <label className="text-sm font-medium">Predicate</label>
              <Input
                placeholder="e.g. renewal_date, email, department"
                value={predicate}
                onChange={(e) => setPredicate(e.target.value)}
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <label className="text-sm font-medium">Value</label>
              <Input
                placeholder="Enter value"
                value={value}
                onChange={(e) => setValue(e.target.value)}
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <label className="text-sm font-medium">Confidence</label>
              <div className="grid grid-cols-3 gap-1.5">
                {[0.6, 0.8, 0.95].map((c) => (
                  <Button
                    key={c}
                    variant={proposeConfidence === c ? 'default' : 'outline'}
                    size="sm"
                    onClick={() => setProposeConfidence(c)}
                  >
                    {Math.round(c * 100)}%
                  </Button>
                ))}
              </div>
              <p className="text-xs text-muted-foreground">
                Use lower values for uncertain inputs and higher values for verified facts.
              </p>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setProposeOpen(false)}>
              Cancel
            </Button>
            <Button
              disabled={!predicate.trim() || !value.trim() || proposeMutation.isPending}
              onClick={() => proposeMutation.mutate()}
            >
              {proposeMutation.isPending ? 'Saving…' : 'Propose'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
