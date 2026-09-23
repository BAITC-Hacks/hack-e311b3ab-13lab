import { createBrowserRouter } from 'react-router'
import { RequireAuth, RequirePermission } from './auth/guards'
import { Layout } from './components/Layout'
import { AuditPage } from './pages/AuditPage'
import { LoginPage } from './pages/LoginPage'
import { MeetingPage } from './pages/meeting/MeetingPage'
import { MeetingsPage } from './pages/MeetingsPage'
import { NewMeetingPage } from './pages/NewMeetingPage'
import { NotFoundPage } from './pages/NotFoundPage'
import { TasksPage } from './pages/TasksPage'
import { UsersPage } from './pages/UsersPage'

export const router = createBrowserRouter([
  { path: '/login', element: <LoginPage /> },
  {
    path: '/',
    element: (
      <RequireAuth>
        <Layout />
      </RequireAuth>
    ),
    children: [
      { index: true, element: <MeetingsPage /> },
      {
        path: 'meetings/new',
        element: (
          <RequirePermission permission="meetings:create">
            <NewMeetingPage />
          </RequirePermission>
        ),
      },
      { path: 'meetings/:id', element: <MeetingPage /> },
      { path: 'tasks', element: <TasksPage /> },
      {
        path: 'users',
        element: (
          <RequirePermission permission="users:manage">
            <UsersPage />
          </RequirePermission>
        ),
      },
      {
        path: 'audit',
        element: (
          <RequirePermission permission="audit:read">
            <AuditPage />
          </RequirePermission>
        ),
      },
      { path: '*', element: <NotFoundPage /> },
    ],
  },
])
