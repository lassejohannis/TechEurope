import { useState } from 'react'
import { useParams } from 'react-router-dom'
import ThreeColumnLayout from '@/components/layout/ThreeColumnLayout'
import ConflictInbox from './ConflictInbox'
import ConflictDetail from './ConflictDetail'
import DecisionPanel from './DecisionPanel'

export default function ReviewPage() {
  const { conflictId } = useParams<{ conflictId: string }>()
  const activeId = conflictId ? decodeURIComponent(conflictId) : null
  const [selectedClaimIndex, setSelectedClaimIndex] = useState<number | null>(null)

  return (
    <ThreeColumnLayout
      left={<ConflictInbox selectedId={activeId} />}
      center={
        <ConflictDetail
          conflictId={activeId}
          selectedClaimIndex={selectedClaimIndex}
          onSelectClaim={setSelectedClaimIndex}
        />
      }
      right={
        <DecisionPanel conflictId={activeId} selectedClaimIndex={selectedClaimIndex} />
      }
    />
  )
}
