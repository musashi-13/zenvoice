import { createFileRoute } from '@tanstack/react-router'

export const Route = createFileRoute('/warehouse/login')({
  component: RouteComponent,
})

function RouteComponent() {
  return <div>Hello "/warehouse/login"!</div>
}
