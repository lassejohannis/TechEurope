import { useState } from 'react'
import { useParams } from 'react-router-dom'

import ThreeColumnLayout from '@/components/layout/ThreeColumnLayout'
import ConflictDetail from './ConflictDetail'
import ConflictInbox from './ConflictInbox'
import DecisionPanel from './DecisionPanel'
import PendingTypesInbox from './PendingTypesInbox'
import TrustWeightsPanel from './TrustWeightsPanel'

type View = 'conflicts' | 'pending_types'

export default function ReviewPage() {
  const { conflictId } = useParams<{ conflictId: string }>()
  const activeId = conflictId ? decodeURIComponent(conflictId) : null
  const [selectedClaimIndex, setSelectedClaimIndex] = useState<number | null>(null)
  const [view, setView] = useState<View>('conflicts')

  if (view === 'pending_types') {
    return (
      <div className="flex h-full flex-col">
        <div className="flex items-center gap-1 border-b px-3 py-2">
          <ViewToggle view={view} onChange={setView} />
        </div>
        <div className="flex-1 overflow-y-auto">
          <PendingTypesInbox />
        </div>
      </div>
    )
  }

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center gap-1 border-b px-3 py-2">
        <ViewToggle view={view} onChange={setView} />
      </div>
      <div className="flex-1">
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
      </div>
    </div>
  )
}

function ViewToggle({ view, onChange }: { view: View; onChange: (v: View) => void }) {
  return (
    <div className="flex items-center gap-1">
      <button
        onClick={() => onChange('conflicts')}
        className={`rounded px-3 py-1 text-sm font-medium transition-colors ${
          view === 'conflicts'
            ? 'bg-foreground text-background'
            : 'text-muted-foreground hover:text-foreground'
        }`}
      >
        Conflicts
      </button>
      <button
        onClick={() => onChange('pending_types')}
        className={`rounded px-3 py-1 text-sm font-medium transition-colors ${
          view === 'pending_types'
            ? 'bg-foreground text-background'
            : 'text-muted-foreground hover:text-foreground'
        }`}
      >
        Pending types
      </button>
    </div>
  )
}
