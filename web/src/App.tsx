import { useQuery } from "@tanstack/react-query"
import { Button } from "@/components/ui/button"

type Hello = { message: string }

async function fetchHello(): Promise<Hello> {
  const res = await fetch("/api/hello")
  if (!res.ok) throw new Error(`API ${res.status}`)
  return res.json()
}

export default function App() {
  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ["hello"],
    queryFn: fetchHello,
  })

  return (
    <main className="min-h-screen flex items-center justify-center bg-background text-foreground">
      <div className="max-w-xl w-full px-6 py-12 space-y-8">
        <header className="space-y-2">
          <p className="text-sm uppercase tracking-wider text-muted-foreground">
            Tech Europe Hack 2026 · Qontext Track
          </p>
          <h1 className="text-4xl font-semibold tracking-tight">Boilerplate live.</h1>
          <p className="text-muted-foreground">
            Vite + React + TS + Tailwind v4 + shadcn/ui + TanStack Query, talking to a FastAPI backend.
          </p>
        </header>

        <section className="rounded-lg border bg-card p-6 space-y-3">
          <h2 className="text-lg font-medium">Backend handshake</h2>
          {isLoading && <p className="text-muted-foreground">Calling /api/hello…</p>}
          {isError && (
            <p className="text-destructive">
              Error: {error instanceof Error ? error.message : String(error)}
            </p>
          )}
          {data && (
            <p>
              <span className="text-muted-foreground">Server says:</span>{" "}
              <span className="font-medium">{data.message}</span>
            </p>
          )}
          <Button variant="outline" onClick={() => refetch()}>
            Re-ping
          </Button>
        </section>

        <footer className="text-sm text-muted-foreground">
          Day-1 work fills in the Core Context Engine + Revenue Intelligence App on top of this scaffold.
        </footer>
      </div>
    </main>
  )
}
