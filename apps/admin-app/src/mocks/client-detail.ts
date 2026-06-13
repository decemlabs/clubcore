/**
 * Сид-данные детальной страницы клиента (Карина Левчук, id «2» из списка).
 * Портировано из Client.html как design-spec. Цвета аватаров — из референса.
 */
import type { ClientDetail } from '@/features/clients/detail';

const TRAINER_COLOR = '#f59e0b';
const YOGA_COLOR = '#a855f7';
const ADMIN_COLOR = '#7c3aed';

export const clientDetail: ClientDetail = {
  id: '2',
  initials: 'КЛ',
  color: TRAINER_COLOR,
  name: 'Карина Левчук',
  status: 'expiring',
  statusLabel: 'Абонемент истекает',
  phone: '+7 925 711-04-22',
  email: 'karina.lev@gmail.com',
  telegram: '@kar_lev',
  birthday: '14 марта 1992 · 34 года',
  memberSinceLabel: 'в клубе с 18 марта 2023',
  tenure: '2 года 1 мес',

  subscription: {
    name: 'Полугодовой',
    amount: '24 600 ₽',
    daysUsed: 177,
    daysTotal: 180,
    fillPct: 98,
    expiresLabel: 'через 3 дня',
    urgent: true,
    features: ['Доступ 24/7', 'Сауна включена', '−10% на тренера', '14 дней заморозки'],
  },

  trainer: {
    initials: 'АС',
    color: TRAINER_COLOR,
    name: 'Аня Соколова',
    spec: 'Силовые, функционал · с марта 2023',
    stats: [
      { value: '96', label: 'тренировок' },
      { value: '211К', label: 'потратила' },
      { value: '★ 5.0', label: 'средняя' },
    ],
  },

  contact: [
    { k: 'Телефон', v: '+7 925 711-04-22' },
    { k: 'E-mail', v: 'karina.lev@gmail.com' },
    { k: 'Telegram', v: '@kar_lev' },
    { k: 'Адрес', v: 'Тверская, 8 · 5 мин пешком' },
    { k: 'Источник', v: 'Instagram · реклама «Лето»' },
    { k: 'Согласие', v: '✓ Рассылка', muted: '· ✓ SMS · ✓ Push' },
  ],

  goals: [
    { label: 'Цель', body: 'Похудеть на 5 кг к лету · прокачать ноги и спину.' },
    {
      label: 'Здоровье',
      body: 'Левое колено иногда побаливает после становой. Без других противопоказаний.',
    },
    {
      label: 'Предпочтения',
      chips: [
        { label: 'Утренние' },
        { label: '2 раза в неделю' },
        { label: 'Мощная музыка' },
        { label: 'Без групповых' },
      ],
    },
  ],

  stats: [
    { label: 'Всего визитов', value: '248', foot: '14 в этом мес · ', footAccent: '+22%' },
    { label: 'Тренировок', value: '96', foot: '95% — с Аней' },
    { label: 'Потрачено всего', value: '211 200 ₽', foot: '+2 200 ₽ за последний мес' },
    { label: 'NPS · отзыв', value: '9', unit: ' / 10', foot: 'опрос 14 апр' },
  ],

  counts: { trainings: 96, payments: 42, chat: 1, notes: 4 },

  activity: {
    moreLabel: 'Показать ещё за апрель · 9 событий',
    groups: [
      {
        day: 'Сегодня · 30 апреля',
        events: [
          {
            id: 'a1',
            time: '11:32',
            kind: 'checkin',
            tone: 'accent',
            title: [{ text: 'Чек-ин в зал ' }, { text: '· QR на ресепшене', muted: true }],
            sub: [
              { text: 'Тренировка идёт сейчас · ' },
              { text: '1ч 24м', bold: true },
              { text: ' · самостоятельно' },
            ],
          },
          {
            id: 'a2',
            time: '11:10',
            kind: 'chat',
            tone: 'default',
            title: 'Сообщение в чате',
            quote: '«Маша, можно перенести тренировку с Аней с четверга на пятницу 18:00?»',
            action: { button: 'Ответить', note: 'не отвечено · 26 мин' },
          },
        ],
      },
      {
        day: 'Вчера · 29 апреля',
        events: [
          {
            id: 'a3',
            time: '19:14',
            kind: 'checkin',
            tone: 'default',
            title: 'Чек-ин в зал',
            sub: [{ text: '1ч 12м', bold: true }, { text: ' · самостоятельно · зал' }],
          },
        ],
      },
      {
        day: '27 апреля · понедельник',
        events: [
          {
            id: 'a4',
            time: '08:42',
            kind: 'training',
            tone: 'warn',
            title: [
              { text: 'Тренировка с ' },
              { text: 'Аней Соколовой', bold: true },
              { text: ' · ноги + спина' },
            ],
            sub: '60 мин · 2 200 ₽ · «Хорошо потянули становую, добавили вес»',
          },
          {
            id: 'a5',
            time: '10:24',
            kind: 'note',
            tone: 'note',
            title: [{ text: 'Заметка администратора ' }, { text: '· Маша Костина', muted: true }],
            quote: '«Просила скидку при продлении. Договорились на −10% если продлит до 5 мая.»',
          },
        ],
      },
      {
        day: '24 апреля · пятница',
        events: [
          {
            id: 'a6',
            time: '20:01',
            kind: 'checkin',
            tone: 'default',
            title: 'Чек-ин в зал',
            sub: [{ text: '48м', bold: true }, { text: ' · самостоятельно' }],
          },
        ],
      },
      {
        day: '22 апреля · среда',
        events: [
          {
            id: 'a7',
            time: '08:30',
            kind: 'training',
            tone: 'warn',
            title: [
              { text: 'Тренировка с ' },
              { text: 'Аней Соколовой', bold: true },
              { text: ' · грудь + руки' },
            ],
            sub: '60 мин · 2 200 ₽ · «Жим лёжа: 3×8 на 60 кг»',
          },
        ],
      },
      {
        day: '20 апреля · понедельник',
        events: [
          {
            id: 'a8',
            time: '19:36',
            kind: 'checkin',
            tone: 'default',
            title: 'Чек-ин в зал',
            sub: [{ text: '1ч 22м', bold: true }, { text: ' · самостоятельно' }],
          },
        ],
      },
    ],
  },

  trainings: {
    title: 'Тренировки · 96 всего',
    sub: '95% — с Аней Соколовой · средняя оценка 4.9 ★',
    moreLabel: 'Показать всё · 91 ещё',
    items: [
      {
        id: 't1',
        day: '27',
        month: 'апр',
        trainerInitials: 'АС',
        trainerColor: TRAINER_COLOR,
        title: 'Ноги + спина',
        tag: 'персональная',
        type: 'personal',
        meta: [{ text: 'Аня Соколова · 60 мин · оценка ' }, { text: '5.0 ★', bold: true }],
        note: '«Хорошо потянули становую, добавили вес 70→75 кг.»',
        amount: '2 200 ₽',
      },
      {
        id: 't2',
        day: '22',
        month: 'апр',
        trainerInitials: 'АС',
        trainerColor: TRAINER_COLOR,
        title: 'Грудь + руки',
        tag: 'персональная',
        type: 'personal',
        meta: [{ text: 'Аня Соколова · 60 мин · оценка ' }, { text: '4.8 ★', bold: true }],
        note: '«Жим лёжа: 3×8 на 60 кг. Следующий раз 62.5.»',
        amount: '2 200 ₽',
      },
      {
        id: 't3',
        day: '15',
        month: 'апр',
        trainerInitials: 'ЛО',
        trainerColor: YOGA_COLOR,
        title: 'Йога — раскрытие бёдер',
        tag: 'первая',
        type: 'group',
        meta: [{ text: 'Лиза Орлова · 75 мин · оценка ' }, { text: '4.5 ★', bold: true }],
        note: '«Пробовали голубя — нужно больше работы. Понравилось.»',
        amount: '2 000 ₽',
      },
      {
        id: 't4',
        day: '8',
        month: 'апр',
        trainerInitials: 'АС',
        trainerColor: TRAINER_COLOR,
        title: 'Функционал',
        tag: 'персональная',
        type: 'personal',
        meta: [{ text: 'Аня Соколова · 60 мин · оценка ' }, { text: '5.0 ★', bold: true }],
        note: '«Круговая, 4 круга. Спина болит — нормально.»',
        amount: '2 200 ₽',
      },
      {
        id: 't5',
        day: '3',
        month: 'апр',
        trainerInitials: 'АС',
        trainerColor: TRAINER_COLOR,
        title: 'Ноги',
        tag: 'персональная',
        type: 'personal',
        meta: [{ text: 'Аня Соколова · 60 мин · оценка ' }, { text: '4.9 ★', bold: true }],
        note: '«Приседания со штангой: 4×6 на 55 кг.»',
        amount: '2 200 ₽',
      },
    ],
  },

  payments: {
    summary: [
      { label: 'Всего', value: '211 200 ₽', foot: 'за 2 года 1 мес' },
      { label: 'Средний чек', value: '5 030 ₽', foot: '42 операции' },
      { label: 'Сейчас на счёте', value: '0 ₽', foot: 'долгов нет' },
      { label: 'Карта', value: '•••• 4821', foot: 'Mir · Сбер' },
    ],
    title: 'История платежей',
    sub: 'Последние 6 операций · 42 всего',
    moreLabel: 'Показать всё · 36 ещё',
    items: [
      {
        id: 'p1',
        icon: 'card',
        title: 'Полугодовой абонемент',
        meta: '5 ноя 2024 · 14:18 · •••• 4821 · чек № 28104',
        amount: '24 600 ₽',
      },
      {
        id: 'p2',
        icon: 'trainer',
        title: 'Персональная тренировка · Аня Соколова',
        meta: '27 апр · 08:30 · •••• 4821 · чек № 41208',
        amount: '2 200 ₽',
      },
      {
        id: 'p3',
        icon: 'trainer',
        title: 'Персональная тренировка · Аня Соколова',
        meta: '22 апр · 08:30 · •••• 4821 · чек № 41112',
        amount: '2 200 ₽',
      },
      {
        id: 'p4',
        icon: 'shop',
        title: 'Шейкер 700 мл',
        meta: '20 апр · 18:55 · ресепшен · чек № 40988',
        amount: '690 ₽',
      },
      {
        id: 'p5',
        icon: 'trainer',
        title: 'Йога · Лиза Орлова',
        meta: '15 апр · 19:00 · •••• 4821 · чек № 40612',
        amount: '2 000 ₽',
      },
      {
        id: 'p6',
        icon: 'refund',
        title: 'Возврат · не пришла на тренировку',
        meta: '10 апр · 18:00 · •••• 4821 · возврат 50%',
        amount: '−1 100 ₽',
        refund: true,
      },
    ],
  },

  chat: {
    lastActivity: 'Последняя активность 26 мин назад · отвечает Маша Костина',
    composePlaceholder: 'Напишите ответ Карине…',
    entries: [
      { kind: 'day', id: 'd1', label: 'Понедельник, 28 апреля' },
      {
        kind: 'msg',
        id: 'm1',
        side: 'them',
        text: 'Привет! Заметили, что у тебя скоро заканчивается абонемент. Хочешь, оформим продление со скидкой?',
        time: '10:18',
      },
      { kind: 'msg', id: 'm2', side: 'me', text: 'Привет. А какая скидка сейчас?', time: '10:21' },
      {
        kind: 'msg',
        id: 'm3',
        side: 'them',
        text: 'До 5 мая годовой со скидкой 15% + бонусный месяц.',
        time: '10:22',
      },
      {
        kind: 'msg',
        id: 'm4',
        side: 'system',
        text: 'Абонемент продлён на 30 дней до 28 мая',
      },
      { kind: 'day', id: 'd2', label: 'Сегодня' },
      {
        kind: 'msg',
        id: 'm5',
        side: 'them',
        text: 'Маша, можно перенести тренировку с Аней с четверга на пятницу 18:00?',
        time: '11:10 · непрочитано',
        unread: true,
      },
    ],
  },

  notes: {
    composePlaceholder: 'Что важно знать про Карину?',
    items: [
      {
        id: 'n1',
        authorInitials: 'МК',
        authorColor: ADMIN_COLOR,
        author: 'Маша Костина',
        date: '27 апреля · 10:24',
        body: [
          { text: 'Просила скидку при продлении. Договорились на ' },
          { text: '−10%', bold: true },
          { text: ' если продлит до 5 мая. Подтвердить с менеджером.' },
        ],
        tags: [{ label: '⚠ Действие', warn: true }, { label: 'продление' }],
      },
      {
        id: 'n2',
        authorInitials: 'МК',
        authorColor: ADMIN_COLOR,
        author: 'Маша Костина',
        date: '15 апреля',
        body: 'Попробовала йогу с Лизой — понравилось. Подумывает добавить йогу в регулярные тренировки.',
      },
      {
        id: 'n3',
        authorInitials: 'АС',
        authorColor: TRAINER_COLOR,
        author: 'Аня Соколова',
        authorTag: 'тренер',
        date: '2 апреля',
        body: 'Левое колено иногда даёт о себе знать после становой. Снизили вес на одну сессию, через неделю вернулись на план.',
        tags: [{ label: 'здоровье' }, { label: 'тренер' }],
      },
      {
        id: 'n4',
        authorInitials: 'МК',
        authorColor: ADMIN_COLOR,
        author: 'Маша Костина',
        date: '18 марта 2023 · первый день',
        body: 'Пришла по рекламе из Instagram. Хочет похудеть и подкачаться. Рекомендовали Аню — силовые + функционал.',
        tags: [{ label: 'первый день' }],
      },
    ],
  },
};
