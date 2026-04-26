import { createBrowserRouter, RouterProvider, Navigate } from 'react-router-dom'
import AppShell from '@/components/layout/AppShell'
import TasksPage from '@/pages/tasks/TasksPage'
import AccountsPage from '@/pages/accounts/AccountsPage'
import AccountPage from '@/pages/account/AccountPage'

const router = createBrowserRouter([
  {
    path: '/',
    element: <AppShell />,
    children: [
      { index: true, element: <Navigate to="/tasks" replace /> },
      { path: 'tasks', element: <TasksPage /> },
      { path: 'accounts', element: <AccountsPage /> },
      { path: 'accounts/:accountId', element: <AccountPage /> },
    ],
  },
])

export default function App() {
  return <RouterProvider router={router} />
}
