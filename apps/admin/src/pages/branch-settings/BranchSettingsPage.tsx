import { useMemo, useState } from 'react';
import { useParams } from 'react-router-dom';
import { toast } from 'sonner';
import { useBranch } from '@/features/branches/api';
import { PageLoading, PageError } from '@/components/feedback/PageState';
import { EmptyState } from '@/components/feedback/EmptyState';
import { Building2 } from '@/components/icons';
import { SettingsContext } from '@/components/settings/context';
import { ScrollspyNav, type ScrollspyNavGroup } from '@/components/settings/ScrollspyNav';
import { SaveBar } from '@/components/settings/SaveBar';
import {
  SectionCard,
  SelectField,
  TextField,
  MoneyField,
  ToggleRow,
  GhostBtn,
  FieldGrid,
  LabeledField,
} from '@/components/settings/controls';
import { Clock, LayoutGrid, CreditCard, Bell, TriangleAlert, Plus } from '@/components/icons';
import { BranchSettingsHead, HoursEditor, ZoneRow, DangerRow } from './components/parts';

const NAV: ScrollspyNavGroup[] = [
  {
    title: '',
    links: [
      { id: 'general', label: 'Общее', icon: 'building' },
      { id: 'hours', label: 'Часы работы', icon: 'clock' },
      { id: 'zones', label: 'Залы и зоны', icon: 'zones' },
      { id: 'payments', label: 'Оплата', icon: 'card' },
      { id: 'notify', label: 'Уведомления', icon: 'bell' },
      { id: 'danger', label: 'Опасная зона', icon: 'danger', danger: true },
    ],
  },
];

/** Текущее значение первым — нативный select показывает первый option выбранным. */
function withCurrentFirst(current: string, pool: string[]): string[] {
  return [current, ...pool.filter((v) => v !== current)];
}

export function BranchSettingsPage() {
  const { branchId = '' } = useParams();
  const { data: branch, isPending, isError, refetch } = useBranch(branchId);
  const [dirty, setDirty] = useState<Set<string>>(() => new Set());

  const ctx = useMemo(
    () => ({
      markDirty: (id: string) => setDirty((prev) => (prev.has(id) ? prev : new Set(prev).add(id))),
    }),
    [],
  );

  if (isPending) return <PageLoading />;
  if (isError) return <PageError onRetry={() => void refetch()} />;
  if (!branch) {
    return (
      <div className="mx-auto w-full max-w-[1440px] px-4 pt-10 sm:px-6">
        <EmptyState
          icon={Building2}
          title="Филиал не найден"
          message="Возможно, он был удалён или ссылка устарела."
        />
      </div>
    );
  }

  const managerName = branch.manager?.name ?? 'Не назначен';

  return (
    <SettingsContext.Provider value={ctx}>
      <div className="mx-auto flex w-full max-w-[1440px] flex-col gap-5 px-4 pb-10 pt-5 sm:px-6 sm:pb-12 sm:pt-6 lg:px-7">
        <BranchSettingsHead branch={branch} />

        <div className="grid items-start gap-7 lg:grid-cols-[224px_minmax(0,1fr)]">
          <ScrollspyNav groups={NAV} />

          <div className="flex min-w-0 flex-col gap-[18px]">
            {/* Общее */}
            <SectionCard
              id="general"
              icon={Building2}
              title="Общее"
              desc="Название, адрес и контакты филиала"
            >
              <div className="space-y-3.5 pt-2">
                <LabeledField label="Название филиала">
                  <TextField sectionId="general" defaultValue={branch.name} />
                </LabeledField>
                <FieldGrid>
                  <LabeledField label="Город">
                    <TextField sectionId="general" defaultValue={branch.city} />
                  </LabeledField>
                  <LabeledField label="Метро">
                    <TextField sectionId="general" defaultValue={branch.metro} />
                  </LabeledField>
                </FieldGrid>
                <LabeledField label="Адрес">
                  <TextField sectionId="general" defaultValue={branch.addr} />
                </LabeledField>
                <FieldGrid>
                  <LabeledField label="Телефон">
                    <TextField sectionId="general" defaultValue={branch.phone} />
                  </LabeledField>
                  <LabeledField label="Часовой пояс">
                    <SelectField
                      sectionId="general"
                      options={withCurrentFirst(branch.timezone, ['МСК (UTC+3)', 'UTC+4', 'UTC+5'])}
                    />
                  </LabeledField>
                </FieldGrid>
                <LabeledField label="Управляющий">
                  <SelectField
                    sectionId="general"
                    options={withCurrentFirst(managerName, [
                      'Ольга Воронина',
                      'Роман Ким',
                      'Сергей Белов',
                      'Не назначен',
                    ])}
                  />
                </LabeledField>
              </div>
            </SectionCard>

            {/* Часы работы */}
            <SectionCard
              id="hours"
              icon={Clock}
              title="Часы работы"
              desc="Когда зал открыт для посещений"
            >
              <HoursEditor hours={branch.hours} sectionId="hours" />
            </SectionCard>

            {/* Залы и зоны */}
            <SectionCard
              id="zones"
              icon={LayoutGrid}
              title="Залы и зоны"
              desc="Помещения и их вместимость для расписания"
            >
              {branch.zones.map((z) => (
                <ZoneRow key={z.id} zone={z} />
              ))}
              <GhostBtn className="mt-3" onClick={() => toast('Добавление зоны')}>
                <Plus className="size-3.5" strokeWidth={2.4} />
                Добавить зону
              </GhostBtn>
            </SectionCard>

            {/* Оплата */}
            <SectionCard
              id="payments"
              icon={CreditCard}
              title="Оплата"
              desc="Комиссия зала и способы оплаты"
            >
              <FieldGrid>
                <LabeledField label="Комиссия зала с тренеров">
                  <MoneyField
                    sectionId="payments"
                    defaultValue={branch.payments.trainerCommissionPct}
                    suffix="%"
                  />
                </LabeledField>
                <LabeledField label="Эквайринг">
                  <SelectField
                    sectionId="payments"
                    options={withCurrentFirst(branch.payments.acquiring, [
                      'Тинькофф Касса',
                      'ЮKassa',
                      'СБП',
                    ])}
                  />
                </LabeledField>
              </FieldGrid>
              <div className="mt-1">
                <ToggleRow
                  first
                  sectionId="payments"
                  defaultChecked={branch.payments.acceptCash}
                  title="Приём наличных"
                  sub="Разрешить оплату на ресепшене"
                />
                <ToggleRow
                  sectionId="payments"
                  defaultChecked={branch.payments.payByLink}
                  title="Онлайн-оплата по ссылке"
                  sub="Отправлять клиенту ссылку на оплату"
                />
                <ToggleRow
                  sectionId="payments"
                  defaultChecked={branch.payments.installments}
                  title="Рассрочка"
                  sub="Сплит-оплата абонементов"
                />
              </div>
            </SectionCard>

            {/* Уведомления */}
            <SectionCard
              id="notify"
              icon={Bell}
              title="Уведомления"
              desc="Что приходит клиентам этого филиала"
            >
              <ToggleRow
                first
                sectionId="notify"
                defaultChecked={branch.notifications.workoutReminder}
                title="Напоминание о тренировке"
                sub="За 2 часа до начала · SMS + push"
              />
              <ToggleRow
                sectionId="notify"
                defaultChecked={branch.notifications.membershipExpiry}
                title="Истечение абонемента"
                sub="За 7 дней до окончания"
              />
              <ToggleRow
                sectionId="notify"
                defaultChecked={branch.notifications.promos}
                title="Акции и новости филиала"
                sub="Маркетинговая рассылка"
              />
            </SectionCard>

            {/* Опасная зона */}
            <SectionCard
              id="danger"
              icon={TriangleAlert}
              title="Опасная зона"
              desc="Необратимые действия с филиалом"
              danger
            >
              <DangerRow
                first
                title="Поставить на паузу"
                desc="Скрыть из переключателя и остановить запись. Активные абонементы продолжат действовать."
                action={
                  <GhostBtn onClick={() => toast('Филиал поставлен на паузу')}>На паузу</GhostBtn>
                }
              />
              <DangerRow
                title="Перенести клиентов и закрыть"
                desc={`Перевести ${branch.clients} клиентов и ${branch.trainers} тренеров в другой филиал, затем закрыть зал.`}
                action={
                  <GhostBtn danger onClick={() => toast('Мастер переноса клиентов')}>
                    Перенести и закрыть
                  </GhostBtn>
                }
              />
              <DangerRow
                title="Удалить филиал"
                desc="Безвозвратно удалить филиал и все его данные. Доступно только когда нет активных клиентов."
                action={<GhostBtn disabled>Удалить</GhostBtn>}
              />
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
