import { useNavigate } from 'react-router-dom'
import { ChevronRight, ChevronDown, User, Building2, Package, FileText, FolderOpen, CheckSquare, MessageSquare } from 'lucide-react'
import { cn } from '@/lib/utils'
import { useUiStore } from '@/store/ui'
import type { LucideIcon } from 'lucide-react'

interface VfsItem {
  path: string
  entityId: string
  label: string
  Icon: LucideIcon
  type: string
}

interface VfsSection {
  path: string
  label: string
  items: VfsItem[]
}

// Static mock VFS structure — replaced by real API when backend is live
const VFS_SECTIONS: VfsSection[] = [
  {
    path: '/static',
    label: 'Static',
    items: [
      { path: '/static/people', entityId: 'person:alice-schmidt', label: 'Alice Schmidt', Icon: User, type: 'person' },
      { path: '/static/people', entityId: 'person:bob-mueller', label: 'Bob Müller', Icon: User, type: 'person' },
      { path: '/static/customers', entityId: 'customer:acme-gmbh', label: 'Acme GmbH', Icon: Building2, type: 'customer' },
      { path: '/static/customers', entityId: 'customer:techcorp-ag', label: 'TechCorp AG', Icon: Building2, type: 'customer' },
      { path: '/static/products', entityId: 'product:core-platform', label: 'Core Platform', Icon: Package, type: 'product' },
    ],
  },
  {
    path: '/procedural',
    label: 'Procedural',
    items: [
      { path: '/procedural/policies', entityId: 'policy:data-protection', label: 'Data Protection Policy', Icon: FileText, type: 'policy' },
      { path: '/procedural/policies', entityId: 'policy:information-security', label: 'Information Security Policy', Icon: FileText, type: 'policy' },
    ],
  },
  {
    path: '/trajectory',
    label: 'Trajectory',
    items: [
      { path: '/trajectory/projects', entityId: 'project:q3-expansion', label: 'Q3 Expansion', Icon: FolderOpen, type: 'project' },
      { path: '/trajectory/tasks', entityId: 'task:onboarding-flow', label: 'Onboarding Flow', Icon: CheckSquare, type: 'task' },
      { path: '/trajectory/communications', entityId: 'communication:acme-thread-apr', label: 'Acme Apr Thread', Icon: MessageSquare, type: 'communication' },
    ],
  },
]

interface Props {
  selectedEntityId: string | null
}

export default function VfsTree({ selectedEntityId }: Props) {
  const navigate = useNavigate()
  const { expandedPaths, togglePath } = useUiStore()

  return (
    <div className="flex flex-col">
      <div className="border-b px-3 py-2">
        <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
          Context Base
        </p>
      </div>

      {VFS_SECTIONS.length === 0 && (
        <div className="flex flex-col items-center gap-2 p-6 text-center">
          <p className="text-sm text-muted-foreground">
            Your context base is organized here. Select a path to explore entities and facts.
          </p>
        </div>
      )}

      <ul className="flex flex-col py-1">
        {VFS_SECTIONS.map((section) => {
          const isExpanded = expandedPaths.has(section.path)
          return (
            <li key={section.path}>
              <button
                onClick={() => togglePath(section.path)}
                className="flex w-full items-center gap-1.5 px-3 py-1.5 text-left text-sm font-medium hover:bg-muted/50 transition-colors"
              >
                {isExpanded ? (
                  <ChevronDown className="size-3.5 shrink-0 text-muted-foreground" />
                ) : (
                  <ChevronRight className="size-3.5 shrink-0 text-muted-foreground" />
                )}
                <span className="text-muted-foreground">{section.label}</span>
              </button>

              {isExpanded && (
                <ul className="flex flex-col">
                  {section.items.map((item) => {
                    const isActive = selectedEntityId === item.entityId
                    return (
                      <li key={item.entityId}>
                        <button
                          onClick={() => navigate(`/browse/${encodeURIComponent(item.entityId)}`)}
                          className={cn(
                            'flex w-full items-center gap-2 py-1.5 pl-8 pr-3 text-left text-sm transition-colors hover:bg-muted/50',
                            isActive && 'bg-muted font-medium text-foreground',
                          )}
                        >
                          <item.Icon className="size-3.5 shrink-0 text-muted-foreground" />
                          <span className="truncate">{item.label}</span>
                        </button>
                      </li>
                    )
                  })}
                </ul>
              )}
            </li>
          )
        })}
      </ul>
    </div>
  )
}
