import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import Icon from '@/components/qontext/icon'
import { INAZUMA, type MockTreeItem, type MockTreeFolder, type MockTreeEntity } from '@/lib/inazuma-mock'

const CONF_COLORS: Record<string, string> = {
  high:     'var(--conf-high)',
  med:      'var(--conf-med)',
  low:      'var(--conf-low)',
  conflict: 'var(--conf-conflict)',
}

function entityIcon(type: string) {
  if (type === 'person')   return 'user'
  if (type === 'customer') return 'briefcase'
  if (type === 'product')  return 'box'
  if (type === 'policy')   return 'shield'
  if (type === 'project')  return 'target'
  return 'file'
}

function TreeRow({
  node, depth = 0, openSet, onToggle, activeId, onSelect,
}: {
  node: MockTreeItem
  depth?: number
  openSet: Set<string>
  onToggle: (id: string) => void
  activeId: string | null
  onSelect: (id: string) => void
}) {
  if (node.kind === 'section') {
    return <div className="tree-section">{node.label}</div>
  }

  const folder = node as MockTreeFolder
  const entity = node as MockTreeEntity
  const isOpen   = node.kind === 'folder' && openSet.has(folder.id)
  const isActive = node.kind === 'entity' && activeId === entity.id
  const hasChildren = node.kind === 'folder' && (folder.children?.length ?? 0) > 0

  const handleClick = () => {
    if (node.kind === 'folder') onToggle(folder.id)
    else onSelect(entity.id)
  }

  return (
    <>
      <div
        className={`tree-row${isActive ? ' active' : ''}`}
        style={{ paddingLeft: 8 + depth * 14 }}
        onClick={handleClick}
        role="button"
        tabIndex={0}
        onKeyDown={(e) => e.key === 'Enter' && handleClick()}
      >
        <span className="tree-caret">
          {hasChildren
            ? <Icon name={isOpen ? 'chevron-down' : 'chevron-right'} size={11} />
            : null}
        </span>
        <span className="tree-icon">
          {node.kind === 'folder'
            ? <Icon name={folder.icon ?? 'folder'} size={14} />
            : <Icon name={entityIcon(entity.type)} size={14} />}
        </span>
        <span className="tree-label">{node.kind === 'folder' ? folder.label : entity.label}</span>
        {node.kind === 'entity' && entity.confidence && (
          <span className="conf-dot" style={{ background: CONF_COLORS[entity.confidence] }} />
        )}
        {node.kind === 'folder' && folder.count != null && (
          <span className="tree-count">{folder.count}</span>
        )}
      </div>
      {hasChildren && isOpen && folder.children!.map((child) => (
        <TreeRow
          key={'id' in child ? child.id : child.label}
          node={child}
          depth={depth + 1}
          openSet={openSet}
          onToggle={onToggle}
          activeId={activeId}
          onSelect={onSelect}
        />
      ))}
    </>
  )
}

interface Props {
  selectedEntityId: string | null
}

export default function VfsTree({ selectedEntityId }: Props) {
  const navigate = useNavigate()
  const [openSet, setOpenSet] = useState(() => new Set(['fold:cust', 'fold:people', 'fold:policies', 'fold:projects']))
  const [q, setQ] = useState('')

  const handleToggle = (id: string) => {
    setOpenSet((prev) => {
      const next = new Set(prev)
      next.has(id) ? next.delete(id) : next.add(id)
      return next
    })
  }

  const handleSelect = (id: string) => {
    navigate(`/browse/${encodeURIComponent(id)}`)
  }

  return (
    <div className="col">
      <div className="panel-header sticky">
        <Icon name="folder" size={14} className="muted" />
        <span className="panel-title">Virtual File System</span>
        <span className="spacer" />
        <button className="action-btn" style={{ width: 'auto', padding: '4px 6px', background: 'transparent', border: 'none' }} title="New entity">
          <Icon name="plus" size={14} />
        </button>
      </div>

      <div className="tree-search">
        <Icon name="search" size={13} className="muted" />
        <input
          placeholder="Search files…"
          value={q}
          onChange={(e) => setQ(e.target.value)}
        />
        <span className="kbd-chip">/</span>
      </div>

      <div className="panel-body">
        <div className="tree">
          {INAZUMA.tree.map((node) => (
            <TreeRow
              key={'id' in node ? node.id : node.label}
              node={node}
              openSet={openSet}
              onToggle={handleToggle}
              activeId={selectedEntityId}
              onSelect={handleSelect}
            />
          ))}
        </div>
      </div>
    </div>
  )
}
