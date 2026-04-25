import { createBrowserRouter, RouterProvider, Navigate } from 'react-router-dom'
import AppShell from '@/components/layout/AppShell'
import BriefingPage from '@/pages/briefing/BriefingPage'
import AccountPage from '@/pages/account/AccountPage'

const router = createBrowserRouter([
  {
    path: '/',
    element: <AppShell />,
    children: [
      { index: true, element: <Navigate to="/briefing" replace /> },
      { path: 'briefing', element: <BriefingPage /> },
      { path: 'accounts/:accountId', element: <AccountPage /> },
    ],
  },
])

export default function App() {
  return <RouterProvider router={router} />
}
