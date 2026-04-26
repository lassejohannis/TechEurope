import type { Entity, SearchResultItem } from '../../types'

export type FilterConstraint = { op: 'gt' | 'gte'; value: number } | null

export interface CascadeInterpretation {
  titleTerms: string[]
  wantsTasks: boolean
  wantsTickets: boolean
  wantsConnections: boolean
  wantsPeople: boolean
  ticketConstraint: FilterConstraint
  connectionConstraint: FilterConstraint
  warnings: string[]
}

const TITLE_PATTERN =
  /(senior|lead|principal|staff|junior)?\s*(engineer|developer|manager|director|architect|analyst|consultant)/gi

const TICKET_PREDICATES = [
  'raised_ticket',
  'assigned_ticket',
  'owns_ticket',
  'ticket',
  'incident',
]

const CONNECTION_EXCLUDE_PREDICATES = [
  ...TICKET_PREDICATES,
  'email',
  'phone',
  'address',
  'url',
  'website',
]

const PEOPLE_TYPES = new Set(['person'])
const TASK_TYPES = new Set(['task', 'project', 'process'])
const TICKET_FOCUS_TYPES = new Set(['ticket', 'communication', 'person'])
const CONNECTION_TERMS = '(?:connections?|contacts?|kontakte?|verbindungen?|netzwerk)'
const TICKET_TERMS = '(?:tickets?|issues?)'

function asText(value: unknown): string {
  if (value == null) return ''
  if (typeof value === 'string') return value
  if (typeof value === 'number' || typeof value === 'boolean') return String(value)
  if (Array.isArray(value)) return value.map((v) => asText(v)).join(' ')
  if (typeof value === 'object') {
    return Object.values(value as Record<string, unknown>)
      .map((v) => asText(v))
      .join(' ')
  }
  return ''
}

function parseIntegerToken(raw: string | undefined): number | null {
  if (!raw) return null
  const digits = raw.replace(/[^\d]/g, '')
  if (!digits) return null
  const value = Number.parseInt(digits, 10)
  return Number.isFinite(value) ? value : null
}

function extractConstraint(query: string, termPattern: string): FilterConstraint {
  const patterns: Array<{ op: 'gt' | 'gte'; re: RegExp }> = [
    { op: 'gt', re: new RegExp(`(?:mehr\\s+als|ueber|über|over|>)\\s*([\\d.,_\\s]+)\\s*${termPattern}`, 'i') },
    { op: 'gte', re: new RegExp(`(?:mindestens|at\\s+least|>=|mind\\.)\\s*([\\d.,_\\s]+)\\s*${termPattern}`, 'i') },
    { op: 'gt', re: new RegExp(`${termPattern}\\s*(?:mehr\\s+als|ueber|über|over|>)\\s*([\\d.,_\\s]+)`, 'i') },
    { op: 'gte', re: new RegExp(`${termPattern}\\s*(?:mindestens|at\\s+least|>=|mind\\.)\\s*([\\d.,_\\s]+)`, 'i') },
    { op: 'gte', re: new RegExp(`([\\d.,_\\s]+)\\s*\\+\\s*${termPattern}`, 'i') },
    { op: 'gte', re: new RegExp(`${termPattern}\\s*([\\d.,_\\s]+)\\s*\\+`, 'i') },
  ]

  for (const pattern of patterns) {
    const match = query.match(pattern.re)
    const value = parseIntegerToken(match?.[1])
    if (value == null) continue
    return { op: pattern.op, value }
  }

  return null
}

function hasUnsupportedNegation(q: string): boolean {
  return /\b(ohne|kein|keine|keinen|nicht|weniger\s+als|at\s+most|max(?:imal)?|<=|<|under)\b/i.test(q)
}

function getEntityText(entity: Entity): string {
  return [
    entity.canonical_name,
    entity.aliases.join(' '),
    asText(entity.attrs),
  ]
    .join(' ')
    .toLowerCase()
}

export function parseInterpretation(query: string): CascadeInterpretation {
  const q = query.toLowerCase()

  const titleMatches = [...query.matchAll(TITLE_PATTERN)]
  const titleTerms = titleMatches
    .flatMap((m) => [m[1], m[2]])
    .filter((part): part is string => !!part)
    .map((part) => part.toLowerCase())

  const ticketConstraint = extractConstraint(query, TICKET_TERMS)
  const connectionConstraint = extractConstraint(query, CONNECTION_TERMS)

  const warnings: string[] = []
  if (hasUnsupportedNegation(q) && (/\b(tickets?|incidents?|issues?)\b/i.test(q) || /\b(connection|connections|contact|contacts|kontakt|kontakte|verbindung|verbindungen|netzwerk)\b/i.test(q))) {
    warnings.push('Negationen wie "ohne", "weniger als" oder "<=" werden aktuell nur eingeschränkt unterstützt.')
  }

  return {
    titleTerms,
    wantsTasks: /\b(workstream|task|todo|to-do|schritt|steps?)\b/i.test(q),
    wantsTickets: /\b(tickets?|incidents?|issues?)\b/i.test(q),
    wantsConnections: /\b(connection|connections|kontakt|kontakte|verbindung|verbindungen|netzwerk)\b/i.test(q),
    wantsPeople: /\b(person|personen|people|employee|employees|mitarbeiter)\b/i.test(q),
    ticketConstraint,
    connectionConstraint,
    warnings,
  }
}

export function getTicketCount(entity: Entity): number {
  return entity.facts.filter((fact) => {
    const predicate = String(fact.predicate || '').toLowerCase()
    if (TICKET_PREDICATES.some((token) => predicate.includes(token))) return true

    if (fact.object_literal == null) return false
    const literal = String(fact.object_literal).toLowerCase()
    return literal.includes('ticket') || literal.startsWith('inc-') || literal.startsWith('req-')
  }).length
}

export function getConnectionCount(entity: Entity): number {
  return new Set(
    entity.facts
      .filter((fact) => {
        if (!fact.object_id) return false
        const predicate = String(fact.predicate || '').toLowerCase()
        return !CONNECTION_EXCLUDE_PREDICATES.some((token) => predicate.includes(token))
      })
      .map((fact) => fact.object_id)
      .filter((id): id is string => typeof id === 'string' && id.length > 0),
  ).size
}

export function cascadeFilter(results: SearchResultItem[], intent: CascadeInterpretation): { filtered: SearchResultItem[]; steps: string[] } {
  let filtered = [...results]
  const steps: string[] = []

  steps.push(`Hybrid Search geliefert: ${results.length} Kandidaten`)

  if (intent.wantsPeople || intent.titleTerms.length > 0 || intent.wantsConnections || intent.connectionConstraint) {
    filtered = filtered.filter((result) => PEOPLE_TYPES.has(String(result.entity.entity_type).toLowerCase()))
    steps.push(`Personen-Fokus: ${filtered.length} übrig`)
  }

  if (intent.titleTerms.length > 0) {
    filtered = filtered.filter((result) => {
      const text = getEntityText(result.entity)
      return intent.titleTerms.every((term) => text.includes(term))
    })
    steps.push(`Titel-Filter (${intent.titleTerms.join(' + ')}): ${filtered.length} übrig`)
  }

  if (intent.ticketConstraint) {
    const constraint = intent.ticketConstraint
    filtered = filtered.filter((result) => {
      const count = getTicketCount(result.entity)
      if (constraint.op === 'gt') return count > constraint.value
      return count >= constraint.value
    })
    const opLabel = constraint.op === 'gt' ? '>' : '≥'
    steps.push(`Ticket-Filter (${opLabel} ${constraint.value}): ${filtered.length} übrig`)
  }

  if (intent.connectionConstraint) {
    const constraint = intent.connectionConstraint
    filtered = filtered.filter((result) => {
      const count = getConnectionCount(result.entity)
      if (constraint.op === 'gt') return count > constraint.value
      return count >= constraint.value
    })
    const opLabel = constraint.op === 'gt' ? '>' : '≥'
    steps.push(`Connections-Filter (${opLabel} ${constraint.value}): ${filtered.length} übrig`)
  }

  if (intent.wantsTasks && !intent.wantsTickets) {
    filtered = filtered.filter((result) => TASK_TYPES.has(String(result.entity.entity_type).toLowerCase()))
    steps.push(`Workstream/Task-Fokus: ${filtered.length} übrig`)
  }

  if (intent.wantsTickets && intent.titleTerms.length === 0 && !intent.ticketConstraint) {
    filtered = filtered.filter((result) => TICKET_FOCUS_TYPES.has(String(result.entity.entity_type).toLowerCase()))
    steps.push(`Ticket-Fokus: ${filtered.length} übrig`)
  }

  for (const warning of intent.warnings) {
    steps.push(`Hinweis: ${warning}`)
  }

  filtered.sort((a, b) => {
    if (intent.wantsConnections || intent.connectionConstraint) {
      const connectionDelta = getConnectionCount(b.entity) - getConnectionCount(a.entity)
      if (connectionDelta !== 0) return connectionDelta
    }
    const ticketDelta = getTicketCount(b.entity) - getTicketCount(a.entity)
    if (ticketDelta !== 0) return ticketDelta
    return b.score - a.score
  })

  return { filtered, steps }
}

export function describeResult(entity: Entity): string {
  const role = asText(entity.attrs).trim()
  const ticketCount = getTicketCount(entity)
  const connectionCount = getConnectionCount(entity)
  if (role) {
    return `${entity.canonical_name} · ${String(entity.entity_type)} · ${connectionCount} Connections · ${ticketCount} Tickets · ${role.slice(0, 90)}`
  }
  return `${entity.canonical_name} · ${String(entity.entity_type)} · ${connectionCount} Connections · ${ticketCount} Tickets`
}
