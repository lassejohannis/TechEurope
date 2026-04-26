import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { FileText, Loader2 } from 'lucide-react'
import type { LucideIcon } from 'lucide-react'

// ── Data types ───────────────────────────────────────────────────────────────

interface VfsNode {
  entity_id: string
  path: string
  type: string
  content: { canonical_name?: string; [key: string]: unknown }
}
interface VfsListResponse { children: VfsNode[]; total: number }
interface VfsSection {
  path: string; label: string; types: string[]; count?: number
  items: Array<{ entityId: string; label: string; Icon: LucideIcon; type: string }>
}
interface VfsSectionsResponse {
  sections: Array<{ path: string; label: string; types: string[]; count?: number }>
  total_sections: number; total_entities: number
}

const UUIDISH_PATTERN =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i

function isUuidish(value: string): boolean {
  return UUIDISH_PATTERN.test(value.trim())
}

function pickNodeLabel(node: VfsNode, type: string): string {
  const canonical = String(node.content?.canonical_name ?? '').trim()
  if (type === 'communication' && canonical && isUuidish(canonical)) {
    const subject = String(node.content?.subject ?? '').trim()
    if (subject && !isUuidish(subject)) return subject
    const sentAt = String(node.content?.date ?? node.content?.sent_at ?? '').trim()
    if (sentAt) return `Communication (${sentAt.slice(0, 10)})`
    return `Communication ${canonical.slice(0, 8)}`
  }
  return canonical || node.entity_id
}

// ── Fetch helpers ────────────────────────────────────────────────────────────

function pluralSegment(type: string): string {
  if (type.endsWith('y') && !/[aeiou]y$/.test(type)) return `${type.slice(0, -1)}ies`
  if (type.endsWith('s') || type.endsWith('x') || type.endsWith('z')) return `${type}es`
  return `${type}s`
}
async function fetchSections() {
  try { const r = await fetch('/api/vfs/_sections'); if (!r.ok) return []
    const d: VfsSectionsResponse = await r.json(); return d.sections ?? []
  } catch { return [] }
}
async function fetchType(type: string): Promise<VfsNode[]> {
  try { const r = await fetch(`/api/vfs/${pluralSegment(type)}`); if (!r.ok) return []
    const d: VfsListResponse = await r.json(); return d.children ?? []
  } catch { return [] }
}
async function fetchBrowseTree() {
  const defs = await fetchSections()
  const types = defs.flatMap(s => s.types)
  const results = await Promise.all(types.map(t => fetchType(t).then(nodes => ({ t, nodes }))))

  const byType = new Map(results.map(r => [r.t, r.nodes]))
  const sections: VfsSection[] = defs.map(def => ({
    ...def,
    items: def.types.flatMap(type =>
      (byType.get(type) ?? []).map(node => ({
        entityId: node.entity_id,
        label: pickNodeLabel(node, type),
        Icon: FileText, type,
      }))
    ),
  }))
  return { sections, totalEntities: sections.reduce((s, sec) => s + sec.items.length, 0) }
}
async function triggerRefresh() {
  try {
    const r = await fetch('/api/admin/refresh-browse-tree', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ limit: 250, infer_mappings: true, auto_approve_mappings: true, llm_extract: false }),
    })
    if (!r.ok) return false
    await r.json().catch(() => ({})); return true
  } catch { return false }
}

// ── Design tokens ────────────────────────────────────────────────────────────
// [backDark, frontLight, frontDark, accentColor]
const PALETTE: Record<string, [string, string, string, string]> = {
  person:        ['#1d4ed8', '#93c5fd', '#60a5fa', '#3b82f6'],
  company:       ['#c2410c', '#fdba74', '#fb923c', '#f97316'],
  document:      ['#334155', '#94a3b8', '#64748b', '#64748b'],
  event:         ['#6d28d9', '#c4b5fd', '#a78bfa', '#8b5cf6'],
  task:          ['#065f46', '#6ee7b7', '#34d399', '#10b981'],
  email:         ['#991b1b', '#fca5a5', '#f87171', '#ef4444'],
  policy:        ['#9d174d', '#f9a8d4', '#f472b6', '#ec4899'],
  ticket:        ['#312e81', '#a5b4fc', '#818cf8', '#6366f1'],
  communication: ['#7c2d12', '#fdba74', '#fb923c', '#f97316'],
}

// ── Folder SVG illustration ──────────────────────────────────────────────────

function FolderSVG({ type }: { type: string }) {
  const pal = PALETTE[type] ?? PALETTE.document
  const [back, fl, fd] = pal
  const id = `fold-${type}`
  return (
    <svg viewBox="0 0 200 130" fill="none" style={{ width: '100%', display: 'block' }}>
      <defs>
        <linearGradient id={`${id}-front`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={fl} />
          <stop offset="100%" stopColor={fd} />
        </linearGradient>
        <linearGradient id={`${id}-back`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={back} stopOpacity="0.9" />
          <stop offset="100%" stopColor={back} stopOpacity="0.7" />
        </linearGradient>
        <filter id={`${id}-shadow`}>
          <feDropShadow dx="0" dy="4" stdDeviation="6" floodColor={fd} floodOpacity="0.35" />
        </filter>
        <filter id={`${id}-backshadow`}>
          <feDropShadow dx="0" dy="2" stdDeviation="3" floodColor={back} floodOpacity="0.3" />
        </filter>
      </defs>
      {/* Back layer */}
      <g filter={`url(#${id}-backshadow)`}>
        <path d="M18 38 Q18 28 28 28 H72 Q78 28 80 34 L86 42 H18 Z" fill={`url(#${id}-back)`} />
        <rect x="14" y="40" width="172" height="76" rx="10" fill={`url(#${id}-back)`} />
      </g>
      {/* Front layer */}
      <g filter={`url(#${id}-shadow)`}>
        <rect x="6" y="50" width="172" height="72" rx="10" fill={`url(#${id}-front)`} />
        <rect x="6" y="50" width="172" height="24" rx="10" fill="white" opacity="0.18" />
        <rect x="6" y="50" width="172" height="72" rx="10" stroke="white" strokeWidth="1" strokeOpacity="0.2" fill="none" />
      </g>
    </svg>
  )
}

// ── Folder card ──────────────────────────────────────────────────────────────

function FolderCard({
  section, isOpen, onClick,
}: {
  section: VfsSection; isOpen: boolean; onClick: () => void
}) {
  const [hovered, setHovered] = useState(false)
  const primaryType = section.types[0] ?? 'document'
  const accentColor = (PALETTE[primaryType] ?? PALETTE.document)[3]

  return (
    <button
      onClick={onClick}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      style={{
        background: '#fff',
        border: isOpen ? `1.5px solid ${accentColor}66` : '1.5px solid transparent',
        borderRadius: 18,
        padding: '16px 16px 14px',
        textAlign: 'left',
        cursor: 'pointer',
        boxShadow: hovered
          ? '0 8px 30px rgba(0,0,0,0.10)'
          : isOpen
            ? '0 4px 20px rgba(0,0,0,0.08)'
            : '0 1px 6px rgba(0,0,0,0.06)',
        transform: hovered ? 'translateY(-2px)' : 'none',
        transition: 'all .18s ease',
        outline: 'none',
        width: '100%',
      }}
    >
      <div style={{ position: 'relative', marginBottom: 4 }}>
        <FolderSVG type={primaryType} />
      </div>
      <p style={{
        fontSize: 15,
        fontWeight: 600,
        color: '#0a0a0a',
        marginTop: 6,
        marginBottom: 0,
        lineHeight: 1.25,
        overflowWrap: 'anywhere',
      }}
      >
        {section.label}
      </p>
      <p style={{
        fontSize: 12.5,
        color: '#aaa',
        marginTop: 2,
        marginBottom: 0,
        lineHeight: 1.25,
        overflowWrap: 'anywhere',
      }}
      >
        {section.count ?? section.items.length} entities
      </p>
    </button>
  )
}

// ── Finder-style file row ────────────────────────────────────────────────────

function FileRow({
  item, sectionType, isActive, onClick, delay,
}: {
  item: VfsSection['items'][number]
  sectionType: string
  isActive: boolean
  onClick: () => void
  delay: number
}) {
  const [hovered, setHovered] = useState(false)
  const pal = PALETTE[sectionType] ?? PALETTE.document

  return (
    <div
      className="row-in"
      data-entity-id={item.entityId}
      onClick={onClick}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      style={{
        display: 'flex', alignItems: 'center', gap: 10,
        padding: '7px 10px', borderRadius: 8, cursor: 'pointer',
        background: isActive ? `${pal[3]}14` : hovered ? '#f0f0f0' : 'transparent',
        outline: isActive ? `1.5px solid ${pal[3]}44` : 'none',
        transition: 'background .1s',
        animationDelay: `${delay}ms`,
      }}
    >
      {/* Document icon */}
      <svg width="18" height="20" viewBox="0 0 18 22" fill="none" style={{ flexShrink: 0 }}>
        <rect x="1" y="1" width="14" height="19" rx="3" fill={`${pal[1]}40`} stroke={pal[3]} strokeWidth="1.2" />
        <path d="M10 1v5h5" stroke={pal[3]} strokeWidth="1.2" strokeLinejoin="round" />
        <rect x="3.5" y="9" width="9" height="1.5" rx="0.75" fill={pal[3]} opacity="0.5" />
        <rect x="3.5" y="12" width="6.5" height="1.5" rx="0.75" fill={pal[3]} opacity="0.35" />
      </svg>
      <span style={{
        flex: 1, fontSize: 13, fontWeight: isActive ? 500 : 400, color: '#0a0a0a',
        overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
      }}>
        {item.label}
      </span>
      <span style={{ fontSize: 11, color: '#bbb', flexShrink: 0, textTransform: 'capitalize' }}>
        {sectionType}
      </span>
      {isActive && (
        <svg width="12" height="12" viewBox="0 0 12 12" fill="none" style={{ flexShrink: 0 }}>
          <path d="M4.5 3l3 3-3 3" stroke={pal[3]} strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      )}
    </div>
  )
}

// ── Main component ───────────────────────────────────────────────────────────

export default function VfsTree({ selectedEntityId }: { selectedEntityId: string | null }) {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [openSection, setOpenSection] = useState<string | null>(null)
  const fileListRef = useRef<HTMLDivElement | null>(null)

  const treeQuery = useQuery({
    queryKey: ['browse', 'tree'],
    queryFn: fetchBrowseTree,
    staleTime: 10 * 60_000,
    gcTime: 60 * 60_000,
    refetchOnMount: false,
    refetchOnWindowFocus: false, refetchOnReconnect: false,
  })

  const sections = treeQuery.data?.sections ?? []
  const loading = treeQuery.isPending
  const totalEntities = treeQuery.data?.totalEntities ?? 0
  const currentSection = sections.find(s => s.path === openSection) ?? null

  // Auto-open (or switch to) the folder containing the active entity
  useEffect(() => {
    if (!selectedEntityId) return
    const sec = sections.find(s => s.items.some(i => i.entityId === selectedEntityId))
    if (sec && sec.path !== openSection) setOpenSection(sec.path)
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedEntityId, sections])

  // Keep the active row clearly visible above the bottom chat area.
  useEffect(() => {
    if (!selectedEntityId || !fileListRef.current) return
    const activeEl = fileListRef.current.querySelector<HTMLElement>(`[data-entity-id="${selectedEntityId}"]`)
    if (!activeEl) return
    requestAnimationFrame(() => {
      activeEl.scrollIntoView({ block: 'center', behavior: 'smooth' })
    })
  }, [selectedEntityId, openSection, currentSection?.path])

  // Background refresh only when tree is empty (bootstrap mode).
  useEffect(() => {
    if (loading || totalEntities > 0) return
    const KEY = 'browse_refresh_last_run'
    const last = Number(window.sessionStorage.getItem(KEY) ?? '0')
    if (Date.now() - last < 10 * 60_000) return
    window.sessionStorage.setItem(KEY, String(Date.now()))
    void triggerRefresh().then(ok => {
      if (ok) queryClient.invalidateQueries({ queryKey: ['browse', 'tree'] })
    })
  }, [loading, totalEntities, queryClient])

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', overflow: 'hidden' }}>
      {/* ── Topbar / breadcrumb ── */}
      <div style={{
        height: 52, flexShrink: 0, display: 'flex', alignItems: 'center',
        padding: '0 20px', borderBottom: '1px solid #e5e5e5', background: '#fff', gap: 8,
      }}>
        {openSection ? (
          <>
            <button
              onClick={() => { setOpenSection(null) }}
              style={{ fontSize: 14, fontWeight: 500, color: '#aaa', background: 'none', border: 'none', cursor: 'pointer', padding: 0 }}
            >
              Context vaults
            </button>
            <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
              <path d="M5 3l4 4-4 4" stroke="#ccc" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
            <span style={{ fontSize: 14, fontWeight: 600, color: '#0a0a0a' }}>{currentSection?.label}</span>
          </>
        ) : (
          <span style={{ fontSize: 14, fontWeight: 600, color: '#0a0a0a' }}>Context vaults</span>
        )}
        <span style={{
          marginLeft: 'auto', fontSize: 11.5, color: '#aaa',
          background: '#f3f3f3', borderRadius: 20, padding: '2px 10px',
        }}>
          {loading ? '…' : `${totalEntities} entities`}
        </span>
      </div>

      {/* ── Scroll area ── */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '24px 22px 24px', background: '#f5f5f7' }}>

        {loading && (
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, color: '#aaa', fontSize: 13 }}>
            <Loader2 size={14} style={{ animation: 'spin 1s linear infinite' }} />
            Loading…
          </div>
        )}

        {!loading && totalEntities === 0 && (
          <div style={{
            border: '1.5px dashed #e5e5e5', borderRadius: 14,
            padding: '48px 24px', textAlign: 'center', color: '#ccc', fontSize: 13,
          }}>
            No entities found. Ingest some data first.
          </div>
        )}

        {/* ── Folder grid ── */}
        {!loading && !openSection && sections.length > 0 && (
          <div
            className="fade-up"
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))',
              gap: 14,
              paddingBottom: 24,
            }}
          >
            {sections.map(sec => (
              <FolderCard
                key={sec.path}
                section={sec}
                isOpen={false}
                onClick={() => setOpenSection(sec.path)}
              />
            ))}
          </div>
        )}

        {/* ── File list (Finder list view) ── */}
        {!loading && openSection && currentSection && (
          <div
            className="fade-up"
            style={{
              background: '#fff', borderRadius: 14, overflow: 'hidden',
              boxShadow: '0 1px 6px rgba(0,0,0,0.06)', marginBottom: 24,
            }}
          >
            {/* Column header */}
            <div style={{
              display: 'flex', alignItems: 'center', gap: 10,
              padding: '8px 10px', borderBottom: '1px solid #f0f0f0', background: '#fafafa',
            }}>
              <span style={{ flex: 1, fontSize: 11, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', color: '#ccc', paddingLeft: 28 }}>
                Name
              </span>
              <span style={{ fontSize: 11, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', color: '#ccc', width: 70, textAlign: 'right' }}>
                Typ
              </span>
              <span style={{ width: 20 }} />
            </div>

            {currentSection.items.length === 0 ? (
              <p style={{ padding: '24px 16px', fontSize: 13, color: '#ccc', textAlign: 'center' }}>
                Dieser Ordner ist leer.
              </p>
            ) : (
              <div ref={fileListRef} style={{ padding: '4px 6px' }}>
                {currentSection.items.map((item, i) => (
                  <FileRow
                    key={item.entityId}
                    item={item}
                    sectionType={currentSection.types[0] ?? 'document'}
                    isActive={selectedEntityId === item.entityId}
                    onClick={() => navigate(`/browse/${encodeURIComponent(item.entityId)}`)}
                    delay={i * 40}
                  />
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
