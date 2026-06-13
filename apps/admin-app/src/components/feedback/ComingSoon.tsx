import { Clock } from '@/components/icons'
import { ScreenIcon } from '@/pages/login/components/auth-ui'

/**
 * Placeholder for deferred (hide-for-future) routes.
 * FND-04: "not broken, not wired".
 *
 * Screens: Branches, Branch-Settings, System-Settings, ImportExport,
 * Duplicates, Archive, Trash, Messages, Roles, Notifications-management.
 */
export function ComingSoon() {
  return (
    <div className="flex flex-1 flex-col items-center justify-center px-6 text-center animate-in fade-in-0 duration-300">
      <div className="max-w-[400px]">
        <ScreenIcon icon={Clock} tone="accent" />
        <h2 className="text-[20px] font-bold tracking-[-0.4px] text-fg">
          Раздел в разработке
        </h2>
        <p className="mt-2 max-w-[320px] text-[14px] leading-[1.55] text-fg-muted">
          Этот раздел будет доступен в следующем обновлении.{' '}
          Пока продолжайте работать в текущих разделах.
        </p>
      </div>
    </div>
  )
}
