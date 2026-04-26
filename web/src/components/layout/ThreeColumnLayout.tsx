import type { ReactNode } from 'react'

interface Props {
  left: ReactNode
  center: ReactNode
  right: ReactNode
  leftWidthClass?: string
  rightWidthClass?: string
}

export default function ThreeColumnLayout({
  left,
  center,
  right,
  leftWidthClass = '280px',
  rightWidthClass = '320px',
}: Props) {
  return (
    <div
      className="grid h-full min-h-0 divide-x overflow-hidden"
      style={{ gridTemplateColumns: `${leftWidthClass} minmax(0, 1fr) ${rightWidthClass}` }}
    >
      <aside className="flex min-h-0 flex-col overflow-y-auto">{left}</aside>
      <section className="flex min-h-0 flex-col overflow-y-auto">{center}</section>
      <aside className="flex min-h-0 flex-col overflow-y-auto">{right}</aside>
    </div>
  )
}
