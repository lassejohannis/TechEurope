import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  ChevronRight,
  ChevronDown,
  User,
  Building2,
  Package,
  FileText,
  FolderOpen,
  CheckSquare,
  MessageSquare,
  Loader2,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { useUiStore } from '@/store/ui'
import type { LucideIcon } from 'lucide-react'

interface VfsNode {
  entity_id: string
  path: string
  type: string
  content: { canonical_name?: string; [key: string]: unknown }
}

interface VfsListResponse {
  children: VfsNode[]
  total: number
}

interface VfsSection {
  path: string
  label: string
  types: string[]
  items: Array<{ entityId: string; label: string; Icon: LucideIcon; type: string }>
}

const TYPE_ICON: Record<string, LucideIcon> = {
  person: User,
  organization: Building2,
  company: Building2,
  customer: Building2,
  product: Package,
  document: FileText,
  policy: FileText,
  project: FolderOpen,
  task: CheckSquare,
  communication: MessageSquare,
}

const SECTION_DEFS: Array<{ path: string; label: string; types: string[] }> = [
  { path: '/people', label: 'People', types: ['person'] },
  { path: '/companies', label: 'Companies', types: ['organization', 'company', 'customer'] },
  { path: '/content', label: 'Content', types: ['communication', 'document', 'policy'] },
  { path: '/work', label: 'Work', types: ['project', 'task', 'product'] },
]

function pluralSegment(type: string): string {
  if (type.endsWith('y') && !/[aeiou]y$/.test(type)) return `${type.slice(0, -1)}ies`
  if (type.endsWith('s') || type.endsWith('x') || type.endsWith('z')) return `${type}es`
  return `${type}s`
}

async function fetchType(type: string): Promise<VfsNode[]> {
  const seg = pluralSegment(type)
  try {
    const res = await fetch(`/api/vfs/${seg}`)
    if (!res.ok) return []
    const data: VfsListResponse = await res.json()
    return data.children ?? []
  } catch {
    return []
  }
}

interface Props {
  selectedEntityId: string | null
}

export default function VfsTree({ selectedEntityId }: Props) {
  const navigate = useNavigate()
  const { expandedPaths, togglePath } = useUiStore()
  const [sections, setSections] = useState<VfsSection[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false

    async function load() {
      setLoading(true)
      const allTypes = SECTION_DEFS.flatMap((s) => s.types)
      const results = await Promise.all(allTypes.map((t) => fetchType(t).then((nodes) => ({ type: t, nodes }))))

      if (cancelled) return

      const nodesByType = new Map(results.map((r) => [r.type, r.nodes]))

      const built: VfsSection[] = SECTION_DEFS.map((def) => ({
        ...def,
        items: def.types.flatMap((type) =>
          (nodesByType.get(type) ?? []).map((node) => ({
            entityId: node.entity_id,
            label: node.content?.canonical_name ?? node.entity_id,
            Icon: TYPE_ICON[type] ?? FileText,
            type,
          })),
        ),
      }))

      setSections(built)
      setLoading(false)
    }

    void load()
    return () => { cancelled = true }
  }, [])

  return (
    <div className="flex flex-col">
      <div className="border-b px-3 py-2">
        <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
          Context Base
        </p>
      </div>

      {loading && (
        <div className="flex items-center gap-2 p-4 text-sm text-muted-foreground">
          <Loader2 className="size-3.5 animate-spin" />
          Loading…
        </div>
      )}

      {!loading && sections.every((s) => s.items.length === 0) && (
        <div className="p-6 text-center text-sm text-muted-foreground">
          No entities found. Ingest some data first.
        </div>
      )}

      <ul className="flex flex-col py-1">
        {sections.map((section) => {
          if (section.items.length === 0) return null
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
                <span className="ml-auto text-xs text-muted-foreground/60">{section.items.length}</span>
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
