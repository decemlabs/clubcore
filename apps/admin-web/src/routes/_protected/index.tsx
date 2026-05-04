import { createFileRoute } from '@tanstack/react-router'
import { z } from 'zod'
import { t } from '@/shared/i18n'

const searchSchema = z.object({
  forbidden: z.string().optional(),
})

export const Route = createFileRoute('/_protected/')({
  validateSearch: searchSchema,
  component: IndexPage,
})

function IndexPage() {
  const search = Route.useSearch()
  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold">{t('shell.nav.home')}</h1>
      {search.forbidden && (
        <div
          role="alert"
          className="border-destructive/50 bg-destructive/10 text-destructive rounded-md border p-3 text-sm"
        >
          {t('shell.forbidden')}: <code className="font-mono">{search.forbidden}</code>
        </div>
      )}
      <p className="text-muted-foreground text-sm">SportZal admin shell — Phase 1.</p>
    </div>
  )
}
