import { useParams } from 'react-router-dom'
import ThreeColumnLayout from '@/components/layout/ThreeColumnLayout'
import VfsTree from './VfsTree'
import EntityDetail from './EntityDetail'
import ActionPanel from './ActionPanel'

export default function BrowsePage() {
  const { entityId } = useParams<{ entityId: string }>()
  const activeId = entityId ? decodeURIComponent(entityId) : null

  return (
    <ThreeColumnLayout
      left={<VfsTree selectedEntityId={activeId} />}
      center={<EntityDetail entityId={activeId} />}
      right={<ActionPanel entityId={activeId} />}
    />
  )
}
