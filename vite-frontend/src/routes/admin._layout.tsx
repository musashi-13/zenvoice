import AdminSidebar from '@/components/admin-sidebar'
import { createFileRoute, Outlet } from '@tanstack/react-router'

export const Route = createFileRoute('/admin/_layout')({
  component: RouteComponent,
})

function RouteComponent() {
  return <div className='flex w-full'>
    Hello
    <AdminSidebar/>
    <Outlet />
  </div>
}
