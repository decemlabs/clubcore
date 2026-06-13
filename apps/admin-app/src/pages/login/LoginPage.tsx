import { useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { toast } from 'sonner'
import { ROUTES } from '@/app/routes'
import { ThemeToggle } from '@/components/ui/ThemeToggle'
import { BrandPanel } from './components/BrandPanel'
import { LoginForm } from './components/LoginForm'
import { ForgotScreen, SentScreen, ResetScreen } from './components/RecoveryScreens'
// NOTE: The two-factor auth screen import has been removed (hidden-for-future, UI-SPEC Surface 3).
// The TwoFactor file remains in the tree un-imported for future graduation.
import { ExpiredScreen, LogoutScreen } from './components/SessionScreens'

// twofa removed from AuthView — the view is hidden-for-future (no backend staff TOTP).
type AuthView = 'login' | 'forgot' | 'forgot-sent' | 'reset' | 'expired' | 'logout'

// twofa removed from DEEP_LINKABLE — deep-linking to it falls through to 'login'.
// 'reset' added: the backend email link is /login?state=reset&token=<value> (T-100-11).
const DEEP_LINKABLE: AuthView[] = ['expired', 'logout', 'reset']

function initialView(param: string | null): AuthView {
  return DEEP_LINKABLE.includes(param as AuthView) ? (param as AuthView) : 'login';
}

/**
 * Полноэкранный логин (chrome-less, вне AppLayout). Двухколоночный сплит: брендовая
 * панель + панель формы с переключателем темы. Семь состояний переключаются локальной
 * стейт-машиной (восстановление пароля — по ссылкам; twofa/expired/logout — через ?state=).
 * Страница внутри RouterProvider → useNavigate работает; вход → переход на дашборд.
 */
export function LoginPage() {
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const [view, setView] = useState<AuthView>(() => initialView(params.get('state')));
  const [email, setEmail] = useState('');

  const goDashboard = () => navigate(ROUTES.dashboard);
  const goLogin = () => setView('login');

  const renderScreen = () => {
    switch (view) {
      case 'forgot':
        return (
          <ForgotScreen
            onBack={goLogin}
            onSent={(value) => {
              setEmail(value);
              setView('forgot-sent');
            }}
          />
        );
      case 'forgot-sent':
        return (
          <SentScreen
            email={email}
            onOpenReset={() => setView('reset')}
            onResend={() => undefined}
            onBack={goLogin}
          />
        );
      case 'reset':
        return (
          <ResetScreen
            onDone={() => {
              toast.success('Пароль обновлён');
              goLogin();
            }}
          />
        );
      // twofa case removed — the view is hidden-for-future (no staff TOTP backend).
      // Deep-link with ?state=twofa falls through to default 'login' screen.
      case 'expired':
        return <ExpiredScreen onRelogin={goLogin} />;
      case 'logout':
        return <LogoutScreen onRelogin={goLogin} />;
      case 'login':
      default:
        return <LoginForm onSuccess={goDashboard} onForgot={() => setView('forgot')} />;
    }
  };

  return (
    <div className="min-h-dvh bg-bg text-fg min-[860px]:grid min-[860px]:grid-cols-[1.05fr_1fr]">
      <BrandPanel />

      <main className="relative flex min-h-dvh items-center justify-center px-6 py-12 min-[860px]:min-h-0">
        <ThemeToggle className="absolute right-5 top-5" />

        <div className="w-full max-w-[380px]">
          {/* Компактный логотип вместо брендовой панели на мобиле */}
          <div className="mb-[30px] flex items-center gap-2.5 min-[860px]:hidden">
            <span className="grid size-[30px] place-items-center rounded-[9px] bg-fg text-[15px] font-extrabold text-primary dark:bg-primary dark:text-primary-foreground">
              М
            </span>
            <span className="text-[15px] font-bold tracking-[-0.3px]">Мой&nbsp;зал</span>
          </div>

          <div key={view} className="animate-in fade-in-0 slide-in-from-bottom-2 duration-300">
            {renderScreen()}
          </div>
        </div>
      </main>
    </div>
  );
}
