import type { CSSProperties } from 'react'

export type IconName =
  | 'compass' | 'search' | 'review' | 'users' | 'briefcase' | 'box' | 'shield'
  | 'git-branch' | 'target' | 'ticket' | 'mail' | 'chevron-right' | 'chevron-down'
  | 'folder' | 'file' | 'user' | 'edit' | 'plus' | 'link' | 'history' | 'alert'
  | 'check' | 'check-circle' | 'refresh' | 'eye' | 'share' | 'copy' | 'code'
  | 'graph' | 'thumbs-up' | 'thumbs-down' | 'sparkles' | 'send' | 'filter' | 'x'
  | 'more' | 'arrow-right' | 'lightbulb' | 'inbox' | 'scale' | 'merge'

interface IconProps {
  name: IconName | string
  size?: number
  className?: string
  style?: CSSProperties
}

export default function Icon({ name, size = 16, className = "", style = {} }: IconProps) {
  const p = {
    width: size, height: size, viewBox: "0 0 24 24",
    fill: "none", stroke: "currentColor", strokeWidth: 1.7,
    strokeLinecap: "round" as const, strokeLinejoin: "round" as const,
    className, style,
  }
  switch (name) {
    case "compass":      return <svg {...p}><circle cx="12" cy="12" r="9"/><path d="M16 8l-2.5 5.5L8 16l2.5-5.5L16 8z"/></svg>
    case "search":       return <svg {...p}><circle cx="11" cy="11" r="7"/><path d="M21 21l-4.3-4.3"/></svg>
    case "review":       return <svg {...p}><path d="M4 6h12M4 12h8M4 18h12"/><path d="M19 5l2 2-7 7-3 1 1-3 7-7z"/></svg>
    case "users":        return <svg {...p}><circle cx="9" cy="8" r="3.5"/><path d="M2.5 19c.7-3 3.4-5 6.5-5s5.8 2 6.5 5"/><circle cx="17.5" cy="9" r="2.5"/><path d="M16 14c2.6.3 4.7 2.2 5.5 5"/></svg>
    case "briefcase":    return <svg {...p}><rect x="3" y="7" width="18" height="13" rx="2"/><path d="M9 7V5a2 2 0 012-2h2a2 2 0 012 2v2"/><path d="M3 13h18"/></svg>
    case "box":          return <svg {...p}><path d="M21 8l-9-5-9 5 9 5 9-5z"/><path d="M3 8v8l9 5 9-5V8"/><path d="M12 13v8"/></svg>
    case "shield":       return <svg {...p}><path d="M12 3l8 3v5c0 5-3.5 8.7-8 10-4.5-1.3-8-5-8-10V6l8-3z"/></svg>
    case "git-branch":   return <svg {...p}><circle cx="6" cy="5" r="2"/><circle cx="6" cy="19" r="2"/><circle cx="18" cy="9" r="2"/><path d="M6 7v10M6 14a6 6 0 006-6h4"/></svg>
    case "target":       return <svg {...p}><circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="5"/><circle cx="12" cy="12" r="1.5" fill="currentColor"/></svg>
    case "ticket":       return <svg {...p}><path d="M3 9a2 2 0 002-2V5h14v2a2 2 0 000 4v2a2 2 0 000 4v2H5v-2a2 2 0 00-2-2v-2a2 2 0 002-2 2 2 0 00-2-2z"/></svg>
    case "mail":         return <svg {...p}><rect x="3" y="5" width="18" height="14" rx="2"/><path d="M3 7l9 6 9-6"/></svg>
    case "chevron-right":return <svg {...p}><path d="M9 6l6 6-6 6"/></svg>
    case "chevron-down": return <svg {...p}><path d="M6 9l6 6 6-6"/></svg>
    case "folder":       return <svg {...p}><path d="M3 7a2 2 0 012-2h4l2 2h8a2 2 0 012 2v8a2 2 0 01-2 2H5a2 2 0 01-2-2V7z"/></svg>
    case "file":         return <svg {...p}><path d="M14 3H7a2 2 0 00-2 2v14a2 2 0 002 2h10a2 2 0 002-2V8l-5-5z"/><path d="M14 3v5h5"/></svg>
    case "user":         return <svg {...p}><circle cx="12" cy="8" r="3.5"/><path d="M5 20c1-3.5 4-5 7-5s6 1.5 7 5"/></svg>
    case "edit":         return <svg {...p}><path d="M4 20h4l11-11-4-4L4 16v4z"/><path d="M14 6l4 4"/></svg>
    case "plus":         return <svg {...p}><path d="M12 5v14M5 12h14"/></svg>
    case "link":         return <svg {...p}><path d="M10 14a4 4 0 005.5 0l3-3a4 4 0 00-5.5-5.5L11.5 7"/><path d="M14 10a4 4 0 00-5.5 0l-3 3a4 4 0 005.5 5.5L12.5 17"/></svg>
    case "history":      return <svg {...p}><path d="M3 12a9 9 0 109-9 9 9 0 00-7 3.5L3 8"/><path d="M3 3v5h5"/><path d="M12 7v5l3 2"/></svg>
    case "alert":        return <svg {...p}><path d="M12 3l10 17H2L12 3z"/><path d="M12 10v4M12 17.5v.5"/></svg>
    case "check":        return <svg {...p}><path d="M5 12l4 4 10-10"/></svg>
    case "check-circle": return <svg {...p}><circle cx="12" cy="12" r="9"/><path d="M8 12l3 3 5-6"/></svg>
    case "refresh":      return <svg {...p}><path d="M21 12a9 9 0 01-15 6.7L3 16"/><path d="M3 12a9 9 0 0115-6.7L21 8"/><path d="M21 3v5h-5M3 21v-5h5"/></svg>
    case "eye":          return <svg {...p}><path d="M2 12s4-7 10-7 10 7 10 7-4 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3"/></svg>
    case "share":        return <svg {...p}><path d="M4 12v7a2 2 0 002 2h12a2 2 0 002-2v-7"/><path d="M16 6l-4-4-4 4"/><path d="M12 2v14"/></svg>
    case "copy":         return <svg {...p}><rect x="8" y="8" width="12" height="12" rx="2"/><path d="M16 8V6a2 2 0 00-2-2H6a2 2 0 00-2 2v8a2 2 0 002 2h2"/></svg>
    case "code":         return <svg {...p}><path d="M16 18l6-6-6-6M8 6l-6 6 6 6"/></svg>
    case "graph":        return <svg {...p}><circle cx="6" cy="6" r="2.5"/><circle cx="18" cy="6" r="2.5"/><circle cx="12" cy="18" r="2.5"/><path d="M8 7l3 9M16 7l-3 9"/></svg>
    case "thumbs-up":    return <svg {...p}><path d="M7 11v9H4a1 1 0 01-1-1v-7a1 1 0 011-1h3z"/><path d="M7 11l4-8a2 2 0 014 0v5h5a2 2 0 012 2.3l-1 6a2 2 0 01-2 1.7H7"/></svg>
    case "thumbs-down":  return <svg {...p}><path d="M7 13V4H4a1 1 0 00-1 1v7a1 1 0 001 1h3z"/><path d="M7 13l4 8a2 2 0 004 0v-5h5a2 2 0 002-2.3l-1-6a2 2 0 00-2-1.7H7"/></svg>
    case "sparkles":     return <svg {...p}><path d="M12 4v4M12 16v4M4 12h4M16 12h4M6 6l2 2M16 16l2 2M6 18l2-2M16 8l2-2"/></svg>
    case "send":         return <svg {...p}><path d="M22 2L11 13M22 2l-7 20-4-9-9-4 20-7z"/></svg>
    case "filter":       return <svg {...p}><path d="M3 5h18l-7 9v6l-4-2v-4L3 5z"/></svg>
    case "x":            return <svg {...p}><path d="M6 6l12 12M18 6L6 18"/></svg>
    case "more":         return <svg {...p}><circle cx="6" cy="12" r="1.5" fill="currentColor"/><circle cx="12" cy="12" r="1.5" fill="currentColor"/><circle cx="18" cy="12" r="1.5" fill="currentColor"/></svg>
    case "arrow-right":  return <svg {...p}><path d="M5 12h14M13 5l7 7-7 7"/></svg>
    case "lightbulb":    return <svg {...p}><path d="M9 18h6M10 22h4"/><path d="M12 2a6 6 0 00-4 10c1.2 1 2 2.5 2 4h4c0-1.5.8-3 2-4a6 6 0 00-4-10z"/></svg>
    case "inbox":        return <svg {...p}><path d="M22 12h-6l-2 3h-4l-2-3H2"/><path d="M5.5 5h13l3.5 7v6a2 2 0 01-2 2H4a2 2 0 01-2-2v-6L5.5 5z"/></svg>
    case "scale":        return <svg {...p}><path d="M12 3v18M5 7h14"/><path d="M5 7l-3 6a3 3 0 006 0L5 7zM19 7l-3 6a3 3 0 006 0l-3-6z"/></svg>
    case "merge":        return <svg {...p}><circle cx="6" cy="5" r="2"/><circle cx="18" cy="19" r="2"/><path d="M6 7v6a4 4 0 004 4h7"/></svg>
    default:             return <svg {...p}><circle cx="12" cy="12" r="2" fill="currentColor"/></svg>
  }
}
