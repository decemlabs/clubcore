import { Loader2 } from 'lucide-react'

export function Splash() {
  return (
    <div className="bg-background fixed inset-0 flex flex-col items-center justify-center gap-12">
      <p className="text-3xl font-semibold">SportZal</p>
      <Loader2 className="text-muted-foreground size-6 animate-spin" aria-label="Загрузка..." />
    </div>
  )
}
