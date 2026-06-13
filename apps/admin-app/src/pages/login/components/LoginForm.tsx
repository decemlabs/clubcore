import { useState, type FormEvent } from 'react';
import { toast } from 'sonner';
import { Mail, ArrowRight } from '@/components/icons';
import { Checkbox } from '@/components/ui/Checkbox';
import {
  AuthHeading,
  Field,
  PasswordField,
  PrimaryButton,
  Divider,
  GoogleButton,
  AuthFooter,
  AuthLink,
} from './auth-ui';

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

/**
 * Основной экран входа. Сабмит валидирует поля и (т.к. бэкенда нет) после короткой
 * «загрузки» вызывает onSuccess → переход на дашборд.
 */
export function LoginForm({
  onSuccess,
  onForgot,
}: {
  onSuccess: () => void;
  onForgot: () => void;
}) {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [remember, setRemember] = useState(true);
  const [errors, setErrors] = useState<{ email?: string; password?: string }>({});
  const [loading, setLoading] = useState(false);

  const handleSubmit = (event: FormEvent) => {
    event.preventDefault();
    const next: typeof errors = {};
    if (!EMAIL_RE.test(email)) next.email = 'Введите корректный адрес почты';
    if (!password) next.password = 'Введите пароль';
    setErrors(next);
    if (Object.keys(next).length > 0) return;
    setLoading(true);
    window.setTimeout(onSuccess, 700);
  };

  return (
    <form onSubmit={handleSubmit} noValidate>
      <AuthHeading title="С возвращением" sub="Войдите в админ-панель, чтобы управлять залом." />

      <Field
        label="Эл. почта"
        name="email"
        type="email"
        autoComplete="username"
        leadIcon={Mail}
        placeholder="you@moizal.ru"
        value={email}
        onChange={(e) => setEmail(e.target.value)}
        error={errors.email}
      />

      <PasswordField
        label="Пароль"
        name="password"
        autoComplete="current-password"
        placeholder="Введите пароль"
        value={password}
        onChange={(e) => setPassword(e.target.value)}
        error={errors.password}
        labelAction={<AuthLink onClick={onForgot}>Забыли пароль?</AuthLink>}
      />

      <label className="mb-[22px] mt-1 flex cursor-pointer items-center gap-2.5 text-[13px] text-fg-muted select-none">
        <Checkbox checked={remember} onCheckedChange={setRemember} />
        Запомнить меня
      </label>

      <PrimaryButton type="submit" loading={loading} icon={ArrowRight}>
        Войти
      </PrimaryButton>

      <Divider />

      <GoogleButton onClick={onSuccess} />

      <AuthFooter>
        Нет доступа?{' '}
        <AuthLink onClick={() => toast('Обратитесь к администратору вашего филиала')}>
          Запросить у администратора
        </AuthLink>
      </AuthFooter>
    </form>
  );
}
