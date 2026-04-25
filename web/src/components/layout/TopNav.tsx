import { NavLink } from 'react-router-dom'
import { Database } from 'lucide-react'
import { Button } from '@/components/ui/button'

const MODES = [
  { to: '/browse', label: 'Browse' },
  { to: '/search', label: 'Search' },
  { to: '/review', label: 'Review' },
] as const

export default function TopNav() {
  return (
    <header className="flex h-12 shrink-0 items-center gap-6 border-b bg-card px-4">
      <div className="flex items-center gap-2">
        <Database className="size-4 text-primary" />
        <span className="text-sm font-semibold tracking-tight">Qontext</span>
      </div>

      <nav className="flex items-center gap-1">
        {MODES.map(({ to, label }) => (
          <NavLink key={to} to={to}>
            {({ isActive }) => (
              <Button variant={isActive ? 'secondary' : 'ghost'} size="sm">
                {label}
              </Button>
            )}
          </NavLink>
        ))}
      </nav>

      <div className="ml-auto flex items-center gap-2">
        <span className="text-xs text-muted-foreground">Context Layer</span>
      </div>
    </header>
  )
}
