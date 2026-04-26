import { useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import {
  ChevronRight,
  ChevronDown,
  FileText,
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
  count?: number
  items: Array<{ entityId: string; label: string; Icon: LucideIcon; type: string }>
}

interface VfsSectionsResponse {
  sections: Array<{
    path: string
    label: string
    types: string[]
    count?: number
  }>
  total_sections: number
  total_entities: number
}

function pluralSegment(type: string): string {
  if (type.endsWith('y') && !/[aeiou]y$/.test(type)) return `${type.slice(0, -1)}ies`
  if (type.endsWith('s') || type.endsWith('x') || type.endsWith('z')) return `${type}es`
  return `${type}s`
}

async function fetchSections(): Promise<Array<{ path: string; label: string; types: string[]; count?: number }>> {
  try {
    const res = await fetch('/api/vfs/_sections')
    if (!res.ok) return []
    const data: VfsSectionsResponse = await res.json()
    return data.sections ?? []
  } catch {
    return []
  }
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

interface BrowseTreeData {
  sections: VfsSection[]
  totalEntities: number
}

async function fetchBrowseTree(): Promise<BrowseTreeData> {
  const sectionDefs = await fetchSections()
  const allTypes = sectionDefs.flatMap((s) => s.types)
  const results = await Promise.all(allTypes.map((t) => fetchType(t).then((nodes) => ({ type: t, nodes }))))
  const nodesByType = new Map(results.map((r) => [r.type, r.nodes]))

  const sections: VfsSection[] = sectionDefs.map((def) => ({
    ...def,
    items: def.types.flatMap((type) =>
      (nodesByType.get(type) ?? []).map((node) => ({
        entityId: node.entity_id,
        label: node.content?.canonical_name ?? node.entity_id,
        Icon: FileText,
        type,
      })),
    ),
  }))
  const totalEntities = sections.reduce((sum, section) => sum + section.items.length, 0)
  return { sections, totalEntities }
}

async function triggerBrowseRefresh(): Promise<boolean> {
  try {
    const res = await fetch('/api/admin/refresh-browse-tree', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        limit: 250,
        infer_mappings: true,
        auto_approve_mappings: true,
        llm_extract: false,
      }),
    })
    // In non-admin/authenticated contexts we silently skip.
    if (!res.ok) return false
    await res.json().catch(() => ({}))
    return true
  } catch {
    // Best-effort background refresh only.
    return false
  }
}

interface Props {
  selectedEntityId: string | null
}

export default function VfsTree({ selectedEntityId }: Props) {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { expandedPaths, togglePath } = useUiStore()
  const treeQuery = useQuery({
    queryKey: ['browse', 'tree'],
    queryFn: fetchBrowseTree,
    staleTime: 5 * 60_000,
    gcTime: 30 * 60_000,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
    refetchOnMount: false,
  })
  const sections = treeQuery.data?.sections ?? []
  const loading = treeQuery.isPending
  const totalEntities = treeQuery.data?.totalEntities ?? 0
  const hasAnyEntities = totalEntities > 0

  useEffect(() => {
    const key = 'browse_refresh_last_run'
    const minIntervalMs = 60_000
    const lastRun = Number(window.sessionStorage.getItem(key) ?? '0')
    if (Date.now() - lastRun < minIntervalMs) return
    window.sessionStorage.setItem(key, String(Date.now()))

    void (async () => {
      const refreshed = await triggerBrowseRefresh()
      if (refreshed) {
        await queryClient.invalidateQueries({ queryKey: ['browse', 'tree'] })
      }
    })()
  }, [queryClient])

  return (
    <div className="flex h-full flex-col bg-gradient-to-b from-background to-muted/20">
      <div className="sticky top-0 z-10 border-b bg-background/95 px-4 py-3 backdrop-blur supports-[backdrop-filter]:bg-background/80">
        <p className="text-xs font-semibold uppercase tracking-[0.14em] text-muted-foreground">
          Context Base
        </p>
        <div className="mt-2 flex items-end justify-between gap-2">
          <p className="text-sm font-medium text-foreground">Knowledge explorer</p>
          <span className="rounded-full border px-2 py-0.5 text-xs text-muted-foreground">
            {loading ? '...' : `${totalEntities} entities`}
          </span>
        </div>
        <p className="mt-1 text-xs text-muted-foreground">
          Browse by domain and drill into entities.
        </p>
      </div>

      {loading && (
        <div className="flex items-center gap-2 px-4 py-5 text-sm text-muted-foreground">
          <Loader2 className="size-4 animate-spin" />
          Loading entities...
        </div>
      )}

      {!loading && !hasAnyEntities && (
        <div className="m-4 rounded-xl border border-dashed bg-background/70 p-6 text-center text-sm text-muted-foreground">
          No entities found. Ingest some data first.
        </div>
      )}

      <ul className="flex flex-col gap-2 px-3 py-3">
        {sections.map((section) => {
          const isExpanded = expandedPaths.has(section.path)
          return (
            <li key={section.path} className="overflow-hidden rounded-xl border bg-background/90 shadow-sm">
              <button
                onClick={() => togglePath(section.path)}
                className="flex w-full items-center gap-2 px-3 py-2.5 text-left text-sm font-medium transition-colors hover:bg-muted/60"
              >
                {isExpanded ? (
                  <ChevronDown className="size-3.5 shrink-0 text-muted-foreground" />
                ) : (
                  <ChevronRight className="size-3.5 shrink-0 text-muted-foreground" />
                )}
                <span className="text-foreground/90">{section.label}</span>
                <span className="ml-auto rounded-full bg-muted px-2 py-0.5 text-xs text-muted-foreground">
                  {section.items.length}
                </span>
              </button>

              {isExpanded && (
                <ul className="flex flex-col border-t bg-muted/20">
                  {section.items.map((item) => {
                    const isActive = selectedEntityId === item.entityId
                    return (
                      <li key={item.entityId}>
                        <button
                          onClick={() => navigate(`/browse/${encodeURIComponent(item.entityId)}`)}
                          className={cn(
                            'flex w-full items-center gap-2 py-2 pl-8 pr-3 text-left text-sm transition-colors hover:bg-background/70',
                            isActive && 'bg-background font-medium text-foreground',
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

      <div className="mt-auto px-4 py-3 text-xs text-muted-foreground">
        {hasAnyEntities
          ? 'Tip: Expand a section and choose an entity to inspect details.'
          : 'Ingest data to populate this navigation tree.'}
      </div>
    </div>
  )
}
