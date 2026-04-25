import { useParams } from 'react-router-dom'
import ConflictInbox from './ConflictInbox'
import ConflictDetail from './ConflictDetail'
import DecisionPanel from './DecisionPanel'

export default function ReviewPage() {
  const { conflictId } = useParams<{ conflictId: string }>()
  const activeId = conflictId ? decodeURIComponent(conflictId) : null

  return (
    <div className="workspace review">
      <ConflictInbox activeId={activeId} />
      <ConflictDetail conflictId={activeId} />
      <DecisionPanel conflictId={activeId} />
    </div>
  )
}
