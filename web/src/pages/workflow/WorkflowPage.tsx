import { useMemo, useState } from 'react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { InteractiveNvlWrapper } from '@neo4j-nvl/react'
import { ForceDirectedLayoutType, type Node as NvlNode, type Relationship as NvlRelationship } from '@neo4j-nvl/base'

type LogItem = {
  id: number
  title: string
  method: string
  path: string
  requestBody?: unknown
  status?: number
  ok: boolean
  responseBody?: unknown
  error?: string
  at: string
}

type GraphNode = {
  id: string
  label: string
  type: string
  labels: string[]
  properties: Record<string, unknown>
}

type GraphEdge = {
  id: string
  source: string
  target: string
  label: string
}

const TYPE_COLORS: Record<string, string> = {
  person: '#dbeafe',
  customer: '#dcfce7',
  product: '#fde68a',
  policy: '#e9d5ff',
  project: '#fed7aa',
  task: '#fbcfe8',
  communication: '#bfdbfe',
  document: '#ddd6fe',
  entity: '#e5e7eb',
}

function nodeColor(type: string): string {
  return TYPE_COLORS[type] ?? '#e5e7eb'
}

async function parseResponseBody(res: Response) {
  const contentType = res.headers.get('content-type') ?? ''
  if (contentType.includes('application/json')) {
    return res.json()
  }
  return res.text()
}

export default function WorkflowPage() {
  const [searchQuery, setSearchQuery] = useState('Who manages Acme GmbH?')
  const [k, setK] = useState('5')
  const [entityId, setEntityId] = useState('')
  const [factId, setFactId] = useState('')
  const [vfsPath, setVfsPath] = useState('/companies')
  const [predicate, setPredicate] = useState('qa_note')
  const [objectEntityId, setObjectEntityId] = useState('')
  const [objectLiteral, setObjectLiteral] = useState('"E2E test via workflow UI"')
  const [confidence, setConfidence] = useState('0.92')
  const [graphLimit, setGraphLimit] = useState('80')
  const [graphFocusEntityId, setGraphFocusEntityId] = useState('')
  const [graphReady, setGraphReady] = useState<boolean | null>(null)
  const [graphNodeCount, setGraphNodeCount] = useState<number | null>(null)
  const [graphEdgeCount, setGraphEdgeCount] = useState<number | null>(null)
  const [graphNodes, setGraphNodes] = useState<GraphNode[]>([])
  const [graphEdges, setGraphEdges] = useState<GraphEdge[]>([])
  const [graphVisibleNodes, setGraphVisibleNodes] = useState('45')
  const [showGraphEdgeLabels, setShowGraphEdgeLabels] = useState(false)
  const [selectedGraphNodeId, setSelectedGraphNodeId] = useState<string | null>(null)
  const [overviewFilter, setOverviewFilter] = useState('')
  const [selectedOverviewNodeId, setSelectedOverviewNodeId] = useState<string | null>(null)
  const [isRunning, setIsRunning] = useState(false)
  const [logs, setLogs] = useState<LogItem[]>([])

  const canPropose = entityId.trim().length > 0 && predicate.trim().length > 0

  async function runRequest(
    title: string,
    method: 'GET' | 'POST',
    path: string,
    body?: unknown,
  ): Promise<{ ok: boolean; status?: number; response?: unknown }> {
    try {
      const res = await fetch(path, {
        method,
        headers: { 'Content-Type': 'application/json' },
        body: body === undefined ? undefined : JSON.stringify(body),
      })
      const parsed = await parseResponseBody(res)
      const item: LogItem = {
        id: Date.now() + Math.floor(Math.random() * 1000),
        title,
        method,
        path,
        requestBody: body,
        status: res.status,
        ok: res.ok,
        responseBody: parsed,
        at: new Date().toISOString(),
      }
      setLogs((prev) => [item, ...prev].slice(0, 40))
      return { ok: res.ok, status: res.status, response: parsed }
    } catch (err) {
      const item: LogItem = {
        id: Date.now() + Math.floor(Math.random() * 1000),
        title,
        method,
        path,
        requestBody: body,
        ok: false,
        error: err instanceof Error ? err.message : String(err),
        at: new Date().toISOString(),
      }
      setLogs((prev) => [item, ...prev].slice(0, 40))
      return { ok: false }
    }
  }

  function parseObjectLiteral(): unknown {
    const raw = objectLiteral.trim()
    if (!raw) return null
    try {
      return JSON.parse(raw)
    } catch {
      return raw
    }
  }

  async function runHealth() {
    await runRequest('Health', 'GET', '/api/health')
  }

  async function runSearch(): Promise<string> {
    const kk = Number(k)
    const result = await runRequest('Search', 'POST', '/api/search', {
      query: searchQuery.trim(),
      k: Number.isFinite(kk) && kk > 0 ? kk : 5,
    })
    if (!result.ok) return ''
    const firstEntityId =
      (result.response as { results?: Array<{ entity?: { id?: string } }> })?.results?.[0]?.entity
        ?.id ?? ''
    if (firstEntityId) {
      setEntityId(firstEntityId)
    }
    return firstEntityId
  }

  async function runEntity(forcedEntityId?: string): Promise<string> {
    const id = (forcedEntityId ?? entityId).trim()
    if (!id) return ''
    const result = await runRequest('Get Entity', 'GET', `/api/entities/${encodeURIComponent(id)}`)
    if (!result.ok) return ''
    const firstFactId = (result.response as { facts?: Array<{ id?: string }> })?.facts?.[0]?.id ?? ''
    if (firstFactId) {
      setFactId(firstFactId)
    }
    return firstFactId
  }

  async function runFactProvenance(forcedFactId?: string) {
    const id = (forcedFactId ?? factId).trim()
    if (!id) return
    await runRequest('Get Fact Provenance', 'GET', `/api/facts/${encodeURIComponent(id)}/provenance`)
  }

  async function runVfsRead() {
    const path = vfsPath.trim().replace(/^\/+/, '')
    if (!path) return
    await runRequest('VFS Read', 'GET', `/api/vfs/${path}`)
  }

  async function runProposeFact(forcedSubjectId?: string) {
    const subjectId = (forcedSubjectId ?? entityId).trim()
    if (!subjectId) return
    const objectId = objectEntityId.trim()
    const parsedConfidence = Number(confidence)
    const safeConfidence = Number.isFinite(parsedConfidence)
      ? Math.max(0, Math.min(1, parsedConfidence))
      : 0.9
    await runRequest('Propose Fact', 'POST', '/api/vfs/propose-fact', {
      subject_id: subjectId,
      predicate: predicate.trim(),
      object_id: objectId || null,
      object_literal: objectId ? null : parseObjectLiteral(),
      confidence: safeConfidence,
      source_system: 'workflow_ui',
      source_method: 'manual_test',
      note: 'E2E workflow test via web UI',
    })
  }

  async function runGraphReadyCheck() {
    const result = await runRequest('Graph Ready Check', 'GET', '/api/query/cypher/named')
    if (!result.ok) {
      setGraphReady(false)
      return false
    }
    // Always ready: Neo4j when configured, Postgres fallback otherwise.
    setGraphReady(true)
    return true
  }

  async function runGraphStats() {
    const nodeRes = await runRequest('Graph Node Count', 'POST', '/api/query/cypher', {
      query: 'MATCH (n:Entity) RETURN count(n) AS node_count',
      params: {},
    })
    if (nodeRes.ok) {
      const value = Number(
        (nodeRes.response as { rows?: Array<{ node_count?: number }> })?.rows?.[0]?.node_count ?? 0,
      )
      setGraphNodeCount(Number.isFinite(value) ? value : 0)
    }

    const edgeRes = await runRequest('Graph Edge Count', 'POST', '/api/query/cypher', {
      query: 'MATCH (:Entity)-[r]->(:Entity) RETURN count(r) AS edge_count',
      params: {},
    })
    if (edgeRes.ok) {
      const value = Number(
        (edgeRes.response as { rows?: Array<{ edge_count?: number }> })?.rows?.[0]?.edge_count ?? 0,
      )
      setGraphEdgeCount(Number.isFinite(value) ? value : 0)
    }
  }

  async function runGraphPreview() {
    const limit = Math.max(10, Math.min(300, Number(graphLimit) || 80))
    const focus = graphFocusEntityId.trim()
    const result = await runRequest('Graph Preview', 'POST', '/api/query/cypher', {
      query: `
        MATCH (a:Entity)-[r]->(b:Entity)
        WHERE $focus_id = '' OR a.id = $focus_id OR b.id = $focus_id
        RETURN
          a.id AS source_id,
          coalesce(a.canonical_name, a.id) AS source_label,
          coalesce(a.entity_type, 'entity') AS source_type,
          labels(a) AS source_labels,
          properties(a) AS source_props,
          b.id AS target_id,
          coalesce(b.canonical_name, b.id) AS target_label,
          coalesce(b.entity_type, 'entity') AS target_type,
          labels(b) AS target_labels,
          properties(b) AS target_props,
          type(r) AS rel_type
        LIMIT $limit
      `,
      params: { limit, focus_id: focus },
    })
    if (!result.ok) return

    const rows =
      (result.response as {
        rows?: Array<{
          source_id?: string
          source_label?: string
          source_type?: string
          source_labels?: string[]
          source_props?: Record<string, unknown>
          target_id?: string
          target_label?: string
          target_type?: string
          target_labels?: string[]
          target_props?: Record<string, unknown>
          rel_type?: string
        }>
      })?.rows ?? []

    const nodeMap = new Map<string, GraphNode>()
    const edges: GraphEdge[] = []
    rows.forEach((row, idx) => {
      const sId = row.source_id ?? ''
      const tId = row.target_id ?? ''
      if (!sId || !tId) return

      if (!nodeMap.has(sId)) {
        nodeMap.set(sId, {
          id: sId,
          label: row.source_label ?? sId,
          type: row.source_type ?? 'entity',
          labels: Array.isArray(row.source_labels) ? row.source_labels : ['Entity'],
          properties:
            row.source_props && typeof row.source_props === 'object'
              ? row.source_props
              : {},
        })
      }
      if (!nodeMap.has(tId)) {
        nodeMap.set(tId, {
          id: tId,
          label: row.target_label ?? tId,
          type: row.target_type ?? 'entity',
          labels: Array.isArray(row.target_labels) ? row.target_labels : ['Entity'],
          properties:
            row.target_props && typeof row.target_props === 'object'
              ? row.target_props
              : {},
        })
      }
      edges.push({
        id: `e-${idx}-${sId}-${tId}`,
        source: sId,
        target: tId,
        label: row.rel_type ?? 'REL',
      })
    })

    setGraphNodes(Array.from(nodeMap.values()))
    setGraphEdges(edges)
  }

  async function runE2E() {
    setIsRunning(true)
    try {
      await runHealth()
      const resolvedEntityId = (await runSearch()) || entityId.trim()
      const resolvedFactId = resolvedEntityId
        ? (await runEntity(resolvedEntityId)) || factId.trim()
        : factId.trim()
      if (resolvedFactId) await runFactProvenance(resolvedFactId)
      await runVfsRead()
      if (resolvedEntityId && predicate.trim()) {
        await runProposeFact(resolvedEntityId)
      }
      const ready = await runGraphReadyCheck()
      if (ready) {
        await runGraphStats()
        await runGraphPreview()
      }
    } finally {
      setIsRunning(false)
    }
  }

  const successCount = useMemo(() => logs.filter((l) => l.ok).length, [logs])
  const graphModel = useMemo(() => {
    const maxVisibleNodes = Math.max(10, Math.min(250, Number(graphVisibleNodes) || 45))
    const degree = new Map<string, number>()
    graphNodes.forEach((node) => degree.set(node.id, 0))
    graphEdges.forEach((edge) => {
      degree.set(edge.source, (degree.get(edge.source) ?? 0) + 1)
      degree.set(edge.target, (degree.get(edge.target) ?? 0) + 1)
    })

    const keptIds = new Set(
      [...graphNodes]
        .sort((a, b) => (degree.get(b.id) ?? 0) - (degree.get(a.id) ?? 0))
        .slice(0, maxVisibleNodes)
        .map((n) => n.id),
    )

    // Include edges that touch at least one high-degree node (handles star topologies
    // where leaf nodes have degree 1 and would otherwise be outside keptIds).
    const filteredEdges = graphEdges.filter(
      (edge) => keptIds.has(edge.source) || keptIds.has(edge.target),
    )
    // Nodes: union of keptIds + all edge endpoints so every edge has both ends in the canvas.
    const edgeEndpointIds = new Set(filteredEdges.flatMap((e) => [e.source, e.target]))
    const nodeById = new Map(graphNodes.map((n) => [n.id, n]))
    const filteredNodes = [...edgeEndpointIds]
      .map((id) => nodeById.get(id))
      .filter((n): n is GraphNode => n !== undefined)
      .sort((a, b) => (degree.get(b.id) ?? 0) - (degree.get(a.id) ?? 0))

    const showEdgeLabel = showGraphEdgeLabels && filteredEdges.length <= 80
    const nvlNodes: NvlNode[] = filteredNodes.map((node) => ({
      id: node.id,
      caption: node.label,
      color: nodeColor(node.type),
      size: Math.min(42, 18 + (degree.get(node.id) ?? 0) * 1.8),
    }))
    const nvlRels: NvlRelationship[] = filteredEdges.map((edge) => ({
      id: edge.id,
      from: edge.source,
      to: edge.target,
      caption: showEdgeLabel ? edge.label : undefined,
      color: '#8d95a3',
      width: 1.25,
    }))

    const overviewNodes = [...graphNodes]
      .sort((a, b) => (degree.get(b.id) ?? 0) - (degree.get(a.id) ?? 0))
      .filter((node) => {
        const q = overviewFilter.trim().toLowerCase()
        if (!q) return true
        return (
          node.label.toLowerCase().includes(q) ||
          node.id.toLowerCase().includes(q) ||
          node.type.toLowerCase().includes(q)
        )
      })

    return {
      degree,
      nvlNodes,
      nvlRels,
      overviewNodes,
      shownNodes: nvlNodes.length,
      shownEdges: nvlRels.length,
      edgeLabelsSuppressed: showGraphEdgeLabels && !showEdgeLabel,
    }
  }, [graphEdges, graphNodes, graphVisibleNodes, overviewFilter, showGraphEdgeLabels])

  const graphSelectedNode = useMemo(
    () => graphNodes.find((node) => node.id === selectedGraphNodeId) ?? null,
    [graphNodes, selectedGraphNodeId],
  )

  const overviewSelectedNode = useMemo(
    () => graphNodes.find((node) => node.id === selectedOverviewNodeId) ?? null,
    [graphNodes, selectedOverviewNodeId],
  )

  return (
    <div className="h-full overflow-auto p-4 sm:p-6">
      <div className="mx-auto grid w-full max-w-7xl gap-4 lg:grid-cols-[360px_minmax(0,1fr)]">
        <Card className="h-fit">
          <CardHeader>
            <CardTitle>Workflow Test Console</CardTitle>
            <CardDescription>
              End-to-end Requests gegen die Live-API inkl. Request/Response-Log.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <label className="text-xs text-muted-foreground">Search Query</label>
              <Input value={searchQuery} onChange={(e) => setSearchQuery(e.target.value)} />
              <label className="text-xs text-muted-foreground">k</label>
              <Input value={k} onChange={(e) => setK(e.target.value)} />
              <Button variant="outline" onClick={runSearch} disabled={isRunning || !searchQuery.trim()}>
                Search
              </Button>
            </div>

            <div className="space-y-2">
              <label className="text-xs text-muted-foreground">Entity ID</label>
              <Input value={entityId} onChange={(e) => setEntityId(e.target.value)} />
              <Button
                variant="outline"
                onClick={() => {
                  void runEntity()
                }}
                disabled={isRunning || !entityId.trim()}
              >
                Get Entity
              </Button>
            </div>

            <div className="space-y-2">
              <label className="text-xs text-muted-foreground">Fact ID</label>
              <Input value={factId} onChange={(e) => setFactId(e.target.value)} />
              <Button
                variant="outline"
                onClick={() => {
                  void runFactProvenance()
                }}
                disabled={isRunning || !factId.trim()}
              >
                Get Fact Provenance
              </Button>
            </div>

            <div className="space-y-2">
              <label className="text-xs text-muted-foreground">VFS Path</label>
              <Input value={vfsPath} onChange={(e) => setVfsPath(e.target.value)} />
              <Button variant="outline" onClick={runVfsRead} disabled={isRunning || !vfsPath.trim()}>
                Read VFS
              </Button>
            </div>

            <div className="space-y-2">
              <label className="text-xs text-muted-foreground">Predicate</label>
              <Input value={predicate} onChange={(e) => setPredicate(e.target.value)} />
              <label className="text-xs text-muted-foreground">Object Entity ID (optional, creates edge)</label>
              <Input
                value={objectEntityId}
                onChange={(e) => setObjectEntityId(e.target.value)}
                placeholder="z.B. person:john-doe"
              />
              <label className="text-xs text-muted-foreground">Object Literal (JSON oder Text)</label>
              <Input value={objectLiteral} onChange={(e) => setObjectLiteral(e.target.value)} />
              <label className="text-xs text-muted-foreground">Confidence</label>
              <Input value={confidence} onChange={(e) => setConfidence(e.target.value)} />
              <Button
                variant="outline"
                onClick={() => {
                  void runProposeFact()
                }}
                disabled={isRunning || !canPropose}
              >
                Propose Fact
              </Button>
            </div>

            <div className="flex flex-wrap gap-2 pt-2">
              <Button onClick={runHealth} variant="secondary" disabled={isRunning}>
                Health
              </Button>
              <Button onClick={runE2E} disabled={isRunning}>
                {isRunning ? 'Running...' : 'Run E2E Smoke'}
              </Button>
              <Button variant="ghost" onClick={() => setLogs([])} disabled={isRunning || logs.length === 0}>
                Clear Log
              </Button>
            </div>

            <div className="space-y-2 rounded-lg border border-border/80 p-3">
              <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Graph Check</p>
              <label className="text-xs text-muted-foreground">Focus Entity ID (optional)</label>
              <Input
                value={graphFocusEntityId}
                onChange={(e) => setGraphFocusEntityId(e.target.value)}
                placeholder="z.B. customer:acme-gmbh"
              />
              <label className="text-xs text-muted-foreground">Preview Edge Limit</label>
              <Input value={graphLimit} onChange={(e) => setGraphLimit(e.target.value)} />
              <label className="text-xs text-muted-foreground">Visible Nodes (Top by degree)</label>
              <Input
                value={graphVisibleNodes}
                onChange={(e) => setGraphVisibleNodes(e.target.value)}
              />
              <div className="flex flex-wrap gap-2">
                <Button variant="outline" onClick={runGraphReadyCheck} disabled={isRunning}>
                  Check Ready
                </Button>
                <Button variant="outline" onClick={runGraphStats} disabled={isRunning}>
                  Count Nodes/Edges
                </Button>
                <Button variant="outline" onClick={runGraphPreview} disabled={isRunning}>
                  Load Graph Preview
                </Button>
                <Button
                  variant={showGraphEdgeLabels ? 'secondary' : 'outline'}
                  onClick={() => setShowGraphEdgeLabels((v) => !v)}
                  disabled={isRunning}
                >
                  Edge Labels {showGraphEdgeLabels ? 'On' : 'Off'}
                </Button>
              </div>
              <p className="text-xs text-muted-foreground">
                Neo4j ready: {graphReady === null ? 'unknown' : graphReady ? 'yes' : 'no'}
              </p>
              <p className="text-xs text-muted-foreground">
                Nodes: {graphNodeCount ?? '-'} | Edges: {graphEdgeCount ?? '-'}
              </p>
              {graphModel.edgeLabelsSuppressed && (
                <p className="text-xs text-muted-foreground">
                  Edge labels bei vielen Kanten automatisch ausgeblendet.
                </p>
              )}
            </div>
          </CardContent>
        </Card>

        <div className="grid min-h-[70vh] gap-4">
          <Card>
            <CardHeader>
              <CardTitle>Graph Visualization</CardTitle>
              <CardDescription>
                Neo4j-Style Force Layout ({graphModel.shownNodes} Nodes, {graphModel.shownEdges} Edges).
              </CardDescription>
            </CardHeader>
            <CardContent>
              {graphModel.nvlNodes.length === 0 ? (
                <p className="text-sm text-muted-foreground">
                  Noch keine Graphdaten geladen. Nutze "Load Graph Preview".
                </p>
              ) : (
                <div className="grid gap-3">
                  <div className="h-[520px] overflow-hidden rounded-lg border border-border/70 bg-background">
                    <InteractiveNvlWrapper
                      nodes={graphModel.nvlNodes}
                      rels={graphModel.nvlRels}
                      nvlOptions={{
                        layout: ForceDirectedLayoutType,
                        renderer: 'canvas',
                        disableTelemetry: true,
                        initialZoom: 0.7,
                      }}
                      mouseEventCallbacks={{
                        onNodeClick: (node) => {
                          setSelectedGraphNodeId(node.id)
                        },
                      }}
                    />
                  </div>
                  <div className="rounded-lg border border-border/70 p-3">
                    <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                      Graph Node Details
                    </p>
                    {!graphSelectedNode ? (
                      <p className="mt-2 text-sm text-muted-foreground">
                        Klick im Graph auf einen Node, um seine Properties zu sehen.
                      </p>
                    ) : (
                      <div className="mt-2 space-y-2">
                        <p className="text-sm font-medium">{graphSelectedNode.label}</p>
                        <p className="font-mono text-xs text-muted-foreground">{graphSelectedNode.id}</p>
                        <p className="text-xs text-muted-foreground">
                          Type: {graphSelectedNode.type} | Degree: {graphModel.degree.get(graphSelectedNode.id) ?? 0}
                        </p>
                        <pre className="max-h-44 overflow-auto rounded-md bg-muted/30 p-2 text-xs">
                          {JSON.stringify(graphSelectedNode.properties, null, 2)}
                        </pre>
                      </div>
                    )}
                  </div>
                </div>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Node Overview</CardTitle>
              <CardDescription>
                Unabhängige Listen-Ansicht mit Property-Inspector.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="mb-3">
                <Input
                  value={overviewFilter}
                  onChange={(e) => setOverviewFilter(e.target.value)}
                  placeholder="Filter by label/id/type"
                />
              </div>
              <div className="grid gap-3 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
                <div className="max-h-72 overflow-auto rounded-lg border border-border/70">
                  {graphModel.overviewNodes.length === 0 ? (
                    <p className="p-3 text-sm text-muted-foreground">Keine Nodes gefunden.</p>
                  ) : (
                    <ul className="divide-y">
                      {graphModel.overviewNodes.map((node) => (
                        <li key={node.id}>
                          <button
                            onClick={() => setSelectedOverviewNodeId(node.id)}
                            className="w-full px-3 py-2 text-left hover:bg-muted/40"
                          >
                            <p className="text-sm font-medium">{node.label}</p>
                            <p className="font-mono text-xs text-muted-foreground">{node.id}</p>
                            <p className="text-xs text-muted-foreground">
                              {node.type} | degree {graphModel.degree.get(node.id) ?? 0}
                            </p>
                          </button>
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
                <div className="max-h-72 overflow-auto rounded-lg border border-border/70 p-3">
                  {!overviewSelectedNode ? (
                    <p className="text-sm text-muted-foreground">
                      Waehle links einen Node aus, um seine Properties anzuzeigen.
                    </p>
                  ) : (
                    <div className="space-y-2">
                      <p className="text-sm font-medium">{overviewSelectedNode.label}</p>
                      <p className="font-mono text-xs text-muted-foreground">{overviewSelectedNode.id}</p>
                      <p className="text-xs text-muted-foreground">
                        Labels: {overviewSelectedNode.labels.join(', ')}
                      </p>
                      <pre className="overflow-auto rounded-md bg-muted/30 p-2 text-xs">
                        {JSON.stringify(overviewSelectedNode.properties, null, 2)}
                      </pre>
                    </div>
                  )}
                </div>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Execution Log</CardTitle>
            <CardDescription>
              {logs.length} Calls, {successCount} erfolgreich
            </CardDescription>
            </CardHeader>
            <CardContent>
              {logs.length === 0 ? (
                <p className="text-sm text-muted-foreground">Noch keine Requests ausgefuehrt.</p>
              ) : (
                <div className="space-y-3">
                  {logs.map((log) => (
                    <div key={log.id} className="rounded-lg border border-border/80 bg-muted/20 p-3">
                      <div className="mb-2 flex items-center justify-between gap-2 text-xs">
                        <span className="font-mono text-muted-foreground">
                          {log.method} {log.path}
                        </span>
                        <span className={log.ok ? 'text-emerald-600' : 'text-red-600'}>
                          {log.ok ? `OK ${log.status ?? ''}` : 'ERROR'}
                        </span>
                      </div>
                      <p className="mb-2 text-sm font-medium">{log.title}</p>
                      {log.requestBody !== undefined && (
                        <pre className="mb-2 overflow-auto rounded-md bg-background p-2 text-xs">
                          {JSON.stringify(log.requestBody, null, 2)}
                        </pre>
                      )}
                      {log.responseBody !== undefined && (
                        <pre className="overflow-auto rounded-md bg-background p-2 text-xs">
                          {JSON.stringify(log.responseBody, null, 2)}
                        </pre>
                      )}
                      {log.error && (
                        <pre className="overflow-auto rounded-md bg-background p-2 text-xs text-red-600">
                          {log.error}
                        </pre>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  )
}
