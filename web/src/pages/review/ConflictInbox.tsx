import { useNavigate } from 'react-router-dom'
import { cn } from '@/lib/utils'
import { Badge } from '@/components/ui/badge'
import { CheckCircle } from 'lucide-react'
import type { DisputedFact } from '@/types'

// Static mock disputes — replaced by real API when backend is live
const MOCK_DISPUTES: DisputedFact[] = [
  {
    id: 'fact:abc001',
    subject: 'customer:acme-gmbh',
    predicate: 'renewal_date',
    object: '2026-06-30',
    object_type: 'date',
    confidence: 0.72,
    status: 'disputed',
    derived_from: ['email:sha256:aaa', 'crm:sha256:bbb'],
    qualifiers: {},
    created_at: '2026-04-20T10:00:00Z',
    updated_at: '2026-04-24T15:30:00Z',
    superseded_by: null,
  },
  {
    id: 'fact:abc002',
    subject: 'person:alice-schmidt',
    predicate: 'email',
    object: 'alice@example.com',
    object_type: 'string',
    confidence: 0.85,
    status: 'disputed',
    derived_from: ['email:sha256:ccc', 'crm:sha256:ddd'],
    qualifiers: {},
    created_at: '2026-04-22T08:00:00Z',
    updated_at: '2026-04-25T09:00:00Z',
    superseded_by: null,
  },
  {
    id: 'fact:abc003',
    subject: 'customer:techcorp-ag',
    predicate: 'account_owner',
    object: 'person:bob-mueller',
    object_type: 'entity',
    confidence: 0.65,
    status: 'disputed',
    derived_from: ['crm:sha256:eee'],
    qualifiers: {},
    created_at: '2026-04-23T14:00:00Z',
    updated_at: '2026-04-25T11:00:00Z',
    superseded_by: null,
  },
]

interface Props {
  selectedId: string | null
}

export default function ConflictInbox({ selectedId }: Props) {
  const navigate = useNavigate()

  return (
    <div className="flex flex-col">
      <div className="border-b px-3 py-2">
        <div className="flex items-center justify-between">
          <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
            Conflict Inbox
          </p>
          {MOCK_DISPUTES.length > 0 && (
            <Badge variant="destructive" className="text-xs">
              {MOCK_DISPUTES.length}
            </Badge>
          )}
        </div>
      </div>

      {MOCK_DISPUTES.length === 0 ? (
        <div className="flex flex-col items-center gap-2 p-6 text-center">
          <CheckCircle className="size-6 text-muted-foreground/40" />
          <p className="text-sm text-muted-foreground">
            No conflicts to review. Conflicts appear here when two sources disagree on the same fact.
          </p>
        </div>
      ) : (
        <ul className="flex flex-col py-1">
          {MOCK_DISPUTES.map((fact) => {
            const isActive = selectedId === fact.id
            return (
              <li key={fact.id}>
                <button
                  onClick={() => navigate(`/review/${encodeURIComponent(fact.id)}`)}
                  className={cn(
                    'flex w-full flex-col gap-1 px-3 py-3 text-left transition-colors hover:bg-muted/50',
                    isActive && 'bg-muted',
                  )}
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-sm font-medium capitalize">
                      {fact.predicate.replace(/_/g, ' ')}
                    </span>
                    <Badge variant="destructive" className="text-xs shrink-0">
                      conflict
                    </Badge>
                  </div>
                  <span className="text-xs text-muted-foreground font-mono truncate">
                    {fact.subject}
                  </span>
                  <span className="text-xs text-muted-foreground">
                    {new Date(fact.updated_at).toLocaleDateString()}
                  </span>
                </button>
              </li>
            )
          })}
        </ul>
      )}
    </div>
  )
}
