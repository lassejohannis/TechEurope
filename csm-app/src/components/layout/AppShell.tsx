import { Outlet } from 'react-router-dom'
import TopBar from './TopBar'
import ToastManager from '@/components/common/ToastManager'

export default function AppShell() {
  return (
    <div className="csm-app">
      <TopBar />
      <main className="csm-main">
        <Outlet />
      </main>
      <ToastManager />
    </div>
  )
}
