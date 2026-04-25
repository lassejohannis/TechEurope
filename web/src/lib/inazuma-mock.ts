// Inazuma sample data — realistic enterprise content for the Context Layer demo.

export type SourceType = 'hr' | 'crm' | 'email' | 'policy' | 'ticket' | 'chat' | 'doc'

export interface MockSource {
  id: string
  type: SourceType
  name: string
  uri: string
  date: string
  from?: string
}

export type ConfLevel = 'high' | 'med' | 'low' | 'conflict'

export interface MockFact {
  key: string
  val: string
  conf: ConfLevel
  srcs: string[]
  mono?: boolean
  link?: string
  disputed?: boolean
  note?: string
}

export interface MockRelationTarget {
  id: string
  name: string
  type: string
  initials: string
}

export interface MockRelation {
  pred: string
  target: MockRelationTarget
  conf: ConfLevel
  srcs: string[]
}

export interface MockSourceRecord {
  id: string
  date: string
  facts: number
}

export interface MockActivity {
  ts: string
  text: string
  icon: string
}

export interface MockEntityStats {
  facts: number
  sources: number
  derived: number
  lastSync: string
}

export interface MockEntity {
  id: string
  type: string
  canonical_name: string
  aliases: string[]
  avatar: string
  crumbs: string[]
  eyebrow: string
  status: string
  facts: MockFact[]
  relations: MockRelation[]
  sourceRecords: MockSourceRecord[]
  activity: MockActivity[]
  stats: MockEntityStats
}

export type MockTreeSection = { kind: 'section'; label: string }
export type MockTreeFolder = {
  id: string; kind: 'folder'; label: string
  icon?: string; count?: number; open?: boolean
  children?: MockTreeItem[]
}
export type MockTreeEntity = {
  id: string; kind: 'entity'; label: string; type: string
  confidence: ConfLevel; active?: boolean
}
export type MockTreeItem = MockTreeSection | MockTreeFolder | MockTreeEntity

export interface MockClaim {
  letter: string
  sourceLabel: string
  sourceName: string
  srcType: SourceType
  value: string
  unit: string
  quote: string
  meta: Record<string, string>
  srcId: string
}

export interface MockConflict {
  id: string
  unread: boolean
  active?: boolean
  subject: string
  pred: string
  time: string
  entity?: string
  since?: string
  severity: 'high' | 'med' | 'low'
  stake?: string
  claimA?: MockClaim
  claimB?: MockClaim
  preferred?: string
}

export interface InazumaMock {
  sources: Record<string, MockSource>
  tree: MockTreeItem[]
  acme: MockEntity
  conflicts: MockConflict[]
  search: {
    query: string
    answer: {
      paragraphs: string[]
      evidence: Array<{
        n: number
        srcType: SourceType
        title: string
        quote: string
        meta: string[]
        conf: ConfLevel
      }>
    }
  }
}

const sources: Record<string, MockSource> = {
  "src:hr:E0142":      { id: "src:hr:E0142",      type: "hr",     name: "Workday HR — Employee E-0142",            uri: "workday://employees/E-0142",                 date: "2025-09-01" },
  "src:hr:E0203":      { id: "src:hr:E0203",      type: "hr",     name: "Workday HR — Employee E-0203",            uri: "workday://employees/E-0203",                 date: "2025-11-12" },
  "src:hr:E0288":      { id: "src:hr:E0288",      type: "hr",     name: "Workday HR — Employee E-0288",            uri: "workday://employees/E-0288",                 date: "2024-06-04" },
  "src:hr:roster":     { id: "src:hr:roster",     type: "hr",     name: "Workday HR — Sales Org Chart",           uri: "workday://orgchart/sales",                   date: "2026-04-01" },
  "src:crm:acme":      { id: "src:crm:acme",      type: "crm",    name: "Salesforce — Account ACME-7741",         uri: "salesforce://accounts/0019000001a8Cm9",      date: "2026-04-18" },
  "src:crm:meridian":  { id: "src:crm:meridian",  type: "crm",    name: "Salesforce — Account MERI-4423",         uri: "salesforce://accounts/0019000001bX2Bn",      date: "2026-04-21" },
  "src:crm:northstar": { id: "src:crm:northstar", type: "crm",    name: "Salesforce — Account NRTH-9921",         uri: "salesforce://accounts/0019000001cY8Aj",      date: "2026-03-30" },
  "src:crm:opp:acme":  { id: "src:crm:opp:acme", type: "crm",    name: "Salesforce — Opportunity 2026 Renewal",  uri: "salesforce://opps/0061r00000ABc1",           date: "2026-04-12" },
  "src:email:1":       { id: "src:email:1",       type: "email",  name: "Re: ACME renewal — pricing proposal",    uri: "outlook://messages/CAK123@inazuma.com",      date: "2026-04-12", from: "alice.schmidt@inazuma.com" },
  "src:email:2":       { id: "src:email:2",       type: "email",  name: "ACME — confirmed renewal terms",         uri: "outlook://messages/CAK998@inazuma.com",      date: "2026-04-22", from: "j.barros@acme-gmbh.de" },
  "src:email:3":       { id: "src:email:3",       type: "email",  name: "Meridian — Q2 expansion ask",           uri: "outlook://messages/CAK552@inazuma.com",      date: "2026-04-19" },
  "src:email:4":       { id: "src:email:4",       type: "email",  name: "PTO request — 2026-05-12 to 2026-05-19",uri: "outlook://messages/CAK771@inazuma.com",      date: "2026-04-08" },
  "src:policy:contract":{ id: "src:policy:contract",type: "policy",name: "Contract Approval Policy v3.2",        uri: "confluence://wiki/policies/contract-approval-v3-2", date: "2025-11-04" },
  "src:policy:discount":{ id: "src:policy:discount",type: "policy",name: "Discount Authority Matrix",            uri: "confluence://wiki/policies/discount-authority",date: "2026-01-15" },
  "src:policy:pto":    { id: "src:policy:pto",    type: "policy", name: "Paid Time Off Policy — EU",             uri: "confluence://wiki/policies/pto-eu",          date: "2025-08-22" },
  "src:ticket:8821":   { id: "src:ticket:8821",   type: "ticket", name: "JIRA INZ-8821 — Acme price adjustment", uri: "jira://INZ-8821",                            date: "2026-04-15" },
  "src:ticket:8915":   { id: "src:ticket:8915",   type: "ticket", name: "JIRA INZ-8915 — Meridian SSO setup",    uri: "jira://INZ-8915",                            date: "2026-04-20" },
  "src:chat:slack1":   { id: "src:chat:slack1",   type: "chat",   name: "Slack #sales-emea — pricing thread",    uri: "slack://C04A2/p1713004500",                  date: "2026-04-13" },
  "src:doc:onepage":   { id: "src:doc:onepage",   type: "doc",    name: "ACME 2026 Renewal — One-Pager",         uri: "drive://docs/acme-renewal-2026",             date: "2026-04-20" },
}

const tree: MockTreeItem[] = [
  { kind: "section", label: "Static" },
  { id: "fold:people", kind: "folder", label: "People", icon: "users", count: 184, children: [
    { id: "fold:sales", kind: "folder", label: "Sales", count: 22, children: [
      { id: "ent:alice",   kind: "entity", label: "Alice Schmidt",  type: "person", confidence: "high" },
      { id: "ent:lukas",   kind: "entity", label: "Lukas Faulkner", type: "person", confidence: "high" },
      { id: "ent:nora",    kind: "entity", label: "Nora Park",      type: "person", confidence: "med" },
      { id: "ent:jose",    kind: "entity", label: "José Barros",    type: "person", confidence: "high" },
    ]},
    { id: "fold:ops", kind: "folder", label: "Operations", count: 14, children: [
      { id: "ent:miyako",  kind: "entity", label: "Miyako Tanaka",  type: "person", confidence: "high" },
      { id: "ent:dev",     kind: "entity", label: "Devansh Rao",    type: "person", confidence: "med" },
    ]},
    { id: "fold:finance", kind: "folder", label: "Finance",    count: 8 },
    { id: "fold:hr",      kind: "folder", label: "People Ops", count: 6 },
  ]},
  { id: "fold:cust", kind: "folder", label: "Customers", icon: "briefcase", count: 47, open: true, children: [
    { id: "ent:acme",      kind: "entity", label: "ACME GmbH",         type: "customer", confidence: "conflict", active: true },
    { id: "ent:meridian",  kind: "entity", label: "Meridian Robotics", type: "customer", confidence: "high" },
    { id: "ent:northstar", kind: "entity", label: "Northstar Energy",  type: "customer", confidence: "med" },
    { id: "ent:helix",     kind: "entity", label: "Helix Biotech",     type: "customer", confidence: "high" },
    { id: "ent:cinder",    kind: "entity", label: "Cinder Logistics",  type: "customer", confidence: "low" },
  ]},
  { id: "fold:prod", kind: "folder", label: "Products", icon: "box", count: 6, children: [
    { id: "ent:p:flow",    kind: "entity", label: "Inazuma Flow",  type: "product", confidence: "high" },
    { id: "ent:p:atlas",   kind: "entity", label: "Inazuma Atlas", type: "product", confidence: "high" },
    { id: "ent:p:relay",   kind: "entity", label: "Inazuma Relay", type: "product", confidence: "high" },
  ]},
  { kind: "section", label: "Procedural" },
  { id: "fold:policies", kind: "folder", label: "Policies", icon: "shield", count: 31, children: [
    { id: "ent:pol:contract", kind: "entity", label: "Contract Approval",          type: "policy", confidence: "high" },
    { id: "ent:pol:discount", kind: "entity", label: "Discount Authority Matrix",  type: "policy", confidence: "high" },
    { id: "ent:pol:pto",      kind: "entity", label: "Paid Time Off — EU",        type: "policy", confidence: "high" },
    { id: "ent:pol:expense",  kind: "entity", label: "Travel & Expense",           type: "policy", confidence: "med" },
  ]},
  { id: "fold:sops", kind: "folder", label: "Processes & SOPs", icon: "git-branch", count: 19 },
  { kind: "section", label: "Trajectory" },
  { id: "fold:projects", kind: "folder", label: "Projects", icon: "target", count: 12, children: [
    { id: "ent:prj:renewal", kind: "entity", label: "ACME Renewal 2026",    type: "project", confidence: "med" },
    { id: "ent:prj:sso",     kind: "entity", label: "Meridian SSO Rollout", type: "project", confidence: "high" },
  ]},
  { id: "fold:tickets", kind: "folder", label: "Tickets",      icon: "ticket", count: 142 },
  { id: "fold:emails",  kind: "folder", label: "Email Threads", icon: "mail",   count: 1284 },
]

const acme: MockEntity = {
  id: "ent:acme",
  type: "customer",
  canonical_name: "ACME GmbH",
  aliases: ["ACME", "Acme Industries DE", "ACME-7741"],
  avatar: "AC",
  crumbs: ["Customers", "ACME GmbH"],
  eyebrow: "Customer · DACH",
  status: "Active customer · 5 yr",
  facts: [
    { key: "Legal name",      val: "Acme GmbH",             conf: "high",     srcs: ["src:crm:acme", "src:hr:roster"] },
    { key: "Customer ID",     val: "ACME-7741",             conf: "high",     srcs: ["src:crm:acme"], mono: true },
    { key: "Headquarters",    val: "München, Germany",      conf: "high",     srcs: ["src:crm:acme"] },
    { key: "Industry",        val: "Industrial automation", conf: "high",     srcs: ["src:crm:acme", "src:doc:onepage"] },
    { key: "Account manager", val: "Alice Schmidt",         conf: "high",     srcs: ["src:hr:roster", "src:crm:acme"], link: "ent:alice" },
    { key: "Customer since",  val: "2021-03-14",            conf: "high",     srcs: ["src:crm:acme"] },
    { key: "Renewal date",    val: "2026-06-15",            conf: "conflict", disputed: true, srcs: ["src:crm:acme", "src:email:1"], note: "Conflicts with email:CAK998 (2026-08-31)" },
    { key: "Contract value",  val: "€ 152,000 / yr",        conf: "med",      srcs: ["src:crm:opp:acme", "src:email:1"] },
    { key: "Discount tier",   val: "Tier 2 (15%)",          conf: "med",      srcs: ["src:crm:opp:acme"] },
    { key: "Net Promoter",    val: "+42",                   conf: "low",      srcs: ["src:doc:onepage"] },
  ],
  relations: [
    { pred: "account_manager_of", target: { id: "ent:alice",      name: "Alice Schmidt",           type: "person",  initials: "AS" }, conf: "high", srcs: ["src:hr:roster"] },
    { pred: "uses_product",       target: { id: "ent:p:flow",     name: "Inazuma Flow",            type: "product", initials: "IF" }, conf: "high", srcs: ["src:crm:acme"] },
    { pred: "uses_product",       target: { id: "ent:p:atlas",    name: "Inazuma Atlas",           type: "product", initials: "IA" }, conf: "high", srcs: ["src:crm:opp:acme"] },
    { pred: "in_renewal",         target: { id: "ent:prj:renewal",name: "ACME Renewal 2026",       type: "project", initials: "AR" }, conf: "med",  srcs: ["src:crm:opp:acme", "src:email:1"] },
    { pred: "active_ticket",      target: { id: "ent:tkt:8821",   name: "INZ-8821 · Price adj.",   type: "ticket",  initials: "TK" }, conf: "high", srcs: ["src:ticket:8821"] },
    { pred: "primary_contact",    target: { id: "ent:jose",       name: "José Barros (ACME)",      type: "person",  initials: "JB" }, conf: "high", srcs: ["src:email:2", "src:crm:acme"] },
    { pred: "governed_by",        target: { id: "ent:pol:contract",name: "Contract Approval v3.2", type: "policy",  initials: "CP" }, conf: "high", srcs: ["src:policy:contract"] },
  ],
  sourceRecords: [
    { id: "src:crm:acme",        date: "2026-04-18", facts: 7 },
    { id: "src:crm:opp:acme",    date: "2026-04-12", facts: 4 },
    { id: "src:email:1",         date: "2026-04-12", facts: 3 },
    { id: "src:email:2",         date: "2026-04-22", facts: 2 },
    { id: "src:doc:onepage",     date: "2026-04-20", facts: 5 },
    { id: "src:ticket:8821",     date: "2026-04-15", facts: 2 },
    { id: "src:policy:contract", date: "2025-11-04", facts: 1 },
  ],
  activity: [
    { ts: "2h ago",    text: "Source <strong>email:CAK998</strong> ingested — re-derived 2 facts.", icon: "refresh" },
    { ts: "Today",     text: "<strong>Renewal date</strong> entered <strong>disputed</strong> state — pending resolution.", icon: "alert" },
    { ts: "Yesterday", text: "Fact <strong>contract_value</strong> updated to € 152,000 (was € 148,500).", icon: "edit" },
    { ts: "3 days",    text: "Linked entity <strong>Project: ACME Renewal 2026</strong> created.", icon: "link" },
    { ts: "1 wk",      text: "Alice Schmidt confirmed as <strong>account_manager_of</strong> (HR sync).", icon: "check" },
  ],
  stats: { facts: 24, sources: 7, derived: 14, lastSync: "2 min ago" },
}

const conflicts: MockConflict[] = [
  {
    id: "conf:1", unread: true, active: true,
    subject: "ACME GmbH — renewal_date", pred: "renewal_date", time: "2h",
    entity: "customer:acme-gmbh", since: "Today, 11:42",
    severity: "high", stake: "Blocks renewal forecast in Sales Pipeline view",
    claimA: {
      letter: "A", sourceLabel: "Source A — CRM", sourceName: "Salesforce · Account ACME-7741", srcType: "crm",
      value: "2026-06-15", unit: "",
      quote: "Subscription renewal_date <mark>2026-06-15</mark>; auto-renew flag = true. Last edited by m.koestler@inazuma.com.",
      meta: { Confidence: "0.92", Updated: "2026-04-18", Author: "m.koestler", "Record ID": "0019000001a8Cm9" },
      srcId: "src:crm:acme",
    },
    claimB: {
      letter: "B", sourceLabel: "Source B — Email", sourceName: "j.barros@acme-gmbh.de · Apr 22", srcType: "email",
      value: "2026-08-31", unit: "",
      quote: "Hi Alice — confirming our internal alignment, the renewal will move to <mark>Aug 31, 2026</mark> to align with our fiscal close. Paperwork by July.",
      meta: { Confidence: "0.84", Updated: "2026-04-22", Author: "j.barros@acme-gmbh.de", "Message-ID": "<CAK998@inazuma.com>" },
      srcId: "src:email:2",
    },
    preferred: "B",
  },
  { id: "conf:2", unread: true,  subject: "Meridian Robotics — discount_tier",    pred: "discount_tier",    time: "5h", severity: "med" },
  { id: "conf:3", unread: false, subject: "Lukas Faulkner — reports_to",          pred: "reports_to",       time: "1d", severity: "low" },
  { id: "conf:4", unread: false, subject: "Northstar Energy — primary_contact",   pred: "primary_contact",  time: "2d", severity: "med" },
  { id: "conf:5", unread: false, subject: "Cinder Logistics — billing_address",   pred: "billing_address",  time: "3d", severity: "low" },
]

export const INAZUMA: InazumaMock = {
  sources,
  tree,
  acme,
  conflicts,
  search: {
    query: "When does the ACME contract renew and who's on it?",
    answer: {
      paragraphs: [
        'The ACME GmbH renewal is currently <span data-cite="2">disputed</span>. The Salesforce CRM record lists the renewal date as <strong>2026-06-15</strong><span data-cite="1"></span>, but a confirmation email from José Barros at ACME (Apr 22) states the date has been moved to <strong>2026-08-31</strong> to align with their fiscal close<span data-cite="2"></span>.',
        'The deal is owned by <strong>Alice Schmidt</strong> (Senior Account Manager, Sales)<span data-cite="3"></span>, with <strong>José Barros</strong> as the primary contact at ACME<span data-cite="2"></span>. The opportunity is currently sized at <strong>€ 152,000 / yr</strong> across Inazuma Flow and Inazuma Atlas<span data-cite="4"></span>, with an open ticket (INZ-8821) requesting a price adjustment<span data-cite="5"></span>.',
        'A Review-mode resolution is pending on the renewal date. Until resolved, downstream forecasts will surface both candidates flagged.',
      ],
      evidence: [
        { n: 1, srcType: "crm",    title: "Salesforce — Account ACME-7741",          quote: 'renewal_date = <mark>2026-06-15</mark>, auto_renew = true, owner = alice.schmidt', meta: ["salesforce://accounts/0019000001a8Cm9", "Updated 2026-04-18"], conf: "high" },
        { n: 2, srcType: "email",  title: "ACME — confirmed renewal terms",           quote: 'the renewal will move to <mark>Aug 31, 2026</mark> to align with our fiscal close. Paperwork by July.', meta: ["from j.barros@acme-gmbh.de", "Apr 22, 14:08"], conf: "high" },
        { n: 3, srcType: "hr",     title: "Workday — Sales org chart",                quote: 'Alice Schmidt — Senior Account Manager, EMEA Sales. Owns: ACME-7741, MERI-4423, NRTH-9921.', meta: ["workday://orgchart/sales", "Synced 2026-04-01"], conf: "high" },
        { n: 4, srcType: "crm",    title: "Salesforce — Opportunity 2026 Renewal",    quote: 'Amount = <mark>€ 152,000</mark> · Products: Flow (seat), Atlas (platform). Stage: Negotiation.', meta: ["salesforce://opps/0061r00000ABc1", "Updated 2026-04-12"], conf: "med" },
        { n: 5, srcType: "ticket", title: "JIRA INZ-8821 — Acme price adjustment",   quote: 'Customer requesting <mark>3% price adjustment</mark> tied to volume increase. Pending Finance review.', meta: ["jira://INZ-8821", "Status: In Progress"], conf: "high" },
      ],
    },
  },
}
