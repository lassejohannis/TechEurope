import { Outlet } from 'react-router-dom'
import TopNav from './TopNav'

export default function AppShell() {
  return (
    <div className="app">
      <TopNav />
      <Outlet />
    </div>
  )
}
