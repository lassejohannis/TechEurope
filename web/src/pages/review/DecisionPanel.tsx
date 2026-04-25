import { CheckCheck, Merge, XCircle } from 'lucide-react'
import { Button } from '@/components/ui/button'

interface Props {
  conflictId: string | null
  selectedClaimIndex: number | null
}

export default function DecisionPanel({ conflictId, selectedClaimIndex }: Props) {
  if (!conflictId) {
    return (
      <div className="flex flex-1 flex-col items-center justify-center gap-3 p-6 text-center">
        <p className="text-sm text-muted-foreground">
          Review the competing facts, then pick one, merge them, or reject both.
        </p>
      </div>
    )
  }

  const canPickOne = selectedClaimIndex !== null

  return (
    <div className="flex flex-col gap-4 p-4">
      <div className="border-b pb-3">
        <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
          Resolve conflict
        </p>
      </div>

      <div className="flex flex-col gap-2">
        <Button
          variant="outline"
          size="sm"
          className="justify-start gap-2"
          disabled={!canPickOne}
        >
          <CheckCheck className="size-4" />
          {canPickOne
            ? `Pick Claim ${String.fromCharCode(65 + selectedClaimIndex!)}`
            : 'Pick a claim (select one above)'}
        </Button>

        <Button variant="outline" size="sm" className="justify-start gap-2" disabled>
          <Merge className="size-4" />
          Merge with qualifier
        </Button>

        <Button
          variant="outline"
          size="sm"
          className="justify-start gap-2 text-destructive hover:text-destructive"
          disabled
        >
          <XCircle className="size-4" />
          Reject both
        </Button>
      </div>

      <div className="rounded-md border bg-muted/30 p-3 text-xs text-muted-foreground">
        <p className="font-medium mb-1">How resolution works</p>
        <ul className="flex flex-col gap-1 list-disc list-inside">
          <li>Pick one → chosen fact stays live, other is superseded</li>
          <li>Merge → new fact created with combined qualifier</li>
          <li>Reject both → both facts moved to "draft" status</li>
        </ul>
        <p className="mt-2">Your decision is recorded as a Resolution and prevents the same conflict from resurfacing.</p>
      </div>
    </div>
  )
}
