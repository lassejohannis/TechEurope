import { CheckCheck, Merge, XCircle } from 'lucide-react'
import { useNavigate } from 'react-router-dom'

import { Button } from '@/components/ui/button'
import {
  useDecideEntityPair,
  useDecideFactConflict,
  useEntityPairInbox,
  useFactConflictInbox,
} from '@/hooks/useConflicts'

interface Props {
  conflictId: string | null
  selectedClaimIndex: number | null
}

export default function DecisionPanel({ conflictId, selectedClaimIndex }: Props) {
  const navigate = useNavigate()
  const facts = useFactConflictInbox('pending')
  const pairs = useEntityPairInbox('pending')
  const decideFact = useDecideFactConflict()
  const decidePair = useDecideEntityPair()

  if (!conflictId) {
    return (
      <div className="flex flex-1 flex-col items-center justify-center gap-3 p-6 text-center">
        <p className="text-sm text-muted-foreground">
          Review the competing facts, then pick one, merge them, or reject both.
        </p>
      </div>
    )
  }

  const isPair = conflictId.startsWith('pair:')
  const isFactConflict = conflictId.startsWith('fact:')
  const rawId = conflictId.replace(/^(pair|fact):/, '')
  const canPickOne = selectedClaimIndex !== null

  const onSettled = () => {
    navigate('/review')
  }

  const handlePickFact = () => {
    const item = facts.data?.items.find((i) => i.id === rawId)
    const chosen = selectedClaimIndex !== null ? item?.facts[selectedClaimIndex] : null
    if (!chosen) return
    decideFact.mutate(
      { resolutionId: rawId, decision: 'pick_one', chosenFactId: chosen.id },
      { onSettled },
    )
  }

  const handleRejectFact = () => {
    decideFact.mutate(
      { resolutionId: rawId, decision: 'reject_all' },
      { onSettled },
    )
  }

  const handleMergeFact = () => {
    decideFact.mutate(
      { resolutionId: rawId, decision: 'both_with_qualifier' },
      { onSettled },
    )
  }

  const handlePickPair = () => {
    const item = pairs.data?.items.find((i) => i.id === rawId)
    const chosen = selectedClaimIndex === 0 ? item?.entity_1?.id : item?.entity_2?.id
    if (!chosen) return
    decidePair.mutate(
      { resolutionId: rawId, decision: 'pick_one', chosenEntityId: chosen },
      { onSettled },
    )
  }

  const handleMergePair = () => {
    const item = pairs.data?.items.find((i) => i.id === rawId)
    const chosen = selectedClaimIndex === 0 ? item?.entity_1?.id : item?.entity_2?.id
    if (!chosen) return
    decidePair.mutate(
      { resolutionId: rawId, decision: 'merge', chosenEntityId: chosen },
      { onSettled },
    )
  }

  const handleRejectPair = () => {
    decidePair.mutate(
      { resolutionId: rawId, decision: 'reject' },
      { onSettled },
    )
  }

  const pending = decideFact.isPending || decidePair.isPending

  return (
    <div className="flex flex-col gap-4 p-4">
      <div className="border-b pb-3">
        <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
          Resolve {isPair ? 'entity pair' : 'fact conflict'}
        </p>
      </div>

      <div className="flex flex-col gap-2">
        <Button
          variant="default"
          size="sm"
          className="justify-start gap-2"
          disabled={!canPickOne || pending}
          onClick={isPair ? handlePickPair : handlePickFact}
        >
          <CheckCheck className="size-4" />
          {canPickOne
            ? `Pick ${isPair ? 'entity' : 'claim'} ${String.fromCharCode(65 + selectedClaimIndex!)}`
            : 'Select one above first'}
        </Button>

        <Button
          variant="outline"
          size="sm"
          className="justify-start gap-2"
          disabled={isPair ? !canPickOne : pending}
          onClick={isPair ? handleMergePair : handleMergeFact}
        >
          <Merge className="size-4" />
          {isPair ? 'Merge into selected' : 'Both true (with qualifier)'}
        </Button>

        <Button
          variant="outline"
          size="sm"
          className="justify-start gap-2 text-destructive hover:text-destructive"
          disabled={pending}
          onClick={isPair ? handleRejectPair : handleRejectFact}
        >
          <XCircle className="size-4" />
          {isPair ? 'Reject (separate entities)' : 'Reject both facts'}
        </Button>
      </div>

      {(decideFact.isError || decidePair.isError) && (
        <p className="text-xs text-destructive">
          Decision failed. Try again or check the API logs.
        </p>
      )}

      <div className="rounded-md border bg-muted/30 p-3 text-xs text-muted-foreground">
        <p className="font-medium mb-1">How resolution works</p>
        {isFactConflict && (
          <ul className="flex flex-col gap-1 list-disc list-inside">
            <li>Pick one → chosen fact stays live, others are superseded</li>
            <li>Both true → leave both live (qualifier added later)</li>
            <li>Reject both → all facts marked superseded</li>
          </ul>
        )}
        {isPair && (
          <ul className="flex flex-col gap-1 list-disc list-inside">
            <li>Pick one → mark as canonical, other stays separate</li>
            <li>Merge → aliases combined, kept entity wins</li>
            <li>Reject → mark as different real-world entities</li>
          </ul>
        )}
        <p className="mt-2">
          Your decision is audited and prevents the same conflict from resurfacing.
        </p>
      </div>
    </div>
  )
}
