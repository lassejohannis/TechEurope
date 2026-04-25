import { createBrowserRouter, RouterProvider, Navigate } from 'react-router-dom'
import AppShell from '@/components/layout/AppShell'
import BrowsePage from '@/pages/browse/BrowsePage'
import SearchPage from '@/pages/search/SearchPage'
import ReviewPage from '@/pages/review/ReviewPage'

const router = createBrowserRouter([
  {
    path: '/',
    element: <AppShell />,
    children: [
      { index: true, element: <Navigate to="/browse" replace /> },
      { path: 'browse', element: <BrowsePage /> },
      { path: 'browse/:entityId', element: <BrowsePage /> },
      { path: 'search', element: <SearchPage /> },
      { path: 'review', element: <ReviewPage /> },
      { path: 'review/:conflictId', element: <ReviewPage /> },
    ],
  },
])

export default function App() {
  return <RouterProvider router={router} />
}
