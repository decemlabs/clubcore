/**
 * Сид-данные детальной страницы тренера. Портированы дословно из Trainer.html
 * (профиль Ольги Власовой). Пока один подробный профиль — резолвится для любого id
 * (как client-detail); при появлении backend useTrainer(id) получит реальный id.
 */
import type { TrainerDetail } from '@/features/trainers/detail';

export const trainerDetail: TrainerDetail = {
  id: 't-olga',
  initials: 'ОВ',
  avatarGradient: 'linear-gradient(135deg,#8b5cf6,#ec4899)',
  name: 'Ольга Власова',
  statusLabel: 'Активна',
  rating: 4.9,
  branch: 'Тверская',
  memberSince: 'В команде с мар 2023',
  phone: '+7 916 503-77-12',
  specs: ['Йога', 'Стретчинг', 'Пилатес', 'Женские группы'],

  kpis: [
    {
      id: 'clients',
      icon: 'clients',
      label: 'Клиентов',
      value: 28,
      delta: { label: '+3', direction: 'up' },
      footNote: 'за месяц',
    },
    {
      id: 'trainings',
      icon: 'trainings',
      label: 'Тренировок · апрель',
      value: 96,
      footNote: '63 перс · 33 групп',
    },
    {
      id: 'fill',
      icon: 'fill',
      label: 'Заполняемость',
      value: 88,
      unit: '%',
      chips: [{ label: 'выше нормы', tone: 'accent' }],
    },
    {
      id: 'earnings',
      icon: 'earnings',
      label: 'Заработок · апрель',
      value: 142800,
      unit: '₽',
      footNote: 'к выплате 5 мая',
    },
  ],

  scheduleDateLabel: 'сегодня',
  schedule: [
    {
      time: '08:00',
      title: 'Йога · персональная',
      sub: 'Карина Левчук · зал 2',
      bar: 'done',
      tag: 'завершена',
      tagTone: 'done',
    },
    {
      time: '10:30',
      title: 'Стретчинг · группа',
      sub: '8 из 10 · зал 1',
      bar: 'done',
      tag: 'завершена',
      tagTone: 'done',
    },
    {
      time: '12:00',
      title: 'Пилатес · персональная',
      sub: 'Анна Петрова · зал 2',
      bar: 'accent',
      tag: 'идёт',
      tagTone: 'now',
    },
    {
      time: '15:00',
      title: 'Женская группа · йога',
      sub: '12 записано · зал 1',
      bar: 'group',
      tag: 'далее',
      tagTone: 'default',
    },
    {
      time: '18:30',
      title: 'Стретчинг · персональная',
      sub: 'Максим Соколов · зал 2',
      bar: 'accent',
      tag: 'далее',
      tagTone: 'default',
    },
  ],

  regularsCount: 28,
  regulars: [
    {
      initials: 'АП',
      color: 'linear-gradient(135deg,#6366f1,#818cf8)',
      name: 'Анна Петрова',
      sub: '2 раза в неделю',
    },
    {
      initials: 'МС',
      color: 'linear-gradient(135deg,#10b981,#34d399)',
      name: 'Максим Соколов',
      sub: 'персональные',
    },
    {
      initials: 'КЛ',
      color: 'linear-gradient(135deg,#f43f5e,#fb7185)',
      name: 'Карина Левчук',
      sub: '3 раза в неделю',
    },
    {
      initials: '+25',
      color: 'linear-gradient(135deg,#0ea5e9,#38bdf8)',
      name: 'Ещё 25 клиентов',
      muted: true,
    },
  ],

  terms: [
    { k: 'Персональная', v: '1 800 ₽ / занятие' },
    { k: 'Групповая', v: '1 200 ₽ / занятие' },
    { k: 'Комиссия зала', v: '30%' },
    { k: 'Сертификаты', v: 'FPA, Yoga Alliance RYT-200' },
  ],

  payout: {
    title: 'Расчёт за апрель 2026',
    periods: ['Апрель 2026', 'Март 2026', 'Февраль 2026'],
    lines: [
      { label: 'Персональные тренировки', sub: '63 × 1 800 ₽', value: '113 400 ₽' },
      { label: 'Групповые тренировки', sub: '33 × 1 200 ₽', value: '39 600 ₽' },
      { label: 'Бонус за заполняемость', sub: '88% · +5%', value: '7 650 ₽' },
      { label: 'Комиссия зала', sub: '30% от тренировок', value: '−45 900 ₽', minus: true },
      { label: 'Удержан НДФЛ', sub: 'самозанятый · 6%', value: '−8 568 ₽', minus: true },
    ],
    totalLabel: 'К выплате',
    totalValue: '106 182 ₽',
    statusLabel: 'Ожидает выплаты',
    period: '1–30 апреля',
    payoutDate: '5 мая 2026',
    method: 'Карта •• 8842',
    payButtonLabel: 'Выплатить 106 182 ₽',
    paidToast: 'Выплата проведена · 106 182 ₽',
    paidButtonLabel: 'Выплачено 30 апр',
  },

  payoutHistory: [
    { id: 'mar', title: 'Март 2026', sub: 'Выплачено 5 апр · карта •• 8842', amount: '98 420 ₽' },
    {
      id: 'feb',
      title: 'Февраль 2026',
      sub: 'Выплачено 5 мар · карта •• 8842',
      amount: '91 060 ₽',
    },
    { id: 'jan', title: 'Январь 2026', sub: 'Выплачено 5 фев · карта •• 8842', amount: '84 300 ₽' },
  ],

  timeline: [
    {
      day: 'Сегодня · 30 апреля',
      items: [
        {
          id: 'h1',
          kind: 'check',
          tone: 'accent',
          time: '10:30',
          title: [
            { t: 'Провела тренировку ' },
            { t: '«Стретчинг · группа»', b: true },
            { t: ' — 8 из 10' },
          ],
        },
        {
          id: 'h2',
          kind: 'check',
          tone: 'accent',
          time: '08:00',
          title: [{ t: 'Чек-ин · персональная с ' }, { t: 'Кариной Левчук', b: true }],
        },
      ],
    },
    {
      day: 'Вчера · 29 апреля',
      items: [
        {
          id: 'h3',
          kind: 'client',
          tone: 'default',
          time: '17:42',
          title: [{ t: 'Новый клиент закреплён — ' }, { t: 'Максим Соколов', b: true }],
        },
        {
          id: 'h4',
          kind: 'cancel',
          tone: 'warn',
          time: '14:10',
          title: [
            { t: 'Отменила тренировку ' },
            { t: '19:00', b: true },
            { t: ' — болезнь, клиент уведомлён' },
          ],
        },
      ],
    },
    {
      day: '5 апреля',
      items: [
        {
          id: 'h5',
          kind: 'payout',
          tone: 'accent',
          time: '12:00',
          title: [
            { t: 'Выплата за март — ' },
            { t: '98 420 ₽', b: true },
            { t: ' на карту •• 8842' },
          ],
        },
        {
          id: 'h6',
          kind: 'rate',
          tone: 'default',
          time: '09:30',
          title: [{ t: 'Обновлены ставки — персональная ' }, { t: '1 800 ₽', b: true }],
        },
      ],
    },
    {
      day: 'Март 2023',
      items: [
        {
          id: 'h7',
          kind: 'join',
          tone: 'accent',
          time: '03 мар 2023',
          title: [{ t: 'Принята в команду — филиал ' }, { t: 'Тверская', b: true }],
        },
      ],
    },
  ],
};
