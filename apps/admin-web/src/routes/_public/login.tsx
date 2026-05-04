import { createFileRoute } from '@tanstack/react-router'
import { z } from 'zod'

// Stub — Task 3 replaces this with LoginPage + beforeLoad silent-redirect (D-03)
export const Route = createFileRoute('/_public/login')({
  validateSearch: z.object({ next: z.string().optional() }),
  component: LoginStub,
})

function LoginStub() {
  return <div>Loading...</div>
}
