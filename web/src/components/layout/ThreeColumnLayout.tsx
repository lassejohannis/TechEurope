import type { ReactNode } from 'react'

interface Props {
  left: ReactNode
  center: ReactNode
  right: ReactNode
}

export default function ThreeColumnLayout({ left, center, right }: Props) {
  return (
    <div className="grid h-full grid-cols-[280px_1fr_320px] divide-x overflow-hidden">
      <aside className="flex flex-col overflow-y-auto">{left}</aside>
      <section className="flex flex-col overflow-y-auto">{center}</section>
      <aside className="flex flex-col overflow-y-auto">{right}</aside>
    </div>
  )
}
