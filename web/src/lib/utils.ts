import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"
import type { ConfidenceLevel } from "@/types"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export function confidenceLevel(c: number): ConfidenceLevel {
  if (c >= 0.9) return 'high'
  if (c >= 0.7) return 'medium'
  if (c >= 0.5) return 'low'
  return 'very-low'
}

// Maps confidence to Tailwind classes using semantic tokens only (no raw colors)
export function confidenceClass(c: number): string {
  const level = confidenceLevel(c)
  const map: Record<ConfidenceLevel, string> = {
    high:      'bg-primary/10 text-primary',
    medium:    'bg-secondary text-secondary-foreground',
    low:       'bg-destructive/10 text-destructive',
    'very-low':'bg-destructive/20 text-destructive',
  }
  return map[level]
}
