import { useMemo, useState } from 'react';
import { toast } from 'sonner';
import { useSystemSettings } from '@/features/system-settings/api';
import { PageLoading, PageError } from '@/components/feedback/PageState';
import { PageHeader } from '@/components/layout/PageHeader';
import { SettingsContext } from '@/components/settings/context';
import { ScrollspyNav, type ScrollspyNavGroup } from '@/components/settings/ScrollspyNav';
import { SaveBar } from '@/components/settings/SaveBar';
import {
  SectionCard,
  SelectField,
  TextField,
  ToggleRow,
  GhostBtn,
  FieldGrid,
  LabeledField,
} from '@/components/settings/controls';
import {
  Shield,
  Monitor,
  Code,
  Lock,
  Link2,
  MessageSquare,
  Mail,
  CreditCard,
  Plus,
} from '@/components/icons';
import { TagPill, StatPill, InfoRow, SessionRow, IntegrationRow, MonoRow } from './components/rows';

const NAV: ScrollspyNavGroup[] = [
  {
    title: 'Доступ',
    links: [
      { id: 'security', label: 'Безопасность', icon: 'shield' },
      { id: 'sessions', label: 'Сессии', icon: 'monitor' },
    ],
  },
  {
    title: 'Интеграции',
    links: [
      { id: 'integrations', label: 'Интеграции', icon: 'code' },
      { id: 'api', label: 'API-ключи', icon: 'lock' },
      { id: 'webhooks', label: 'Webhooks', icon: 'link' },
    ],
  },
  {
    title: 'Каналы',
    links: [
      { id: 'sms', label: 'SMS', icon: 'message' },
      { id: 'email', label: 'Email', icon: 'mail' },
      { id: 'acq', label: 'Эквайринг', icon: 'card' },
    ],
  },
];

export function SystemSettingsPage() {
  const { data, isPending, isError, refetch } = useSystemSettings();
  const [dirty, setDirty] = useState<Set<string>>(() => new Set());

  const ctx = useMemo(
    () => ({
      markDirty: (id: string) => setDirty((prev) => (prev.has(id) ? prev : new Set(prev).add(id))),
    }),
    [],
  );

  if (isPending) return <PageLoading />;
  if (isError || !data) return <PageError onRetry={() => void refetch()} />;

  return (
    <SettingsContext.Provider value={ctx}>
      <div className="mx-auto flex w-full max-w-[1440px] flex-col gap-5 px-4 pb-10 pt-5 sm:px-6 sm:pb-12 sm:pt-6 lg:px-7">
        <PageHeader
          title="Настройки системы"
          subtitle="Безопасность, интеграции и каналы связи на уровне аккаунта."
        />

        <div className="grid items-start gap-7 lg:grid-cols-[224px_minmax(0,1fr)]">
          <ScrollspyNav groups={NAV} />

          <div className="flex min-w-0 flex-col gap-[18px]">
            {/* Безопасность */}
            <SectionCard
              id="security"
              icon={Shield}
              title="Безопасность"
              desc="Политика паролей и двухфакторной защиты"
            >
              <ToggleRow
                first
                sectionId="security"
                defaultChecked
                title="Обязательная 2FA"
                sub="Требовать второй фактор для всех сотрудников"
              />
              <ToggleRow
                sectionId="security"
                defaultChecked
                title="Сложные пароли"
                sub="Минимум 8 символов, буквы, цифры, символ"
              />
              <FieldGrid className="mt-4">
                <LabeledField label="Срок действия пароля">
                  <SelectField
                    sectionId="security"
                    options={['90 дней', '180 дней', 'Не истекает']}
                  />
                </LabeledField>
                <LabeledField label="Авто-выход после простоя">
                  <SelectField sectionId="security" options={['30 минут', '1 час', '4 часа']} />
                </LabeledField>
              </FieldGrid>
            </SectionCard>

            {/* Активные сессии */}
            <SectionCard
              id="sessions"
              icon={Monitor}
              title="Активные сессии"
              desc="Устройства с доступом к аккаунту"
            >
              {data.sessions.map((s) => (
                <SessionRow
                  key={s.id}
                  session={s}
                  action={
                    s.current ? undefined : (
                      <GhostBtn onClick={() => toast('Сессия завершена')}>Завершить</GhostBtn>
                    )
                  }
                />
              ))}
              <GhostBtn
                danger
                className="mt-3"
                onClick={() => toast('Все сессии, кроме текущей, завершены')}
              >
                Завершить все остальные
              </GhostBtn>
            </SectionCard>

            {/* Интеграции */}
            <SectionCard
              id="integrations"
              icon={Code}
              title="Интеграции"
              desc="Подключённые сервисы"
            >
              {data.integrations.map((it) => (
                <IntegrationRow
                  key={it.id}
                  item={it}
                  action={
                    it.connected ? (
                      <TagPill tone="on">Подключено</TagPill>
                    ) : (
                      <GhostBtn onClick={() => toast(`Подключение «${it.name}»`)}>
                        Подключить
                      </GhostBtn>
                    )
                  }
                />
              ))}
            </SectionCard>

            {/* API-ключи */}
            <SectionCard
              id="api"
              icon={Lock}
              title="API-ключи"
              desc="Для интеграций и внешних приложений"
            >
              {data.apiKeys.map((k) => (
                <MonoRow
                  key={k.id}
                  mono={k.key}
                  sub={k.sub}
                  pill={
                    k.tone === 'live' ? (
                      <TagPill tone="on">Активен</TagPill>
                    ) : (
                      <TagPill tone="warn">Тест</TagPill>
                    )
                  }
                  actions={
                    k.tone === 'live' ? (
                      <GhostBtn onClick={() => toast.success('Ключ скопирован')}>
                        Копировать
                      </GhostBtn>
                    ) : (
                      <GhostBtn danger onClick={() => toast('Ключ отозван')}>
                        Отозвать
                      </GhostBtn>
                    )
                  }
                />
              ))}
              <GhostBtn className="mt-3" onClick={() => toast.success('Создан новый API-ключ')}>
                <Plus className="size-3.5" strokeWidth={2.4} />
                Создать ключ
              </GhostBtn>
            </SectionCard>

            {/* Webhooks */}
            <SectionCard
              id="webhooks"
              icon={Link2}
              title="Webhooks"
              desc="HTTP-уведомления о событиях"
            >
              {data.webhooks.map((w) => (
                <MonoRow
                  key={w.id}
                  mono={w.url}
                  sub={w.sub}
                  pill={
                    w.state === 'active' ? (
                      <TagPill tone="on">Активен</TagPill>
                    ) : (
                      <TagPill tone="warn">Ошибки</TagPill>
                    )
                  }
                />
              ))}
              <GhostBtn className="mt-3" onClick={() => toast('Добавление webhook')}>
                <Plus className="size-3.5" strokeWidth={2.4} />
                Добавить endpoint
              </GhostBtn>
            </SectionCard>

            {/* SMS */}
            <SectionCard
              id="sms"
              icon={MessageSquare}
              title="SMS"
              desc="Провайдер рассылок и подпись"
            >
              <FieldGrid>
                <LabeledField label="Провайдер">
                  <SelectField sectionId="sms" options={['SMS.ru', 'SMSC', 'Twilio']} />
                </LabeledField>
                <LabeledField label="Имя отправителя">
                  <TextField sectionId="sms" defaultValue="MoiZal" />
                </LabeledField>
              </FieldGrid>
              <div className="mt-2">
                <InfoRow
                  title="Баланс"
                  sub="≈ 4 200 SMS осталось"
                  aside={<StatPill>12 600 ₽</StatPill>}
                />
              </div>
              <GhostBtn className="mt-3" onClick={() => toast.success('Тестовое SMS отправлено')}>
                Отправить тест
              </GhostBtn>
            </SectionCard>

            {/* Email */}
            <SectionCard id="email" icon={Mail} title="Email" desc="Отправка писем и SMTP">
              <FieldGrid>
                <LabeledField label="Способ">
                  <SelectField
                    sectionId="email"
                    options={['Встроенный SMTP', 'Собственный SMTP', 'SendGrid']}
                  />
                </LabeledField>
                <LabeledField label="Адрес отправителя">
                  <TextField sectionId="email" defaultValue="hello@moizal.ru" />
                </LabeledField>
              </FieldGrid>
              <div className="mt-2">
                <InfoRow
                  title="Домен подтверждён"
                  sub="SPF и DKIM настроены"
                  aside={<TagPill tone="on">Verified</TagPill>}
                />
              </div>
              <GhostBtn
                className="mt-3"
                onClick={() => toast.success('Тестовое письмо отправлено')}
              >
                Отправить тест
              </GhostBtn>
            </SectionCard>

            {/* Эквайринг */}
            <SectionCard
              id="acq"
              icon={CreditCard}
              title="Эквайринг"
              desc="Приём платежей картами и СБП"
            >
              <FieldGrid>
                <LabeledField label="Провайдер">
                  <SelectField
                    sectionId="acq"
                    options={['Тинькофф Касса', 'ЮKassa', 'СберБизнес']}
                  />
                </LabeledField>
                <LabeledField label="Terminal ID">
                  <TextField sectionId="acq" defaultValue="1700123456" />
                </LabeledField>
              </FieldGrid>
              <div className="mt-1">
                <ToggleRow
                  first
                  sectionId="acq"
                  defaultChecked
                  title="Система быстрых платежей (СБП)"
                  sub="Оплата по QR · комиссия 0.4%"
                />
                <ToggleRow
                  sectionId="acq"
                  defaultChecked
                  title="Сохранение карт"
                  sub="Рекуррентные платежи для автопродления"
                />
                <InfoRow
                  title="Статус подключения"
                  sub="Последняя транзакция 4 мин назад"
                  aside={<TagPill tone="on">Активно</TagPill>}
                />
              </div>
            </SectionCard>
          </div>
        </div>

        <SaveBar
          count={dirty.size}
          onSave={() => setDirty(new Set())}
          onCancel={() => setDirty(new Set())}
        />
      </div>
    </SettingsContext.Provider>
  );
}
