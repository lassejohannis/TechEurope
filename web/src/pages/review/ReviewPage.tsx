import { useState } from 'react'
import { useParams } from 'react-router-dom'

import ThreeColumnLayout from '@/components/layout/ThreeColumnLayout'
import ConflictDetail from './ConflictDetail'
import ConflictInbox from './ConflictInbox'
import DecisionPanel from './DecisionPanel'
import TrustWeightsPanel from './TrustWeightsPanel'

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
        <div className="flex h-full flex-col">
          <div className="flex-1 overflow-y-auto">
            <DecisionPanel
              conflictId={activeId}
              selectedClaimIndex={selectedClaimIndex}
            />
          </div>
          <TrustWeightsPanel />
        </div>
      }
    />
  )
}
