import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'

/* ── Types ──────────────────────────────────────────────────────────────── */

type GraphNode = {
  id: string
  label: string
  type: string
  properties: Record<string, unknown>
}
type GraphEdge = { id: string; source: string; target: string; label: string }
type RenderEdge = {
  id: string
  source: string
  target: string
  label: string
  labels: string[]
  count: number
}
type SimNode = GraphNode & { x: number; y: number; vx: number; vy: number; r: number }
type NeighborMap = Map<string, Set<string>>
type CameraAnim = {
  fromPanX: number
  fromPanY: number
  fromScale: number
  toPanX: number
  toPanY: number
  toScale: number
  startAt: number
  duration: number
}

/* ── Node colours ───────────────────────────────────────────────────────── */

const PALETTE: Record<string, [string, string]> = {
  person:        ['#3b82f6', '#fff'],
  company:       ['#22c55e', '#fff'],
  organization:  ['#22c55e', '#fff'],
  communication: ['#a855f7', '#fff'],
  document:      ['#f97316', '#fff'],
  product:       ['#eab308', '#111'],
  task:          ['#ec4899', '#fff'],
  policy:        ['#14b8a6', '#fff'],
}
const DEFAULT_STYLE: [string, string] = ['#6b7280', '#fff']
function nodeStyle(type: string): [string, string] {
  return PALETTE[type.toLowerCase()] ?? DEFAULT_STYLE
}

function normalizeProperties(properties: Record<string, unknown>): Record<string, unknown> {
  const normalized: Record<string, unknown> = { ...properties }
  for (const [key, value] of Object.entries(normalized)) {
    if (typeof value !== 'string') continue
    const t = value.trim()
    const looksLikeJson =
      (t.startsWith('{') && t.endsWith('}')) ||
      (t.startsWith('[') && t.endsWith(']'))
    if (!looksLikeJson) continue
    try {
      normalized[key] = JSON.parse(t)
    } catch {
      // Keep original string if it is not valid JSON.
    }
  }
  return normalized
}

function previewValue(value: unknown): string {
  if (value == null) return '—'
  if (typeof value === 'string') return value
  if (typeof value === 'number' || typeof value === 'boolean') return String(value)
  if (Array.isArray(value)) return value.join(', ')
  try {
    return JSON.stringify(value)
  } catch {
    return String(value)
  }
}

function isPlainObject(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function flattenProperties(
  value: Record<string, unknown>,
  prefix = '',
): Array<[string, unknown]> {
  const out: Array<[string, unknown]> = []
  for (const [k, v] of Object.entries(value)) {
    const key = prefix ? `${prefix}.${k}` : k
    if (isPlainObject(v)) {
      out.push(...flattenProperties(v, key))
      continue
    }
    out.push([key, v])
  }
  return out
}

const ATTRIBUTE_LABELS: Record<string, string> = {
  entity_type: 'Entity Type',
  aliases: 'Aliases',
  canonical_name: 'Canonical Name',
  id: 'ID',
  last_synced: 'Last Synced',
  emp_id: 'Employee ID',
  'attrs.email': 'Email',
  'attrs.emp_id': 'Employee ID',
  'attrs.vfs_path': 'Profile Path',
}

function formatAttributeLabel(key: string): string {
  const mapped = ATTRIBUTE_LABELS[key]
  if (mapped) return mapped

  const tail = key.split('.').pop() ?? key
  const words = tail.split('_').filter(Boolean)
  if (words.length === 0) return key
  return words
    .map((w) => (w.toLowerCase() === 'id' ? 'ID' : `${w[0].toUpperCase()}${w.slice(1).toLowerCase()}`))
    .join(' ')
}

function dedupeAttributeEntries(entries: Array<[string, unknown]>): Array<[string, unknown]> {
  const seen = new Set<string>()
  const out: Array<[string, unknown]> = []
  for (const [key, value] of entries) {
    const label = formatAttributeLabel(key).toLowerCase()
    const rendered = previewValue(value).trim().toLowerCase()
    const fingerprint = `${label}::${rendered}`
    if (seen.has(fingerprint)) continue
    seen.add(fingerprint)
    out.push([key, value])
  }
  return out
}

/* ── Force simulation ───────────────────────────────────────────────────── */

function initSim(nodes: GraphNode[], edges: GraphEdge[], w: number, h: number): SimNode[] {
  const degree = new Map<string, number>()
  edges.forEach(e => {
    degree.set(e.source, (degree.get(e.source) ?? 0) + 1)
    degree.set(e.target, (degree.get(e.target) ?? 0) + 1)
  })
  const radius = Math.min(w, h) * 0.3
  return nodes.map((n, i) => {
    const angle = (2 * Math.PI * i) / Math.max(nodes.length, 1)
    return {
      ...n,
      x: Math.cos(angle) * radius + (Math.random() - 0.5) * 20,
      y: Math.sin(angle) * radius + (Math.random() - 0.5) * 20,
      vx: 0,
      vy: 0,
      r: Math.min(38, 16 + (degree.get(n.id) ?? 0) * 1.6),
    }
  })
}

function tick(nodes: SimNode[], edges: GraphEdge[], alpha: number) {
  const REPULSION = 4000
  const SPRING_K  = 0.05
  const IDEAL_LEN = 90
  const GRAVITY   = 0.004

  for (let i = 0; i < nodes.length; i++) {
    for (let j = i + 1; j < nodes.length; j++) {
      const a = nodes[i], b = nodes[j]
      const dx = a.x - b.x || 0.01, dy = a.y - b.y || 0.01
      const d  = Math.sqrt(dx * dx + dy * dy)
      const f  = (REPULSION / (d * d)) * alpha
      a.vx += (dx / d) * f; a.vy += (dy / d) * f
      b.vx -= (dx / d) * f; b.vy -= (dy / d) * f
    }
  }

  const byId = new Map(nodes.map(n => [n.id, n]))
  for (const e of edges) {
    const a = byId.get(e.source), b = byId.get(e.target)
    if (!a || !b) continue
    const dx = b.x - a.x, dy = b.y - a.y
    const d  = Math.sqrt(dx * dx + dy * dy) || 1
    const f  = (d - IDEAL_LEN) * SPRING_K * alpha
    a.vx += (dx / d) * f; a.vy += (dy / d) * f
    b.vx -= (dx / d) * f; b.vy -= (dy / d) * f
  }

  for (const n of nodes) {
    n.vx += -n.x * GRAVITY * alpha
    n.vy += -n.y * GRAVITY * alpha
    n.vx *= 0.82; n.vy *= 0.82
    n.x  += n.vx;  n.y  += n.vy
  }
}

function buildNeighborMap(edges: GraphEdge[]): NeighborMap {
  const map: NeighborMap = new Map()
  for (const e of edges) {
    if (!map.has(e.source)) map.set(e.source, new Set())
    if (!map.has(e.target)) map.set(e.target, new Set())
    map.get(e.source)!.add(e.target)
    map.get(e.target)!.add(e.source)
  }
  return map
}

function bundleEdges(edges: GraphEdge[]): { simEdges: GraphEdge[]; renderEdges: RenderEdge[] } {
  const grouped = new Map<string, { source: string; target: string; labels: string[] }>()
  for (const e of edges) {
    const k = `${e.source}→${e.target}`
    const prev = grouped.get(k)
    if (prev) {
      prev.labels.push(e.label)
    } else {
      grouped.set(k, { source: e.source, target: e.target, labels: [e.label] })
    }
  }

  const renderEdges: RenderEdge[] = []
  const simEdges: GraphEdge[] = []
  let i = 0
  for (const [key, group] of grouped.entries()) {
    const counts = new Map<string, number>()
    for (const l of group.labels) counts.set(l, (counts.get(l) ?? 0) + 1)
    const sortedLabels = [...counts.entries()].sort((a, b) => b[1] - a[1]).map(([l]) => l)
    const base = sortedLabels[0] ?? 'REL'
    const label = group.labels.length > 1 ? `${base} +${group.labels.length - 1}` : base
    renderEdges.push({
      id: `re-${i++}`,
      source: group.source,
      target: group.target,
      label,
      labels: sortedLabels,
      count: group.labels.length,
    })
    simEdges.push({ id: `se-${key}`, source: group.source, target: group.target, label: base })
  }

  return { simEdges, renderEdges }
}

function isRelated(a: string, b: string, neighbors: NeighborMap): boolean {
  if (a === b) return true
  return neighbors.get(a)?.has(b) ?? false
}

function easeOutCubic(t: number): number {
  return 1 - (1 - t) ** 3
}

function connectionCount(nodeId: string, edges: RenderEdge[]): number {
  return edges.reduce((sum, e) => (
    e.source === nodeId || e.target === nodeId ? sum + e.count : sum
  ), 0)
}

function fitToView(
  nodes: SimNode[],
  width: number,
  height: number,
): { panX: number; panY: number; scale: number } {
  if (!nodes.length) return { panX: 0, panY: 0, scale: 1 }
  let minX = Infinity
  let minY = Infinity
  let maxX = -Infinity
  let maxY = -Infinity
  for (const n of nodes) {
    minX = Math.min(minX, n.x - n.r)
    minY = Math.min(minY, n.y - n.r)
    maxX = Math.max(maxX, n.x + n.r)
    maxY = Math.max(maxY, n.y + n.r)
  }
  const graphW = Math.max(1, maxX - minX)
  const graphH = Math.max(1, maxY - minY)
  const pad = 56
  const sx = (width - pad * 2) / graphW
  const sy = (height - pad * 2) / graphH
  const scale = Math.max(0.12, Math.min(2.8, Math.min(sx, sy)))
  const cx = (minX + maxX) / 2
  const cy = (minY + maxY) / 2
  return {
    panX: -cx * scale,
    panY: -cy * scale,
    scale,
  }
}

/* ── Canvas renderer ────────────────────────────────────────────────────── */

function render(
  ctx: CanvasRenderingContext2D,
  nodes: SimNode[],
  edges: RenderEdge[],
  selectedId: string | null,
  hoveredId: string | null,
  neighbors: NeighborMap,
  panX: number, panY: number, scale: number,
  edgeLabels: boolean,
) {
  const W = ctx.canvas.width, H = ctx.canvas.height
  ctx.clearRect(0, 0, W, H)
  ctx.save()
  ctx.translate(panX + W / 2, panY + H / 2)
  ctx.scale(scale, scale)

  const byId = new Map(nodes.map(n => [n.id, n]))
  const focusId = selectedId ?? hoveredId

  /* edges */
  ctx.globalAlpha = 1
  for (const e of edges) {
    const a = byId.get(e.source), b = byId.get(e.target)
    if (!a || !b) continue
    const isDirect = focusId && (e.source === focusId || e.target === focusId)
    const isActive = !focusId || isDirect ||
      isRelated(focusId, e.source, neighbors) ||
      isRelated(focusId, e.target, neighbors)

    const mx = (a.x + b.x) / 2
    const my = (a.y + b.y) / 2
    const dx = b.x - a.x
    const dy = b.y - a.y
    const len = Math.max(1, Math.hypot(dx, dy))
    const nx = -dy / len
    const ny = dx / len
    const hash = e.id.split('').reduce((acc, ch) => acc + ch.charCodeAt(0), 0)
    const bend = ((hash % 13) - 6) * 2.6
    const cx = mx + nx * bend
    const cy = my + ny * bend

    const edgeColor = isDirect ? '#3b82f6' : isActive ? '#475569' : '#cbd5e1'
    const edgeWidth = isDirect ? 2.5 : isActive ? 1.6 : 0.9
    const edgeAlpha = isDirect ? 1 : isActive ? 0.65 : 0.18

    if (isDirect) {
      ctx.shadowColor = '#3b82f6'
      ctx.shadowBlur = 6 / scale
    }
    ctx.strokeStyle = edgeColor
    ctx.lineWidth = edgeWidth / scale
    ctx.globalAlpha = edgeAlpha
    ctx.beginPath()
    ctx.moveTo(a.x, a.y)
    ctx.quadraticCurveTo(cx, cy, b.x, b.y)
    ctx.stroke()
    ctx.shadowBlur = 0

    // arrow head
    const tx = b.x - cx
    const ty = b.y - cy
    const tLen = Math.max(1, Math.hypot(tx, ty))
    const ux = tx / tLen
    const uy = ty / tLen
    const arrowL = (isDirect ? 10 : 8) / scale
    const arrowW = (isDirect ? 5 : 4.2) / scale
    const bx = b.x - ux * (b.r * 0.35)
    const by = b.y - uy * (b.r * 0.35)
    ctx.fillStyle = edgeColor
    ctx.globalAlpha = isDirect ? 1 : isActive ? 0.75 : 0.18
    ctx.beginPath()
    ctx.moveTo(bx, by)
    ctx.lineTo(bx - ux * arrowL + -uy * arrowW, by - uy * arrowL + ux * arrowW)
    ctx.lineTo(bx - ux * arrowL - -uy * arrowW, by - uy * arrowL - ux * arrowW)
    ctx.closePath()
    ctx.fill()

    if (edgeLabels && scale > 0.62 && isActive) {
      ctx.fillStyle = isDirect ? '#3b82f6' : '#64748b'
      ctx.font = `${(isDirect ? 10 : 9) / scale}px system-ui`
      ctx.textAlign = 'center'
      ctx.textBaseline = 'middle'
      ctx.globalAlpha = isDirect ? 0.95 : 0.8
      ctx.fillText(e.label, cx, cy)
    }

  }
  ctx.globalAlpha = 1

  /* nodes */
  for (const n of nodes) {
    const [fill, fg] = nodeStyle(n.type)
    const sel = n.id === selectedId
    const hov = n.id === hoveredId
    const active = !focusId || isRelated(focusId, n.id, neighbors)
    const nodeAlpha = active ? 1 : 0.22

    ctx.globalAlpha = nodeAlpha
    ctx.beginPath(); ctx.arc(n.x, n.y, n.r, 0, 2 * Math.PI)
    ctx.fillStyle = fill; ctx.fill()
    ctx.strokeStyle = sel ? '#fff' : hov ? '#e2e8f0' : 'rgba(0,0,0,0.18)'
    ctx.lineWidth   = sel ? 3 / scale : hov ? 2 / scale : 1 / scale
    if (sel || hov) { ctx.shadowColor = fill; ctx.shadowBlur = (sel ? 16 : 10) / scale }
    ctx.stroke()
    ctx.shadowBlur = 0

    const fs = Math.max(8, Math.min(12, n.r * 0.55)) / scale
    ctx.font = `${fs}px system-ui`
    ctx.fillStyle = fg; ctx.textAlign = 'center'; ctx.textBaseline = 'middle'
    let lbl = n.label
    while (ctx.measureText(lbl).width > n.r * 1.7 && lbl.length > 3) lbl = lbl.slice(0, -2)
    if (lbl !== n.label) lbl += '…'
    ctx.fillText(lbl, n.x, n.y)
  }
  ctx.globalAlpha = 1

  ctx.restore()
}

/* ── Hit test ───────────────────────────────────────────────────────────── */

function hit(nodes: SimNode[], mx: number, my: number, panX: number, panY: number, scale: number, W: number, H: number): SimNode | null {
  const wx = (mx - W / 2 - panX) / scale
  const wy = (my - H / 2 - panY) / scale
  for (let i = nodes.length - 1; i >= 0; i--) {
    const n = nodes[i]
    if ((wx - n.x) ** 2 + (wy - n.y) ** 2 <= n.r * n.r) return n
  }
  return null
}

/* ── Data fetcher ───────────────────────────────────────────────────────── */

async function fetchGraph(limit: number, focusId: string): Promise<{ nodes: GraphNode[]; edges: GraphEdge[] }> {
  try {
    const res = await fetch('/api/query/cypher', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        query: `
          MATCH (a:Entity)-[r]->(b:Entity)
          WHERE $focus_id = '' OR a.id = $focus_id OR b.id = $focus_id
          RETURN a.id AS sid,
                 coalesce(a.canonical_name, split(a.id,':')[-1]) AS sl,
                 coalesce(a.entity_type,'entity') AS st, properties(a) AS sp,
                 b.id AS tid,
                 coalesce(b.canonical_name, split(b.id,':')[-1]) AS tl,
                 coalesce(b.entity_type,'entity') AS tt, properties(b) AS tp,
                 type(r) AS rel
          LIMIT $limit`,
        params: { limit, focus_id: focusId },
      }),
    })
    if (!res.ok) return { nodes: [], edges: [] }
    const data = await res.json()
    const rows: Record<string, unknown>[] = data?.rows ?? []
    const nodeMap = new Map<string, GraphNode>()
    const edges: GraphEdge[] = []
    rows.forEach((r, i) => {
      const s = String(r.sid ?? ''), t = String(r.tid ?? '')
      if (!s || !t) return
      if (!nodeMap.has(s)) nodeMap.set(s, { id: s, label: String(r.sl ?? s), type: String(r.st ?? 'entity'), properties: (r.sp as Record<string, unknown>) ?? {} })
      if (!nodeMap.has(t)) nodeMap.set(t, { id: t, label: String(r.tl ?? t), type: String(r.tt ?? 'entity'), properties: (r.tp as Record<string, unknown>) ?? {} })
      edges.push({ id: `e${i}`, source: s, target: t, label: String(r.rel ?? 'REL') })
    })
    return { nodes: [...nodeMap.values()], edges }
  } catch { return { nodes: [], edges: [] } }
}

/* ── Component ──────────────────────────────────────────────────────────── */

export default function WorkflowPage() {
  const canvasRef = useRef<HTMLCanvasElement>(null)

  const s = useRef({
    nodes:      [] as SimNode[],
    edges:      [] as GraphEdge[],
    renderEdges: [] as RenderEdge[],
    neighbors:  new Map() as NeighborMap,
    rawEdgeCount: 0,
    camAnim:    null as CameraAnim | null,
    alpha:      0,
    rafId:      0,
    panX:       0, panY:  0, scale: 1,
    isPan:      false, isDrag: false, hasMoved: false,
    mx0:        0, my0:   0,
    px0:        0, py0:   0,
    dragNode:   null as SimNode | null,
  })

  const [selected,     setSelected]     = useState<SimNode | null>(null)
  const [hoveredId,    setHoveredId]    = useState<string | null>(null)
  const [graphVersion, setGraphVersion] = useState(0)   // bumped on load → re-derive lists
  const [loading,      setLoading]      = useState(false)
  const [edgeLabels,   setEdgeLabels]   = useState(false)
  const [focusId,      setFocusId]      = useState('')
  const [limitStr,     setLimitStr]     = useState('80')
  const [filter,       setFilter]       = useState('')
  const [copiedNodeId, setCopiedNodeId] = useState<string | null>(null)

  const edgeLabelsRef = useRef(false); edgeLabelsRef.current = edgeLabels
  const selectedRef   = useRef<SimNode | null>(null); selectedRef.current = selected
  const hoveredRef    = useRef<string | null>(null); hoveredRef.current = hoveredId

  const startCameraTween = useCallback((toPanX: number, toPanY: number, toScale: number, duration = 380) => {
    s.current.camAnim = {
      fromPanX: s.current.panX,
      fromPanY: s.current.panY,
      fromScale: s.current.scale,
      toPanX,
      toPanY,
      toScale,
      startAt: performance.now(),
      duration,
    }
  }, [])

  /* animation loop */
  const loop = useCallback(() => {
    const c = canvasRef.current; if (!c) return
    const ctx = c.getContext('2d'); if (!ctx) return
    if (s.current.camAnim) {
      const now = performance.now()
      const t = Math.min(1, (now - s.current.camAnim.startAt) / s.current.camAnim.duration)
      const k = easeOutCubic(t)
      s.current.panX = s.current.camAnim.fromPanX + (s.current.camAnim.toPanX - s.current.camAnim.fromPanX) * k
      s.current.panY = s.current.camAnim.fromPanY + (s.current.camAnim.toPanY - s.current.camAnim.fromPanY) * k
      s.current.scale = s.current.camAnim.fromScale + (s.current.camAnim.toScale - s.current.camAnim.fromScale) * k
      if (t >= 1) s.current.camAnim = null
    }
    if (s.current.alpha > 0.001) { tick(s.current.nodes, s.current.edges, s.current.alpha); s.current.alpha *= 0.991 }
    render(ctx, s.current.nodes, s.current.renderEdges, selectedRef.current?.id ?? null,
      hoveredRef.current, s.current.neighbors,
      s.current.panX, s.current.panY, s.current.scale, edgeLabelsRef.current)
    s.current.rafId = requestAnimationFrame(loop)
  }, [])

  /* load graph */
  const loadGraph = useCallback(async () => {
    setLoading(true)
    try {
      const lim = Math.max(10, Math.min(300, Number(limitStr) || 80))
      const { nodes, edges: rawEdges } = await fetchGraph(lim, focusId.trim())
      const { simEdges, renderEdges } = bundleEdges(rawEdges)
      const c = canvasRef.current
      const W = c?.clientWidth ?? 900, H = c?.clientHeight ?? 600
      s.current.nodes = initSim(nodes, simEdges, W, H)
      s.current.edges = simEdges
      s.current.renderEdges = renderEdges
      s.current.neighbors = buildNeighborMap(simEdges)
      s.current.rawEdgeCount = rawEdges.length
      const fitted = fitToView(s.current.nodes, W, H)
      s.current.panX = fitted.panX
      s.current.panY = fitted.panY
      s.current.scale = fitted.scale
      s.current.camAnim = null
      s.current.alpha = 1
      setSelected(null)
      setHoveredId(null)
      setGraphVersion(v => v + 1)
    } finally { setLoading(false) }
  }, [limitStr, focusId])

  /* auto-load + start RAF */
  useEffect(() => {
    void loadGraph()
    s.current.rafId = requestAnimationFrame(loop)
    return () => cancelAnimationFrame(s.current.rafId)
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  /* resize canvas buffer to match CSS size */
  useEffect(() => {
    const c = canvasRef.current; if (!c) return
    const sync = () => { c.width = c.clientWidth; c.height = c.clientHeight }
    sync()
    const ro = new ResizeObserver(sync)
    ro.observe(c)
    return () => ro.disconnect()
  }, [])

  /* mouse helpers */
  const getXY = (e: React.MouseEvent) => {
    const r = canvasRef.current!.getBoundingClientRect()
    return { x: e.clientX - r.left, y: e.clientY - r.top }
  }

  const onMouseDown = useCallback((e: React.MouseEvent) => {
    s.current.camAnim = null
    const { x, y } = getXY(e)
    const c = canvasRef.current!
    const node = hit(s.current.nodes, x, y, s.current.panX, s.current.panY, s.current.scale, c.clientWidth, c.clientHeight)
    s.current.mx0 = x; s.current.my0 = y; s.current.hasMoved = false
    if (node) { s.current.isDrag = true; s.current.dragNode = node; s.current.alpha = Math.max(s.current.alpha, 0.15) }
    else       { s.current.isPan  = true; s.current.px0 = s.current.panX; s.current.py0 = s.current.panY }
  }, [])

  const onMouseMove = useCallback((e: React.MouseEvent) => {
    const { x, y } = getXY(e)
    const dx = x - s.current.mx0, dy = y - s.current.my0
    if (Math.abs(dx) > 2 || Math.abs(dy) > 2) s.current.hasMoved = true
    if (s.current.isDrag && s.current.dragNode) {
      const c = canvasRef.current!
      const node = s.current.dragNode
      node.x = (x - c.clientWidth  / 2 - s.current.panX) / s.current.scale
      node.y = (y - c.clientHeight / 2 - s.current.panY) / s.current.scale
      node.vx = 0; node.vy = 0
    } else if (s.current.isPan) {
      s.current.panX = s.current.px0 + dx
      s.current.panY = s.current.py0 + dy
    } else {
      const c = canvasRef.current!
      const node = hit(s.current.nodes, x, y, s.current.panX, s.current.panY, s.current.scale, c.clientWidth, c.clientHeight)
      const next = node?.id ?? null
      if (next !== hoveredRef.current) setHoveredId(next)
    }
  }, [])

  const onMouseUp = useCallback((e: React.MouseEvent) => {
    if (!s.current.hasMoved) {
      const { x, y } = getXY(e)
      const c = canvasRef.current!
      const node = hit(s.current.nodes, x, y, s.current.panX, s.current.panY, s.current.scale, c.clientWidth, c.clientHeight)
      setSelected(node ? { ...node } : null)
      setHoveredId(node?.id ?? null)
    }
    s.current.isDrag = false; s.current.isPan = false; s.current.dragNode = null
  }, [])

  const onMouseLeave = useCallback((e: React.MouseEvent) => {
    onMouseUp(e)
    setHoveredId(null)
  }, [onMouseUp])

  const onWheel = useCallback((e: React.WheelEvent) => {
    e.preventDefault()
    s.current.camAnim = null
    const { x, y } = getXY(e)
    const c = canvasRef.current!
    const factor   = e.deltaY < 0 ? 1.12 : 0.89
    const newScale = Math.max(0.08, Math.min(6, s.current.scale * factor))
    const cx = c.clientWidth / 2, cy = c.clientHeight / 2
    s.current.panX = x - cx - (x - cx - s.current.panX) * (newScale / s.current.scale)
    s.current.panY = y - cy - (y - cy - s.current.panY) * (newScale / s.current.scale)
    s.current.scale = newScale
  }, [])

  const handleFitView = useCallback(() => {
    const c = canvasRef.current
    if (!c) return
    const fitted = fitToView(s.current.nodes, c.clientWidth, c.clientHeight)
    startCameraTween(fitted.panX, fitted.panY, fitted.scale)
    s.current.alpha = Math.max(s.current.alpha, 0.12)
  }, [startCameraTween])

  const handleCenterSelection = useCallback(() => {
    if (!selected) return
    startCameraTween(-selected.x * s.current.scale, -selected.y * s.current.scale, s.current.scale)
    s.current.alpha = Math.max(s.current.alpha, 0.09)
  }, [selected, startCameraTween])

  /* derived lists */
  const overviewNodes = useMemo(() => {
    const q = filter.trim().toLowerCase()
    return [...s.current.nodes]
      .sort((a, b) => b.r - a.r)
      .filter(n => !q || n.label.toLowerCase().includes(q) || n.id.toLowerCase().includes(q) || n.type.toLowerCase().includes(q))
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filter, graphVersion])

  const legend = useMemo(() => {
    const seen = new Set(s.current.nodes.map(n => n.type))
    return [...seen].sort()
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [graphVersion])

  const hoveredNode = useMemo(() => {
    if (!hoveredId) return null
    return s.current.nodes.find((n) => n.id === hoveredId) ?? null
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [hoveredId, graphVersion])

  const detailNode = selected ?? hoveredNode
  const isHoverPreview = !selected && !!hoveredNode

  const normalizedDetailProperties = useMemo(
    () => (detailNode ? normalizeProperties(detailNode.properties) : {}),
    [detailNode],
  )

  const detailPropertyPreview = useMemo(
    () => dedupeAttributeEntries(flattenProperties(normalizedDetailProperties)),
    [normalizedDetailProperties],
  )

  async function handleExtractRawData() {
    if (!detailNode) return
    const raw = JSON.stringify(normalizedDetailProperties, null, 2)
    try {
      await navigator.clipboard.writeText(raw)
      setCopiedNodeId(detailNode.id)
      window.setTimeout(() => setCopiedNodeId((prev) => (prev === detailNode.id ? null : prev)), 1200)
    } catch {
      setCopiedNodeId(null)
    }
  }

  return (
    <div className="flex h-full flex-col gap-3 overflow-auto p-4">
      {/* Toolbar */}
      <div className="flex flex-wrap items-center gap-2">
        <Input className="w-60" placeholder="Focus Entity ID (optional)" value={focusId} onChange={e => setFocusId(e.target.value)} />
        <Input className="w-20" placeholder="Limit" value={limitStr} onChange={e => setLimitStr(e.target.value)} />
        <Button onClick={loadGraph} disabled={loading}>{loading ? 'Loading…' : 'Load Graph'}</Button>
        <Button variant="outline" onClick={handleFitView}>Fit View</Button>
        <Button variant="outline" onClick={handleCenterSelection} disabled={!selected}>Center Selection</Button>
        <Button variant={edgeLabels ? 'secondary' : 'outline'} onClick={() => setEdgeLabels(v => !v)}>
          Edge Labels {edgeLabels ? 'On' : 'Off'}
        </Button>
        <div className="ml-auto flex flex-wrap items-center gap-3">
          {legend.map(t => {
            const [clr] = nodeStyle(t)
            return (
              <span key={t} className="flex items-center gap-1 text-xs text-muted-foreground">
                <span className="inline-block h-2.5 w-2.5 rounded-full" style={{ background: clr }} />
                {t}
              </span>
            )
          })}
          <span className="text-xs text-muted-foreground">
            {s.current.nodes.length} nodes · {s.current.renderEdges.length} links
          </span>
        </div>
      </div>

      {/* Canvas */}
      <div className="relative min-h-[520px] flex-1 overflow-hidden rounded-xl border border-border/70 bg-slate-50 dark:bg-slate-900">
        <canvas
          ref={canvasRef}
          className="h-full w-full cursor-grab active:cursor-grabbing"
          style={{ display: 'block' }}
          onMouseDown={onMouseDown}
          onMouseMove={onMouseMove}
          onMouseUp={onMouseUp}
          onMouseLeave={onMouseLeave}
          onWheel={onWheel}
        />
        {s.current.nodes.length === 0 && !loading && (
          <p className="pointer-events-none absolute inset-0 flex items-center justify-center text-sm text-muted-foreground">
            Keine Daten — klicke „Load Graph".
          </p>
        )}
      </div>

      {/* Node detail + overview */}
      <div className="grid gap-3 lg:grid-cols-2">
        <Card>
          <CardHeader><CardTitle className="text-sm">Node Detail</CardTitle></CardHeader>
          <CardContent>
            {!detailNode ? (
              <p className="text-sm text-muted-foreground">Hover oder klicke im Graph auf einen Node.</p>
            ) : (
              <div className="space-y-3">
                {isHoverPreview && (
                  <div className="rounded-lg border border-blue-200 bg-blue-50/80 px-3 py-1.5 text-xs font-medium text-blue-700">
                    Preview (Hover) - click to pin
                  </div>
                )}
                <div className="rounded-2xl border border-white/60 bg-white/70 p-4 shadow-[0_2px_20px_rgba(15,23,42,0.05)] backdrop-blur-xl">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="inline-block h-3 w-3 rounded-full" style={{ background: nodeStyle(detailNode.type)[0] }} />
                    <p className="text-base font-semibold text-slate-900">{detailNode.label}</p>
                    <span className="inline-flex items-center rounded-full bg-blue-100 px-2 py-0.5 text-[11px] font-semibold text-blue-700">
                      {detailNode.type}
                    </span>
                    <span className="inline-flex items-center rounded-full bg-slate-100 px-2 py-0.5 text-[11px] font-semibold text-slate-700">
                      {connectionCount(detailNode.id, s.current.renderEdges)} connections
                    </span>
                  </div>
                  <p className="mt-2 break-all font-mono text-xs text-slate-500">{detailNode.id}</p>
                </div>

                {detailPropertyPreview.length > 0 && (
                  <div className="rounded-2xl border border-border/70 bg-background/70 p-3">
                    <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                      Attributes
                    </p>
                    <div className="space-y-1.5">
                      {detailPropertyPreview.map(([key, value]) => (
                        <div key={key} className="grid grid-cols-[150px_1fr] items-center gap-2 text-xs">
                          <span className="text-slate-500">{formatAttributeLabel(key)}</span>
                          <div className="overflow-x-auto">
                            <span className="block whitespace-nowrap text-slate-800" title={previewValue(value)}>
                              {previewValue(value)}
                            </span>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                <div className="rounded-2xl border border-border/70 bg-background/70 p-3">
                  <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                    Raw Data
                  </p>
                  <Button
                    size="sm"
                    variant={copiedNodeId === detailNode.id ? 'secondary' : 'outline'}
                    className={
                      copiedNodeId === detailNode.id
                        ? 'border-emerald-200 bg-emerald-50 text-emerald-700 hover:bg-emerald-100'
                        : ''
                    }
                    onClick={handleExtractRawData}
                  >
                    {copiedNodeId === detailNode.id ? (
                      <span className="inline-flex items-center gap-1.5">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                          <path d="M20 6 9 17l-5-5" />
                        </svg>
                        Copied to clipboard
                      </span>
                    ) : (
                      'Extract Raw Data'
                    )}
                  </Button>
                </div>
              </div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader><CardTitle className="text-sm">All Nodes</CardTitle></CardHeader>
          <CardContent className="space-y-2">
            <Input placeholder="Filter by label / id / type" value={filter} onChange={e => setFilter(e.target.value)} />
            <div className="max-h-56 overflow-auto rounded-lg border border-border/70">
              {overviewNodes.length === 0 ? (
                <p className="p-3 text-sm text-muted-foreground">Keine Nodes.</p>
              ) : overviewNodes.map(n => (
                <button
                  key={n.id}
                  onClick={() => {
                    setSelected({ ...n })
                    setHoveredId(n.id)
                    startCameraTween(-n.x * s.current.scale, -n.y * s.current.scale, s.current.scale, 320)
                    s.current.alpha = Math.max(s.current.alpha, 0.08)
                  }}
                  className="flex w-full items-center gap-2 border-b px-3 py-2 text-left last:border-0 hover:bg-muted/40"
                >
                  <span className="inline-block h-2.5 w-2.5 shrink-0 rounded-full" style={{ background: nodeStyle(n.type)[0] }} />
                  <div>
                    <p className="text-sm font-medium">{n.label}</p>
                    <p className="font-mono text-xs text-muted-foreground">{n.type}</p>
                  </div>
                </button>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
