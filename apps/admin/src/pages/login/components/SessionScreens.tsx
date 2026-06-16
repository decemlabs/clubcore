import { Clock, LogOut } from '@/components/icons';
import { ScreenIcon, AuthHeading, PrimaryButton, AuthFooter, Callout } from './auth-ui';

/* ─── Сессия истекла ─── */
export function ExpiredScreen({ onRelogin }: { onRelogin: () => void }) {
  return (
    <div>
      <ScreenIcon icon={Clock} tone="warning" />
      <AuthHeading
        title="Сессия истекла"
        sub="Вы были неактивны более 30 минут. Войдите снова, чтобы продолжить работу."
      />
      <div className="mb-[22px]">
        <Callout>Несохранённые изменения в открытых формах могли быть потеряны.</Callout>
      </div>
      <PrimaryButton onClick={onRelogin}>Войти снова</PrimaryButton>
    </div>
  );
}

/* ─── Вы вышли ─── */
export function LogoutScreen({ onRelogin }: { onRelogin: () => void }) {
  return (
    <div className="text-center">
      <ScreenIcon icon={LogOut} />
      <AuthHeading
        title="Вы вышли из системы"
        sub="Сессия безопасно завершена. До скорой встречи!"
      />
      <PrimaryButton onClick={onRelogin}>Войти снова</PrimaryButton>
      <AuthFooter>Это всё — можно просто закрыть вкладку.</AuthFooter>
    </div>
  );
}
