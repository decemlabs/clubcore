import { useNavigate } from '@tanstack/react-router'
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/shared/ui/tabs'
import { Route as LoginRoute } from '@/routes/_public/login'
import { EmailLoginForm } from './EmailLoginForm'
import { TelegramLoginTab } from './TelegramLoginTab'

export function LoginPage() {
  const search = LoginRoute.useSearch()
  const navigate = useNavigate()

  const sanitizeNext = (next: string | undefined): string => {
    if (!next) return '/'
    // Open-redirect guard (T-10-17): never accept absolute URLs
    if (next.startsWith('http') || next.startsWith('//')) return '/'
    return next
  }

  const onSuccess = () => {
    void navigate({ to: sanitizeNext(search.next), replace: true })
  }

  return (
    <main className="bg-background flex min-h-screen items-center justify-center p-4">
      <div className="bg-card w-full max-w-sm space-y-6 rounded-lg border p-6 shadow-md">
        <div className="space-y-1 text-center">
          <h1 className="text-3xl font-semibold">SportZal</h1>
          <p className="text-muted-foreground text-xl font-semibold">Войти в систему</p>
        </div>
        <Tabs defaultValue="email">
          <TabsList className="grid w-full grid-cols-2">
            <TabsTrigger value="email">Email / Пароль</TabsTrigger>
            <TabsTrigger value="telegram">Telegram OTP</TabsTrigger>
          </TabsList>
          <TabsContent value="email" className="pt-4">
            <EmailLoginForm onSuccess={onSuccess} />
          </TabsContent>
          <TabsContent value="telegram" className="pt-4">
            <TelegramLoginTab onSuccess={onSuccess} />
          </TabsContent>
        </Tabs>
      </div>
    </main>
  )
}
