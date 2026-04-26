import { useEffect, useMemo, useState } from 'react'
import {
  Flag,
  Plus,
  GitBranch,
  Activity,
  CheckCircle2,
  Info,
  Pencil,
  Trash2,
  Link2,
  Boxes,
} from 'lucide-react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip'
import { useEntity } from '@/hooks/useEntity'
import { useFact } from '@/hooks/useFact'
import {
  ApiError,
  deleteFact,
  editEntity,
  editFact,
  flagFact,
  getEntityProvenance,
  linkEntity,
  patchVfsNode,
  proposeFact,
} from '@/lib/api'
import type { Fact } from '@/types'

interface Props {
  entityId: string | null
}

function factValueText(fact: Fact): string {
  const value = fact.object_literal ?? fact.object_id
  if (value == null) return '—'
  if (typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean') {
    return String(value)
  }
  try {
    const json = JSON.stringify(value)
    return json.length > 80 ? `${json.slice(0, 77)}...` : json
  } catch {
    return 'structured value'
  }
}

export default function ActionPanel({ entityId }: Props) {
  const ADD_NEW_FACT_VALUE = '__add_new_fact__'
  const { data } = useEntity(entityId)
  const qc = useQueryClient()

  const [proposeOpen, setProposeOpen] = useState(false)
  const [flagOpen, setFlagOpen] = useState(false)
  const [editOpen, setEditOpen] = useState(false)
  const [deleteOpen, setDeleteOpen] = useState(false)
  const [provenanceOpen, setProvenanceOpen] = useState(false)
  const [entityNoteOpen, setEntityNoteOpen] = useState(false)
  const [entityEditOpen, setEntityEditOpen] = useState(false)
  const [linkEntityOpen, setLinkEntityOpen] = useState(false)
  const [entityProvenanceOpen, setEntityProvenanceOpen] = useState(false)

  const [predicate, setPredicate] = useState('')
  const [value, setValue] = useState('')
  const [proposeConfidence, setProposeConfidence] = useState(0.8)
  const [proposeNote, setProposeNote] = useState('')
  const [statusMsg, setStatusMsg] = useState<string | null>(null)

  const [selectedFactId, setSelectedFactId] = useState<string | null>(null)
  const [flagReason, setFlagReason] = useState('')
  const [editValue, setEditValue] = useState('')
  const [editConfidence, setEditConfidence] = useState(0.8)
  const [editNote, setEditNote] = useState('')
  const [deleteReason, setDeleteReason] = useState('')
  const [entityNote, setEntityNote] = useState('')
  const [entityName, setEntityName] = useState('')
  const [entityEditReason, setEntityEditReason] = useState('')
  const [newPropKey, setNewPropKey] = useState('')
  const [newPropValue, setNewPropValue] = useState('')
  const [linkPredicate, setLinkPredicate] = useState('')
  const [linkType, setLinkType] = useState('organization')
  const [linkName, setLinkName] = useState('')
  const [linkReason, setLinkReason] = useState('')

  const facts = data?.facts ?? []
  const liveCount = facts.filter((f) => f.status === 'live' || f.status === 'active').length
  const disputedCount = facts.filter((f) => f.status === 'disputed').length
  const staleCount = facts.filter((f) => f.status === 'needs_refresh' || f.status === 'superseded').length
  const avgConfidence = facts.length
    ? facts.reduce((sum, f) => sum + f.confidence, 0) / facts.length
    : 0
  const selectedFact = facts.find((f) => f.id === selectedFactId) ?? null
  const entityVfsPath = typeof data?.attrs?.vfs_path === 'string' ? data.attrs.vfs_path : null
  const currentEntityNote = useMemo(() => {
    const fromEntityNote = data?.attrs?.entity_note
    if (typeof fromEntityNote === 'string') return fromEntityNote
    const fromNote = data?.attrs?.note
    if (typeof fromNote === 'string') return fromNote
    return ''
  }, [data?.attrs])

  const provenanceQuery = useFact(provenanceOpen ? selectedFactId : null)
  const entityProvenanceQuery = useQuery({
    queryKey: ['entity-provenance', entityId],
    queryFn: () => getEntityProvenance(entityId!),
    enabled: Boolean(entityId && entityProvenanceOpen),
    staleTime: 60_000,
    gcTime: 10 * 60_000,
    refetchOnWindowFocus: false,
  })

  useEffect(() => {
    if (!facts.length) {
      setSelectedFactId(null)
      return
    }
    if (selectedFactId && facts.some((f) => f.id === selectedFactId)) return
    const preferred = facts.find((f) => f.status === 'live' || f.status === 'active' || f.status === 'disputed') ?? facts[0]
    setSelectedFactId(preferred.id)
  }, [facts, selectedFactId])

  useEffect(() => {
    setEntityNote(currentEntityNote)
  }, [currentEntityNote, entityId])

  useEffect(() => {
    setEntityName(data?.canonical_name ?? '')
    setNewPropKey('')
    setNewPropValue('')
    setEntityEditReason('')
    setLinkPredicate('')
    setLinkType('organization')
    setLinkName('')
    setLinkReason('')
  }, [data?.canonical_name, entityId])

  const topPredicates = useMemo(() => {
    const counts = new Map<string, number>()
    for (const f of facts) {
      counts.set(f.predicate, (counts.get(f.predicate) ?? 0) + 1)
    }
    return [...counts.entries()]
      .sort((a, b) => b[1] - a[1])
      .slice(0, 4)
  }, [facts])

  const attributeCount = useMemo(
    () => Object.values(data?.attrs ?? {}).filter((v) => v != null && String(v).trim() !== '').length,
    [data?.attrs],
  )
  const hasQualityScore = facts.length > 0

  const proposeMutation = useMutation({
    mutationFn: async () => {
      if (!entityId) throw new Error('No entity selected')
      return proposeFact({
        subject_id: entityId,
        predicate: predicate.trim(),
        object_literal: value.trim(),
        confidence: proposeConfidence,
        source_system: 'browse_ui',
        source_method: 'human_input',
        note: proposeNote.trim() || undefined,
      })
    },
    onSuccess: () => {
      setStatusMsg('Fact proposed successfully.')
      setProposeOpen(false)
      setPredicate('')
      setValue('')
      setProposeConfidence(0.8)
      setProposeNote('')
      qc.invalidateQueries({ queryKey: ['entity', entityId] })
    },
    onError: (error: unknown) => {
      if (error instanceof ApiError) {
        setStatusMsg(`Could not propose fact (${error.status}).`)
        return
      }
      setStatusMsg('Could not propose fact.')
    },
  })

  const flagMutation = useMutation({
    mutationFn: async () => {
      if (!selectedFactId) throw new Error('No fact selected')
      return flagFact(selectedFactId, flagReason.trim())
    },
    onSuccess: () => {
      setStatusMsg('Fact flagged as disputed.')
      setFlagOpen(false)
      setFlagReason('')
      qc.invalidateQueries({ queryKey: ['entity', entityId] })
      if (selectedFactId) qc.invalidateQueries({ queryKey: ['fact', selectedFactId] })
    },
    onError: (error: unknown) => {
      if (error instanceof ApiError) {
        setStatusMsg(`Could not flag fact (${error.status}).`)
        return
      }
      setStatusMsg('Could not flag fact.')
    },
  })

  const editMutation = useMutation({
    mutationFn: async () => {
      if (!selectedFactId) throw new Error('No fact selected')
      return editFact(selectedFactId, {
        object_literal: editValue.trim(),
        confidence: editConfidence,
        note: editNote.trim() || undefined,
      })
    },
    onSuccess: () => {
      setStatusMsg('Fact edited successfully.')
      setEditOpen(false)
      setEditNote('')
      qc.invalidateQueries({ queryKey: ['entity', entityId] })
      if (selectedFactId) qc.invalidateQueries({ queryKey: ['fact', selectedFactId] })
    },
    onError: (error: unknown) => {
      if (error instanceof ApiError) {
        setStatusMsg(`Could not edit fact (${error.status}).`)
        return
      }
      setStatusMsg('Could not edit fact.')
    },
  })

  const deleteMutation = useMutation({
    mutationFn: async () => {
      if (!selectedFactId) throw new Error('No fact selected')
      return deleteFact(selectedFactId, deleteReason.trim() || undefined)
    },
    onSuccess: () => {
      setStatusMsg('Fact deleted (invalidated).')
      setDeleteOpen(false)
      setDeleteReason('')
      qc.invalidateQueries({ queryKey: ['entity', entityId] })
      if (selectedFactId) qc.invalidateQueries({ queryKey: ['fact', selectedFactId] })
    },
    onError: (error: unknown) => {
      if (error instanceof ApiError) {
        setStatusMsg(`Could not delete fact (${error.status}).`)
        return
      }
      setStatusMsg('Could not delete fact.')
    },
  })

  const entityNoteMutation = useMutation({
    mutationFn: async () => {
      if (!entityVfsPath) throw new Error('Entity path unavailable')
      return patchVfsNode(
        entityVfsPath,
        { entity_note: entityNote.trim() || null },
        'Updated entity note from browse UI',
      )
    },
    onSuccess: () => {
      setStatusMsg('Entity note updated.')
      setEntityNoteOpen(false)
      qc.invalidateQueries({ queryKey: ['entity', entityId] })
    },
    onError: (error: unknown) => {
      if (error instanceof ApiError) {
        setStatusMsg(`Could not update entity note (${error.status}).`)
        return
      }
      setStatusMsg('Could not update entity note.')
    },
  })

  const entityEditMutation = useMutation({
    mutationFn: async () => {
      if (!entityId) throw new Error('No entity selected')
      const attrs = newPropKey.trim()
        ? { [newPropKey.trim()]: newPropValue.trim() || null }
        : undefined
      return editEntity(entityId, {
        canonical_name: entityName.trim() || undefined,
        attrs,
        reason: entityEditReason.trim() || undefined,
      })
    },
    onSuccess: () => {
      setStatusMsg('Entity updated successfully.')
      setEntityEditOpen(false)
      setNewPropKey('')
      setNewPropValue('')
      setEntityEditReason('')
      qc.invalidateQueries({ queryKey: ['entity', entityId] })
      qc.invalidateQueries({ queryKey: ['entity-provenance', entityId] })
    },
    onError: (error: unknown) => {
      if (error instanceof ApiError) {
        setStatusMsg(`Could not update entity (${error.status}).`)
        return
      }
      setStatusMsg('Could not update entity.')
    },
  })

  const linkEntityMutation = useMutation({
    mutationFn: async () => {
      if (!entityId) throw new Error('No entity selected')
      return linkEntity(entityId, {
        predicate: linkPredicate.trim(),
        target_entity_type: linkType.trim(),
        target_canonical_name: linkName.trim(),
        reason: linkReason.trim() || undefined,
      })
    },
    onSuccess: () => {
      setStatusMsg('Linked entity created/connected.')
      setLinkEntityOpen(false)
      setLinkPredicate('')
      setLinkName('')
      setLinkReason('')
      qc.invalidateQueries({ queryKey: ['entity', entityId] })
      qc.invalidateQueries({ queryKey: ['entity-provenance', entityId] })
    },
    onError: (error: unknown) => {
      if (error instanceof ApiError) {
        setStatusMsg(`Could not link entity (${error.status}).`)
        return
      }
      setStatusMsg('Could not link entity.')
    },
  })

  function openEditForFact(f: Fact) {
    setSelectedFactId(f.id)
    setEditValue(String(f.object_literal ?? f.object_id ?? ''))
    setEditConfidence(f.confidence)
    setEditNote('')
    setEditOpen(true)
  }

  function openFlagForFact(f: Fact) {
    setSelectedFactId(f.id)
    setFlagReason('')
    setFlagOpen(true)
  }

  function openDeleteForFact(f: Fact) {
    setSelectedFactId(f.id)
    setDeleteReason('')
    setDeleteOpen(true)
  }

  function openProvenanceForFact(f: Fact) {
    setSelectedFactId(f.id)
    setProvenanceOpen(true)
  }

  function getDefaultFact(): Fact | null {
    return selectedFact ?? facts[0] ?? null
  }

  function openFlagDialog() {
    const fallback = getDefaultFact()
    if (fallback) setSelectedFactId(fallback.id)
    setFlagReason('')
    setFlagOpen(true)
  }

  function openProvenanceDialog() {
    const fallback = getDefaultFact()
    if (fallback) setSelectedFactId(fallback.id)
    setProvenanceOpen(true)
  }

  function openEditDialog() {
    const fallback = getDefaultFact()
    if (fallback) {
      openEditForFact(fallback)
      return
    }
    setEditValue('')
    setEditNote('')
    setEditOpen(true)
  }

  function openDeleteDialog() {
    const fallback = getDefaultFact()
    if (fallback) {
      openDeleteForFact(fallback)
      return
    }
    setDeleteReason('')
    setDeleteOpen(true)
  }

  function selectFactForEdit(factId: string) {
    const fact = facts.find((f) => f.id === factId)
    if (!fact) return
    setSelectedFactId(fact.id)
    setEditValue(String(fact.object_literal ?? fact.object_id ?? ''))
    setEditConfidence(fact.confidence)
  }

  function openProposeFromDialog(closeDialog: () => void) {
    closeDialog()
    setProposeOpen(true)
  }

  function openEntityNoteDialog() {
    setEntityNote(currentEntityNote)
    setEntityNoteOpen(true)
  }

  function openEntityEditDialog() {
    setEntityName(data?.canonical_name ?? '')
    setEntityEditOpen(true)
  }

  function openLinkEntityDialog() {
    setLinkEntityOpen(true)
  }

  function openEntityProvenanceDialog() {
    setEntityProvenanceOpen(true)
  }

  function updateProposeConfidencePercent(next: string) {
    const parsed = Number(next)
    if (!Number.isFinite(parsed)) return
    const clamped = Math.min(100, Math.max(0, parsed))
    setProposeConfidence(clamped / 100)
  }

  function updateEditConfidencePercent(next: string) {
    const parsed = Number(next)
    if (!Number.isFinite(parsed)) return
    const clamped = Math.min(100, Math.max(0, parsed))
    setEditConfidence(clamped / 100)
  }

  if (!entityId) {
    return (
      <div className="flex flex-1 flex-col items-center justify-center gap-3 p-6 text-center">
        <p className="text-sm text-muted-foreground">
          Select an entity to see insights, key attributes, and quick actions.
        </p>
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-4 p-4">
      <Card size="sm">
        <CardHeader className="pb-2">
          <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
            Insights
          </p>
          {data && <CardTitle className="truncate">{data.canonical_name}</CardTitle>}
          <div className="flex flex-wrap gap-1">
            <Badge variant="secondary">{data?.entity_type}</Badge>
            <Badge variant="outline">{facts.length} facts</Badge>
            <TooltipProvider>
              <Tooltip>
                <TooltipTrigger>
                  <Badge variant="outline" className="inline-flex items-center gap-1">
                    Data Quality {hasQualityScore ? `${Math.round((data?.trust_score ?? 0) * 100)}%` : 'No score yet'}
                    <Info className="size-3" />
                  </Badge>
                </TooltipTrigger>
                <TooltipContent>
                  Score = avg confidence × source diversity × recency.
                </TooltipContent>
              </Tooltip>
            </TooltipProvider>
          </div>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="grid grid-cols-3 gap-2">
            <div className="rounded-md border bg-muted/30 p-2">
              <p className="text-[11px] text-muted-foreground">Live</p>
              <p className="text-sm font-semibold">{liveCount}</p>
            </div>
            <div className="rounded-md border bg-muted/30 p-2">
              <p className="text-[11px] text-muted-foreground">Disputed</p>
              <p className="text-sm font-semibold">{disputedCount}</p>
            </div>
            <div className="rounded-md border bg-muted/30 p-2">
              <p className="text-[11px] text-muted-foreground">Stale</p>
              <p className="text-sm font-semibold">{staleCount}</p>
            </div>
          </div>
          <div className="flex items-center justify-between text-xs text-muted-foreground">
            <span className="inline-flex items-center gap-1">
              <Activity className="size-3.5" /> Avg confidence
            </span>
            <span className="font-medium text-foreground">{Math.round(avgConfidence * 100)}%</span>
          </div>
        </CardContent>
      </Card>

      <Card size="sm">
        <CardHeader className="pb-2">
          <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Quick Actions</p>
        </CardHeader>
        <CardContent className="space-y-2">
          <Button
            variant="outline"
            size="sm"
            className="w-full justify-start gap-2"
            onClick={() => setProposeOpen(true)}
          >
            <Plus className="size-4" />
            Propose fact
          </Button>
          <Button
            variant="outline"
            size="sm"
            className="w-full justify-start gap-2"
            onClick={openFlagDialog}
          >
            <Flag className="size-4" />
            Flag Facts
          </Button>
          <Button
            variant="outline"
            size="sm"
            className="w-full justify-start gap-2"
            onClick={openProvenanceDialog}
          >
            <GitBranch className="size-4" />
            View Provenance
          </Button>
          <Button
            variant="outline"
            size="sm"
            className="w-full justify-start gap-2"
            onClick={openEditDialog}
          >
            <Pencil className="size-4" />
            Edit Item
          </Button>
          <Button
            variant="outline"
            size="sm"
            className="w-full justify-start gap-2 text-destructive hover:text-destructive"
            onClick={openDeleteDialog}
          >
            <Trash2 className="size-4" />
            Delete Item
          </Button>
          <Button
            variant="outline"
            size="sm"
            className="w-full justify-start gap-2"
            onClick={openEntityNoteDialog}
          >
            <Pencil className="size-4" />
            Entity Note
          </Button>
          <Button
            variant="outline"
            size="sm"
            className="w-full justify-start gap-2"
            onClick={openEntityEditDialog}
          >
            <Boxes className="size-4" />
            Edit Entity Data
          </Button>
          <Button
            variant="outline"
            size="sm"
            className="w-full justify-start gap-2"
            onClick={openLinkEntityDialog}
          >
            <Link2 className="size-4" />
            Link New Entity
          </Button>
          <Button
            variant="outline"
            size="sm"
            className="w-full justify-start gap-2"
            onClick={openEntityProvenanceDialog}
          >
            <GitBranch className="size-4" />
            Entity Provenance
          </Button>
          {statusMsg && (
            <p className="inline-flex items-center gap-1 text-xs text-muted-foreground">
              <CheckCircle2 className="size-3.5" />
              {statusMsg}
            </p>
          )}
        </CardContent>
      </Card>

      <Card size="sm">
        <CardHeader className="pb-2">
          <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Fact Items</p>
        </CardHeader>
        <CardContent className="space-y-2">
          {facts.length === 0 ? (
            <p className="text-xs text-muted-foreground">No facts available.</p>
          ) : (
            facts.slice(0, 16).map((fact) => (
              <div
                key={fact.id}
                className={`rounded-md border p-2 ${
                  fact.id === selectedFactId ? 'border-primary/50 bg-primary/5' : 'bg-muted/20'
                }`}
              >
                <button
                  type="button"
                  className="w-full text-left"
                  onClick={() => setSelectedFactId(fact.id)}
                >
                  <p className="text-xs font-semibold text-foreground">
                    {fact.predicate.replace(/_/g, ' ')}
                  </p>
                  <p className="truncate text-xs text-muted-foreground">
                    {factValueText(fact)}
                  </p>
                </button>
                <div className="mt-2 flex flex-wrap gap-1">
                  <Button size="sm" variant="outline" className="h-7 px-2 text-[11px]" onClick={() => openEditForFact(fact)}>
                    Edit
                  </Button>
                  <Button size="sm" variant="outline" className="h-7 px-2 text-[11px]" onClick={() => openFlagForFact(fact)}>
                    Flag
                  </Button>
                  <Button size="sm" variant="outline" className="h-7 px-2 text-[11px]" onClick={() => openProvenanceForFact(fact)}>
                    Trace
                  </Button>
                  <Button size="sm" variant="outline" className="h-7 px-2 text-[11px]" onClick={() => openDeleteForFact(fact)}>
                    Delete
                  </Button>
                </div>
              </div>
            ))
          )}
        </CardContent>
      </Card>

      <Card size="sm">
        <CardHeader className="pb-2">
          <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Coverage</p>
        </CardHeader>
        <CardContent className="space-y-2">
          <div className="grid grid-cols-2 gap-2 text-xs">
            <div className="rounded-md border bg-muted/30 p-2">
              <p className="text-muted-foreground">Attributes</p>
              <p className="font-semibold text-foreground">{attributeCount}</p>
            </div>
            <div className="rounded-md border bg-muted/30 p-2">
              <p className="text-muted-foreground">Predicates</p>
              <p className="font-semibold text-foreground">{topPredicates.length}</p>
            </div>
          </div>
          <div>
            <p className="mb-1 text-[11px] font-medium uppercase tracking-wide text-muted-foreground">Top Predicates</p>
            {topPredicates.length === 0 ? (
              <p className="text-xs text-muted-foreground">No facts available.</p>
            ) : (
              <div className="flex flex-wrap gap-1">
                {topPredicates.map(([pred, count]) => (
                  <Badge key={pred} variant="outline">
                    {pred.replace(/_/g, ' ')} ({count})
                  </Badge>
                ))}
              </div>
            )}
          </div>
        </CardContent>
      </Card>

      {disputedCount > 0 && (
        <div className="rounded-md border border-destructive/30 bg-destructive/5 p-3">
          <p className="text-xs font-medium text-destructive">
            {disputedCount} conflict
            {disputedCount > 1 ? 's' : ''} pending
          </p>
          <p className="mt-0.5 text-xs text-muted-foreground">
            Go to Review mode to resolve.
          </p>
        </div>
      )}

      <Dialog open={proposeOpen} onOpenChange={setProposeOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Propose a fact</DialogTitle>
          </DialogHeader>
          <div className="flex flex-col gap-3 py-2">
            <div className="flex flex-col gap-1.5">
              <label className="text-sm font-medium">Subject</label>
              <Input value={entityId} disabled className="font-mono text-xs" />
            </div>
            <div className="flex flex-col gap-1.5">
              <label className="text-sm font-medium">Predicate</label>
              <Input
                placeholder="e.g. renewal_date, email, department"
                value={predicate}
                onChange={(e) => setPredicate(e.target.value)}
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <label className="text-sm font-medium">Value</label>
              <Input
                placeholder="Enter value"
                value={value}
                onChange={(e) => setValue(e.target.value)}
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <label className="text-sm font-medium">Confidence</label>
              <Input
                type="number"
                min={0}
                max={100}
                step={0.1}
                value={Number((proposeConfidence * 100).toFixed(1))}
                onChange={(e) => updateProposeConfidencePercent(e.target.value)}
              />
              <p className="text-xs text-muted-foreground">Enter a value between 0 and 100.</p>
            </div>
            <div className="flex flex-col gap-1.5">
              <label className="text-sm font-medium">Note</label>
              <Input
                placeholder="Optional note"
                value={proposeNote}
                onChange={(e) => setProposeNote(e.target.value)}
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setProposeOpen(false)}>
              Cancel
            </Button>
            <Button
              disabled={!predicate.trim() || !value.trim() || proposeMutation.isPending}
              onClick={() => proposeMutation.mutate()}
            >
              {proposeMutation.isPending ? 'Saving…' : 'Propose'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={flagOpen} onOpenChange={setFlagOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Flag Facts</DialogTitle>
          </DialogHeader>
          <div className="flex flex-col gap-2 py-2">
            <div className="flex flex-col gap-1.5">
              <label className="text-sm font-medium">Fact</label>
              <select
                className="h-9 rounded-md border bg-background px-3 text-sm"
                value={selectedFactId ?? ''}
                onChange={(e) => {
                  const next = e.target.value
                  if (next === ADD_NEW_FACT_VALUE) {
                    openProposeFromDialog(() => setFlagOpen(false))
                    return
                  }
                  setSelectedFactId(next || null)
                }}
              >
                <option value="">Select a fact</option>
                <option value={ADD_NEW_FACT_VALUE}>+ Add new fact</option>
                {facts.map((fact) => (
                  <option key={fact.id} value={fact.id}>
                    {fact.predicate}: {factValueText(fact)}
                  </option>
                ))}
              </select>
            </div>
            {facts.length === 0 && (
              <Button size="sm" variant="outline" className="w-fit" onClick={() => openProposeFromDialog(() => setFlagOpen(false))}>
                <Plus className="size-4" />
                Add new fact
              </Button>
            )}
            <p className="text-xs text-muted-foreground">
              {selectedFact ? `${selectedFact.predicate}: ${factValueText(selectedFact)}` : 'No fact selected'}
            </p>
            <Input
              placeholder="Reason (required)"
              value={flagReason}
              onChange={(e) => setFlagReason(e.target.value)}
            />
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setFlagOpen(false)}>
              Cancel
            </Button>
            <Button
              disabled={!selectedFactId || flagReason.trim().length < 3 || flagMutation.isPending}
              onClick={() => flagMutation.mutate()}
            >
              {flagMutation.isPending ? 'Flagging…' : 'Flag Fact'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={editOpen} onOpenChange={setEditOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Edit Fact Item</DialogTitle>
          </DialogHeader>
          <div className="flex flex-col gap-3 py-2">
            <div className="flex flex-col gap-1.5">
              <label className="text-sm font-medium">Fact</label>
              <select
                className="h-9 rounded-md border bg-background px-3 text-sm"
                value={selectedFactId ?? ''}
                onChange={(e) => {
                  const next = e.target.value
                  if (next === ADD_NEW_FACT_VALUE) {
                    openProposeFromDialog(() => setEditOpen(false))
                    return
                  }
                  selectFactForEdit(next)
                }}
              >
                <option value="">Select a fact</option>
                <option value={ADD_NEW_FACT_VALUE}>+ Add new fact</option>
                {facts.map((fact) => (
                  <option key={fact.id} value={fact.id}>
                    {fact.predicate}: {factValueText(fact)}
                  </option>
                ))}
              </select>
            </div>
            {facts.length === 0 && (
              <Button size="sm" variant="outline" className="w-fit" onClick={() => openProposeFromDialog(() => setEditOpen(false))}>
                <Plus className="size-4" />
                Add new fact
              </Button>
            )}
            <p className="text-xs text-muted-foreground">
              {selectedFact ? `Predicate: ${selectedFact.predicate}` : 'No fact selected'}
            </p>
            <div className="flex flex-col gap-1.5">
              <label className="text-sm font-medium">New value</label>
              <Input value={editValue} onChange={(e) => setEditValue(e.target.value)} />
            </div>
            <div className="flex flex-col gap-1.5">
              <label className="text-sm font-medium">Confidence</label>
              <Input
                type="number"
                min={0}
                max={100}
                step={0.1}
                value={Number((editConfidence * 100).toFixed(1))}
                onChange={(e) => updateEditConfidencePercent(e.target.value)}
              />
              <p className="text-xs text-muted-foreground">Enter a value between 0 and 100.</p>
            </div>
            <div className="flex flex-col gap-1.5">
              <label className="text-sm font-medium">Note</label>
              <Input
                placeholder="Optional note"
                value={editNote}
                onChange={(e) => setEditNote(e.target.value)}
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setEditOpen(false)}>
              Cancel
            </Button>
            <Button
              disabled={!selectedFactId || !editValue.trim() || editMutation.isPending}
              onClick={() => editMutation.mutate()}
            >
              {editMutation.isPending ? 'Saving…' : 'Save Edit'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={deleteOpen} onOpenChange={setDeleteOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete Fact Item</DialogTitle>
          </DialogHeader>
          <div className="flex flex-col gap-2 py-2">
            <div className="flex flex-col gap-1.5">
              <label className="text-sm font-medium">Fact</label>
              <select
                className="h-9 rounded-md border bg-background px-3 text-sm"
                value={selectedFactId ?? ''}
                onChange={(e) => {
                  const next = e.target.value
                  if (next === ADD_NEW_FACT_VALUE) {
                    openProposeFromDialog(() => setDeleteOpen(false))
                    return
                  }
                  setSelectedFactId(next || null)
                }}
              >
                <option value="">Select a fact</option>
                <option value={ADD_NEW_FACT_VALUE}>+ Add new fact</option>
                {facts.map((fact) => (
                  <option key={fact.id} value={fact.id}>
                    {fact.predicate}: {factValueText(fact)}
                  </option>
                ))}
              </select>
            </div>
            {facts.length === 0 && (
              <Button size="sm" variant="outline" className="w-fit" onClick={() => openProposeFromDialog(() => setDeleteOpen(false))}>
                <Plus className="size-4" />
                Add new fact
              </Button>
            )}
            <p className="text-xs text-muted-foreground">
              {selectedFact ? `${selectedFact.predicate}: ${factValueText(selectedFact)}` : 'No fact selected'}
            </p>
            <Input
              placeholder="Reason (optional)"
              value={deleteReason}
              onChange={(e) => setDeleteReason(e.target.value)}
            />
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteOpen(false)}>
              Cancel
            </Button>
            <Button
              variant="destructive"
              disabled={!selectedFactId || deleteMutation.isPending}
              onClick={() => deleteMutation.mutate()}
            >
              {deleteMutation.isPending ? 'Deleting…' : 'Delete'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={provenanceOpen} onOpenChange={setProvenanceOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Fact Provenance</DialogTitle>
          </DialogHeader>
          <div className="mb-2 flex flex-col gap-1.5">
            <label className="text-sm font-medium">Fact</label>
            <select
              className="h-9 rounded-md border bg-background px-3 text-sm"
              value={selectedFactId ?? ''}
              onChange={(e) => {
                const next = e.target.value
                if (next === ADD_NEW_FACT_VALUE) {
                  openProposeFromDialog(() => setProvenanceOpen(false))
                  return
                }
                setSelectedFactId(next || null)
              }}
            >
              <option value="">Select a fact</option>
              <option value={ADD_NEW_FACT_VALUE}>+ Add new fact</option>
              {facts.map((fact) => (
                <option key={fact.id} value={fact.id}>
                  {fact.predicate}: {factValueText(fact)}
                </option>
              ))}
            </select>
          </div>
          {facts.length === 0 && (
            <Button size="sm" variant="outline" className="mb-2 w-fit" onClick={() => openProposeFromDialog(() => setProvenanceOpen(false))}>
              <Plus className="size-4" />
              Add new fact
            </Button>
          )}
          {!selectedFactId ? (
            <p className="text-sm text-muted-foreground">No fact selected.</p>
          ) : provenanceQuery.isLoading ? (
            <p className="text-sm text-muted-foreground">Loading provenance…</p>
          ) : provenanceQuery.isError || !provenanceQuery.data ? (
            <p className="text-sm text-muted-foreground">Could not load provenance.</p>
          ) : (
            <div className="flex flex-col gap-2 py-1 text-sm">
              <p><span className="font-medium">Fact:</span> {provenanceQuery.data.fact.predicate}</p>
              <p><span className="font-medium">Source system:</span> {provenanceQuery.data.source_reference.system}</p>
              <p><span className="font-medium">Source path:</span> {provenanceQuery.data.source_reference.path ?? '—'}</p>
              <p><span className="font-medium">Record:</span> {provenanceQuery.data.source_reference.record_id ?? '—'}</p>
              <p><span className="font-medium">Method:</span> {provenanceQuery.data.source_reference.method}</p>
              <p><span className="font-medium">Timestamp:</span> {provenanceQuery.data.source_reference.timestamp ?? '—'}</p>
            </div>
          )}
          <DialogFooter>
            <Button variant="outline" onClick={() => setProvenanceOpen(false)}>
              Close
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={entityNoteOpen} onOpenChange={setEntityNoteOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Entity Note</DialogTitle>
          </DialogHeader>
          <div className="flex flex-col gap-2 py-2">
            <p className="text-xs text-muted-foreground">
              Add a note for the whole entity.
            </p>
            <textarea
              className="min-h-28 w-full rounded-md border bg-background px-3 py-2 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring"
              placeholder="Write note..."
              value={entityNote}
              onChange={(e) => setEntityNote(e.target.value)}
            />
            {!entityVfsPath && (
              <p className="text-xs text-destructive">
                Entity path is missing, note cannot be saved for this item.
              </p>
            )}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setEntityNoteOpen(false)}>
              Cancel
            </Button>
            <Button
              disabled={!entityVfsPath || entityNoteMutation.isPending}
              onClick={() => entityNoteMutation.mutate()}
            >
              {entityNoteMutation.isPending ? 'Saving…' : 'Save Note'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={entityEditOpen} onOpenChange={setEntityEditOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Edit Entity Data</DialogTitle>
          </DialogHeader>
          <div className="flex flex-col gap-3 py-2">
            <div className="flex flex-col gap-1.5">
              <label className="text-sm font-medium">Entity Name</label>
              <Input
                value={entityName}
                onChange={(e) => setEntityName(e.target.value)}
                placeholder="Canonical name"
              />
            </div>
            <div className="grid grid-cols-2 gap-2">
              <div className="flex flex-col gap-1.5">
                <label className="text-sm font-medium">New Property Key</label>
                <Input
                  value={newPropKey}
                  onChange={(e) => setNewPropKey(e.target.value)}
                  placeholder="e.g. document_type"
                />
              </div>
              <div className="flex flex-col gap-1.5">
                <label className="text-sm font-medium">New Property Value</label>
                <Input
                  value={newPropValue}
                  onChange={(e) => setNewPropValue(e.target.value)}
                  placeholder="e.g. policy_pdf"
                />
              </div>
            </div>
            <p className="text-xs text-muted-foreground">
              Leave property value empty to remove the property.
            </p>
            <div className="flex flex-col gap-1.5">
              <label className="text-sm font-medium">Reason</label>
              <Input
                value={entityEditReason}
                onChange={(e) => setEntityEditReason(e.target.value)}
                placeholder="Optional audit reason"
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setEntityEditOpen(false)}>
              Cancel
            </Button>
            <Button
              disabled={entityEditMutation.isPending || (!entityName.trim() && !newPropKey.trim())}
              onClick={() => entityEditMutation.mutate()}
            >
              {entityEditMutation.isPending ? 'Saving…' : 'Save Entity Changes'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={linkEntityOpen} onOpenChange={setLinkEntityOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Link New Entity</DialogTitle>
          </DialogHeader>
          <div className="flex flex-col gap-3 py-2">
            <div className="grid grid-cols-2 gap-2">
              <div className="flex flex-col gap-1.5">
                <label className="text-sm font-medium">Predicate</label>
                <Input
                  value={linkPredicate}
                  onChange={(e) => setLinkPredicate(e.target.value)}
                  placeholder="e.g. references"
                />
              </div>
              <div className="flex flex-col gap-1.5">
                <label className="text-sm font-medium">Target Type</label>
                <Input
                  value={linkType}
                  onChange={(e) => setLinkType(e.target.value)}
                  placeholder="e.g. document, organization, policy"
                />
              </div>
            </div>
            <div className="flex flex-col gap-1.5">
              <label className="text-sm font-medium">Target Name</label>
              <Input
                value={linkName}
                onChange={(e) => setLinkName(e.target.value)}
                placeholder="e.g. Compliance Handbook 2026"
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <label className="text-sm font-medium">Reason</label>
              <Input
                value={linkReason}
                onChange={(e) => setLinkReason(e.target.value)}
                placeholder="Optional audit reason"
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setLinkEntityOpen(false)}>
              Cancel
            </Button>
            <Button
              disabled={linkEntityMutation.isPending || !linkPredicate.trim() || !linkType.trim() || !linkName.trim()}
              onClick={() => linkEntityMutation.mutate()}
            >
              {linkEntityMutation.isPending ? 'Linking…' : 'Create & Link'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={entityProvenanceOpen} onOpenChange={setEntityProvenanceOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Entity Provenance</DialogTitle>
          </DialogHeader>
          {entityProvenanceQuery.isLoading ? (
            <p className="text-sm text-muted-foreground">Loading provenance…</p>
          ) : entityProvenanceQuery.isError || !entityProvenanceQuery.data ? (
            <p className="text-sm text-muted-foreground">Could not load entity provenance.</p>
          ) : (
            <div className="flex max-h-[60vh] flex-col gap-3 overflow-auto py-1 text-sm">
              <div className="rounded-md border bg-muted/20 p-3 text-xs">
                <p><span className="font-medium">Entity:</span> {entityProvenanceQuery.data.canonical_name}</p>
                <p><span className="font-medium">Type:</span> {entityProvenanceQuery.data.entity_type}</p>
                <p>
                  <span className="font-medium">Conflicts:</span>{' '}
                  disputed {entityProvenanceQuery.data.conflicts.disputed_facts},
                  pending fact {entityProvenanceQuery.data.conflicts.pending_fact_resolutions},
                  pending entity {entityProvenanceQuery.data.conflicts.pending_entity_resolutions}
                </p>
              </div>
              <div>
                <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground">Sources</p>
                <div className="space-y-1.5">
                  {entityProvenanceQuery.data.sources.length === 0 ? (
                    <p className="text-xs text-muted-foreground">No source records.</p>
                  ) : entityProvenanceQuery.data.sources.map((s) => (
                    <div key={s.source_id} className="rounded-md border p-2 text-xs">
                      <p><span className="font-medium">{s.source_type}</span> · {s.event_type}</p>
                      <p>facts: {s.fact_count}</p>
                      <p className="text-muted-foreground">{s.timestamp ?? '—'}</p>
                    </div>
                  ))}
                </div>
              </div>
              <div>
                <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground">Edits</p>
                <div className="space-y-1.5">
                  {entityProvenanceQuery.data.edits.length === 0 ? (
                    <p className="text-xs text-muted-foreground">No edits tracked.</p>
                  ) : entityProvenanceQuery.data.edits.slice(0, 30).map((e) => (
                    <div key={String(e.id)} className="rounded-md border p-2 text-xs">
                      <p><span className="font-medium">{e.kind}</span> · fact {e.fact_id ?? '—'}</p>
                      <p className="text-muted-foreground">{e.triggered_by ?? 'unknown'} · {e.at}</p>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}
          <DialogFooter>
            <Button variant="outline" onClick={() => setEntityProvenanceOpen(false)}>
              Close
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
