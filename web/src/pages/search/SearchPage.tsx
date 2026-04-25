import { useState } from 'react'
import { Search } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { EntityTypeBadge } from '@/components/entity/EntityTypeBadge'
import { ConfidencePill } from '@/components/entity/ConfidencePill'
import { useSearch } from '@/hooks/useSearch'
import { useNavigate } from 'react-router-dom'
import type { SearchParams } from '@/types'

export default function SearchPage() {
  const navigate = useNavigate()
  const [inputValue, setInputValue] = useState('')
  const [submittedParams, setSubmittedParams] = useState<SearchParams | null>(null)

  const { data, isLoading, isError } = useSearch(submittedParams)

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!inputValue.trim()) return
    setSubmittedParams({ query: inputValue.trim() })
  }

  const hasResults =
    data &&
    (data.entities.length > 0 || data.facts.length > 0 || data.files.length > 0)

  return (
    <div className="flex flex-col items-center gap-6 p-8">
      <div className="w-full max-w-2xl">
        <form onSubmit={handleSubmit} className="flex gap-2">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              placeholder="Ask anything about your organization…"
              className="pl-9"
            />
          </div>
          <Button type="submit" disabled={isLoading || !inputValue.trim()}>
            {isLoading ? 'Searching…' : 'Search'}
          </Button>
        </form>

        {!submittedParams && (
          <p className="mt-4 text-center text-sm text-muted-foreground">
            Try: "Who manages Acme GmbH?" or "What are the open renewal dates?"
          </p>
        )}
      </div>

      {submittedParams && (
        <div className="w-full max-w-2xl flex flex-col gap-4">
          {isLoading && (
            <p className="text-sm text-muted-foreground">Searching context base…</p>
          )}

          {isError && (
            <Card>
              <CardContent className="pt-4">
                <p className="text-sm text-muted-foreground">
                  Backend not yet available. Search will work once the API is live.
                </p>
              </CardContent>
            </Card>
          )}

          {data && !hasResults && (
            <p className="text-sm text-muted-foreground text-center">
              No entities or facts matched. Try different terms or relax your confidence filter.
            </p>
          )}

          {data?.query_interpretation && (
            <div className="flex flex-wrap items-center gap-1.5 text-xs text-muted-foreground">
              <span>Interpreted as:</span>
              <Badge variant="outline">{data.query_interpretation.intent}</Badge>
              {data.query_interpretation.entities_mentioned.map((e) => (
                <Badge key={e} variant="secondary">{e}</Badge>
              ))}
            </div>
          )}

          {data && data.entities.length > 0 && (
            <section className="flex flex-col gap-2">
              <h2 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                Entities
              </h2>
              {data.entities.map((entity) => (
                <Card
                  key={entity.id}
                  className="cursor-pointer hover:border-primary/50 transition-all"
                  onClick={() => navigate(`/browse/${encodeURIComponent(entity.id)}`)}
                >
                  <CardHeader className="pb-2">
                    <div className="flex items-center gap-2">
                      <EntityTypeBadge type={entity.type} />
                      <CardTitle className="text-base">{entity.canonical_name}</CardTitle>
                    </div>
                  </CardHeader>
                </Card>
              ))}
            </section>
          )}

          {data && data.facts.length > 0 && (
            <section className="flex flex-col gap-2">
              <h2 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                Facts
              </h2>
              {data.facts.map((fact) => (
                <Card key={fact.id}>
                  <CardContent className="flex items-start justify-between gap-2 pt-4">
                    <div className="flex flex-col gap-0.5">
                      <span className="text-xs text-muted-foreground capitalize">
                        {fact.predicate.replace(/_/g, ' ')}
                      </span>
                      <span className="text-sm">{fact.object === null ? '—' : String(fact.object)}</span>
                    </div>
                    <ConfidencePill confidence={fact.confidence} />
                  </CardContent>
                </Card>
              ))}
            </section>
          )}

          {data && data.files.length > 0 && (
            <section className="flex flex-col gap-2">
              <h2 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                Documents
              </h2>
              {data.files.map((file) => (
                <Card
                  key={file.path}
                  className="cursor-pointer hover:border-primary/50 transition-all"
                  onClick={() => navigate(`/browse/${encodeURIComponent(file.entity_id)}`)}
                >
                  <CardContent className="pt-4">
                    <p className="font-mono text-xs text-muted-foreground">{file.path}</p>
                    <p className="mt-1 text-sm">{file.snippet}</p>
                  </CardContent>
                </Card>
              ))}
            </section>
          )}
        </div>
      )}
    </div>
  )
}
