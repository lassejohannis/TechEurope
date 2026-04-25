import type { MockSource, ConfLevel, MockRelationTarget } from '@/lib/inazuma-mock'

const SRC_TYPE_META: Record<string, { abbr: string; label: string }> = {
  email:  { abbr: "EM", label: "Email" },
  crm:    { abbr: "CR", label: "CRM" },
  hr:     { abbr: "HR", label: "HR" },
  policy: { abbr: "PO", label: "Policy" },
  ticket: { abbr: "TK", label: "Ticket" },
  chat:   { abbr: "CH", label: "Chat" },
  doc:    { abbr: "DC", label: "Doc" },
}

const CONF_LABELS: Record<ConfLevel, string> = {
  high: "High", med: "Medium", low: "Low", conflict: "Conflict",
}

export function ConfBadge({ level, label }: { level: ConfLevel; label?: string }) {
  return <span className={`conf-badge ${level}`}>{label ?? CONF_LABELS[level]}</span>
}

export function SourceBadge({ src, mini }: { src: MockSource; mini?: boolean }) {
  const meta = SRC_TYPE_META[src.type] ?? { abbr: "??", label: src.type }
  if (mini) {
    return <span className={`src-mini ${src.type}`} title={src.name}>{meta.abbr}</span>
  }
  const short = src.name.split("—")[0].trim().split("·")[0].trim()
  return (
    <span className={`src-badge ${src.type}`} title={src.name}>
      <span className="src-dot" />
      <span className="src-name">{short}</span>
      <span className="src-meta">· {meta.label}</span>
    </span>
  )
}

export function SourceMiniStack({
  srcs,
  sources,
  max = 4,
}: {
  srcs: string[]
  sources: Record<string, MockSource>
  max?: number
}) {
  const list = srcs.slice(0, max).map((id) => sources[id]).filter(Boolean)
  const overflow = srcs.length - max
  return (
    <span className="src-mini-stack">
      {list.map((s) => <SourceBadge key={s.id} src={s} mini />)}
      {overflow > 0 && <span className="src-mini doc">+{overflow}</span>}
    </span>
  )
}

export function EntityPill({ entity }: { entity: MockRelationTarget & { name: string; type: string; initials: string } }) {
  return (
    <span className="entity-pill">
      <span className="ep-icon">{entity.initials}</span>
      <span className="ep-name">{entity.name}</span>
      <span className="ep-type">{entity.type}</span>
    </span>
  )
}

export function Kbd({ children }: { children: React.ReactNode }) {
  return <span className="kbd">{children}</span>
}
