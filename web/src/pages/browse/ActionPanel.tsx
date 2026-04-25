import { useState } from 'react'
import { Flag, Plus, GitBranch } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { useEntity } from '@/hooks/useEntity'

interface Props {
  entityId: string | null
}

export default function ActionPanel({ entityId }: Props) {
  const { data } = useEntity(entityId)
  const [proposeOpen, setProposeOpen] = useState(false)
  const [predicate, setPredicate] = useState('')
  const [value, setValue] = useState('')

  if (!entityId) {
    return (
      <div className="flex flex-1 flex-col items-center justify-center gap-3 p-6 text-center">
        <p className="text-sm text-muted-foreground">
          Actions appear here once you select an entity — propose facts, flag disputes, or trace
          provenance.
        </p>
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-4 p-4">
      <div className="border-b pb-3">
        <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
          Actions
        </p>
        {data && (
          <p className="mt-1 text-sm font-medium truncate">{data.entity.canonical_name}</p>
        )}
      </div>

      <div className="flex flex-col gap-2">
        <Button
          variant="outline"
          size="sm"
          className="justify-start gap-2"
          onClick={() => setProposeOpen(true)}
        >
          <Plus className="size-4" />
          Propose fact
        </Button>

        <Button variant="outline" size="sm" className="justify-start gap-2" disabled>
          <Flag className="size-4" />
          Flag a fact
        </Button>

        <Button variant="outline" size="sm" className="justify-start gap-2" disabled>
          <GitBranch className="size-4" />
          View provenance
        </Button>
      </div>

      {data && data.facts.some((f) => f.status === 'disputed') && (
        <div className="rounded-md border border-destructive/30 bg-destructive/5 p-3">
          <p className="text-xs font-medium text-destructive">
            {data.facts.filter((f) => f.status === 'disputed').length} conflict
            {data.facts.filter((f) => f.status === 'disputed').length > 1 ? 's' : ''} pending
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
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setProposeOpen(false)}>
              Cancel
            </Button>
            <Button disabled={!predicate || !value}>
              Propose
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
