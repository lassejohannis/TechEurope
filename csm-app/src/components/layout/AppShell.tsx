import { Outlet } from 'react-router-dom'
import TopBar from './TopBar'

export default function AppShell() {
  return (
    <div className="csm-app">
      <TopBar />
      <main className="csm-main">
        <Outlet />
      </main>
    </div>
  )
}
