import {
  cascadeFilter,
  getConnectionCount,
  getTicketCount,
  parseInterpretation,
} from '../src/pages/search/searchLogic.ts'
import type { Entity, Fact, SearchResultItem } from '../src/types'

function makeFact(overrides: Partial<Fact>): Fact {
  return {
    id: `f_${Math.random().toString(36).slice(2, 10)}`,
    subject_id: 'p1',
    predicate: 'related_to',
    object_id: null,
    object_literal: null,
    confidence: 1,
    derivation: 'test',
    valid_from: '2024-01-01T00:00:00Z',
    valid_to: null,
    recorded_at: '2024-01-01T00:00:00Z',
    source_id: 's1',
    status: 'live',
    evidence: [],
    ...overrides,
  }
}

function makeEntity(id: string, entity_type: string, facts: Fact[], attrs: Record<string, unknown> = {}): Entity {
  return {
    id,
    entity_type,
    canonical_name: id,
    aliases: [],
    attrs,
    trust_score: 0.5,
    fact_count: facts.length,
    source_diversity: 1,
    facts,
  }
}

function makeResult(entity: Entity, score: number): SearchResultItem {
  return { entity, score, match_type: 'hybrid', evidence: [] }
}

const alice = makeEntity(
  'Alice',
  'person',
  [
    makeFact({ object_id: 'p2', predicate: 'works_with' }),
    makeFact({ object_id: 'p3', predicate: 'reports_to' }),
    makeFact({ object_id: 't1', predicate: 'assigned_ticket' }),
  ],
  { title: 'Senior Engineer' },
)
const bob = makeEntity(
  'Bob',
  'person',
  [
    makeFact({ object_id: 'p2', predicate: 'works_with' }),
    makeFact({ object_id: 'p3', predicate: 'works_with' }),
    makeFact({ object_id: 'p4', predicate: 'works_with' }),
    makeFact({ object_id: 'inc-1', predicate: 'raised_ticket' }),
    makeFact({ object_literal: 'INC-42', predicate: 'note' }),
  ],
  { title: 'Junior Engineer' },
)
const policyDoc = makeEntity(
  'Doc',
  'document',
  [makeFact({ object_id: 'policy-1', predicate: 'references' })],
)

const results: SearchResultItem[] = [
  makeResult(alice, 0.92),
  makeResult(bob, 0.84),
  makeResult(policyDoc, 0.99),
]

type TestCase = { name: string; run: () => void }
const tests: TestCase[] = []

function test(name: string, run: () => void): void {
  tests.push({ name, run })
}

function assert(condition: boolean, message: string): void {
  if (!condition) throw new Error(message)
}

test('parse > connections (de)', () => {
  const intent = parseInterpretation('Personen mit mehr als 40 Connections')
  assert(intent.connectionConstraint?.op === 'gt', 'op should be gt')
  assert(intent.connectionConstraint?.value === 40, 'value should be 40')
  assert(intent.wantsConnections, 'should want connections')
})

test('parse >= connections (en)', () => {
  const intent = parseInterpretation('people with at least 25 contacts')
  assert(intent.connectionConstraint?.op === 'gte', 'op should be gte')
  assert(intent.connectionConstraint?.value === 25, 'value should be 25')
})

test('parse 40+ shorthand', () => {
  const intent = parseInterpretation('show me 40+ connections')
  assert(intent.connectionConstraint?.op === 'gte', '40+ should map to gte')
  assert(intent.connectionConstraint?.value === 40, '40+ should map to 40')
})

test('parse ticket threshold', () => {
  const intent = parseInterpretation('Senior Engineer mit über 3 Tickets')
  assert(intent.ticketConstraint?.op === 'gt', 'tickets should parse gt')
  assert(intent.ticketConstraint?.value === 3, 'tickets value should be 3')
})

test('negation warning', () => {
  const intent = parseInterpretation('Personen mit weniger als 3 Tickets')
  assert(intent.warnings.length > 0, 'should include warning for unsupported negation')
})

test('ticket count excludes unrelated literals', () => {
  assert(getTicketCount(alice) === 1, 'alice should have 1 ticket')
  assert(getTicketCount(bob) === 2, 'bob should have 2 tickets')
})

test('connection count excludes ticket predicates', () => {
  assert(getConnectionCount(alice) === 2, 'alice should have 2 connections')
  assert(getConnectionCount(bob) === 3, 'bob should have 3 connections')
})

test('connections query applies person focus', () => {
  const intent = parseInterpretation('connections über 1')
  const { filtered } = cascadeFilter(results, intent)
  assert(filtered.every((r) => r.entity.entity_type === 'person'), 'only person entities expected')
})

test('connections filter works', () => {
  const intent = parseInterpretation('personen mit mindestens 3 connections')
  const { filtered } = cascadeFilter(results, intent)
  assert(filtered.length === 1 && filtered[0]?.entity.id === 'Bob', 'only bob should match')
})

test('sorting by connections first for connection queries', () => {
  const intent = parseInterpretation('zeige personen nach connections')
  const { filtered } = cascadeFilter(results, intent)
  assert(filtered[0]?.entity.id === 'Bob', 'bob should rank first by connections')
})

test('title filter and person focus', () => {
  const intent = parseInterpretation('Senior Engineer')
  const { filtered } = cascadeFilter(results, intent)
  assert(filtered.length === 1 && filtered[0]?.entity.id === 'Alice', 'title filter should match alice')
})

let passed = 0
let failed = 0
for (const t of tests) {
  try {
    t.run()
    console.log(`PASS ${t.name}`)
    passed += 1
  } catch (err) {
    console.log(`FAIL ${t.name}: ${(err as Error).message}`)
    failed += 1
  }
}

console.log(`\nSummary: ${passed}/${tests.length} passed, ${failed} failed`)
if (failed > 0) {
  process.exitCode = 1
}
