import { useParams } from 'react-router-dom'
import VfsTree from './VfsTree'
import EntityDetail from './EntityDetail'
import ActionPanel from './ActionPanel'

export default function BrowsePage() {
  const { entityId } = useParams<{ entityId: string }>()
  const activeId = entityId ? decodeURIComponent(entityId) : null

  return (
    <div className="workspace">
      <VfsTree selectedEntityId={activeId} />
      <EntityDetail entityId={activeId} />
      <ActionPanel entityId={activeId} />
    </div>
  )
}
