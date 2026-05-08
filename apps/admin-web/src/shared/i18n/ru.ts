export const ru = {
  shell: {
    appName: 'SportZal',
    roleSwitch: {
      label: 'Роль',
      owner: 'Владелец',
      reception: 'Ресепшн',
    },
    theme: {
      label: 'Тема',
      light: 'Светлая',
      dark: 'Тёмная',
      system: 'Системная',
    },
    nav: {
      home: 'Главная',
      visits: 'Отметки', // NEW Phase 22 D-22-4 (22-03 adds /visits route)
      clients: 'Клиенты',
      memberships: 'Абонементы', // NEW Phase 22 D-22-4
      membershipPlans: 'Тарифы', // NEW Phase 22 D-22-4
      schedule: 'Расписание',
      staff: 'Сотрудники',
      finance: 'Финансы',
      settings: 'Настройки',
    },
    notifications: {
      label: 'Уведомления',
      empty: 'Нет новых уведомлений',
    },
    profile: {
      label: 'Профиль',
      logout: 'Выйти',
      demoMode: 'Демо-режим',
    },
    forbidden: 'Доступ запрещён',
  },
  common: {
    loading: 'Загрузка…',
    empty: 'Пусто',
    error: 'Ошибка',
    retry: 'Повторить',
  },
  auth: {
    login: {
      heading: 'Войти в систему',
      emailTab: 'Email / Пароль',
      telegramTab: 'Telegram OTP',
      emailLabel: 'Email',
      passwordLabel: 'Пароль',
      submit: 'Войти',
      submitting: 'Вход…',
      showPassword: 'Показать пароль',
      hidePassword: 'Скрыть пароль',
    },
    telegram: {
      instruction: 'Нажмите кнопку ниже, откройте ссылку в Telegram и дождитесь кода.',
      getDeepLink: 'Получить ссылку Telegram',
      openBot: 'Открыть бота в Telegram',
      bound: 'Чат привязан. Введите код из Telegram.',
      otpLabel: '6-значный код',
      otpSubmit: 'Подтвердить код',
      polling: 'Ожидание подтверждения…',
      timedOut: 'Срок действия ссылки истёк.',
      refreshLink: 'Получить новую ссылку',
    },
    errors: {
      invalidCredentials: 'Неверный email или пароль.',
      rateLimited: 'Слишком много попыток. Попробуйте через несколько минут.',
      otpInvalid: 'Неверный код. Попробуйте ещё раз.',
      otpExpired: 'Код истёк. Получите новый.',
      otpMaxAttempts: 'Код заблокирован. Начните процесс заново.',
      botNotStarted: 'Вы ещё не написали боту. Перейдите по ссылке.',
      network: 'Ошибка соединения. Проверьте сеть и попробуйте снова.',
    },
    splash: 'Загрузка…',
  },
  clients: {
    heading: 'Клиенты',
    search: { placeholder: 'Поиск по имени или телефону…' },
    actions: {
      create: 'Новый клиент',
      edit: 'Редактировать клиента',
      delete: 'Удалить клиента',
    },
    form: {
      createHeading: 'Добавить клиента',
      editHeading: 'Редактировать клиента',
      saveCreate: 'Добавить клиента',
      saveEdit: 'Сохранить изменения',
      cancel: 'Не сохранять',
      fields: {
        lastName: 'Фамилия',
        firstName: 'Имя',
        middleName: 'Отчество',
        phone: 'Телефон',
        email: 'Email',
        birthDate: 'Дата рождения',
        notes: 'Заметки',
      },
    },
    errors: {
      lastNameRequired: 'Укажите фамилию',
      firstNameRequired: 'Укажите имя',
      phoneRequired: 'Укажите номер телефона',
      phoneFormat: 'Введите телефон в формате +7 (XXX) XXX-XX-XX',
      phoneDuplicate: 'Клиент с таким телефоном уже существует',
      emailFormat: 'Введите корректный email',
    },
    empty: {
      heading: 'Клиентов пока нет',
      body: 'Добавьте первого клиента, нажав «Новый клиент».',
    },
    noResults: {
      heading: 'Ничего не найдено',
      body: 'Попробуйте изменить запрос или очистить фильтры.',
    },
    errorState: {
      heading: 'Не удалось загрузить клиентов',
      body: 'Проверьте соединение или обновите страницу.',
      retry: 'Повторить загрузку',
    },
    delete: {
      heading: 'Удалить клиента?',
      body: 'Клиент {fullName} будет скрыт из списков. Данные сохранятся в базе (мягкое удаление).',
      confirm: 'Удалить',
      cancel: 'Не удалять',
    },
  },
  memberships: {
    heading: 'Абонементы',
    actions: {
      sell: 'Продать абонемент',
      cancel: 'Отменить',
      create: 'Новый тариф',
    },
    status: {
      active: 'Активен',
      expired: 'Истёк',
      cancelled: 'Отменён',
    },
    badge: {
      expirestoday: 'истёк сегодня',
      expiresToday: 'Абонемент истекает сегодня',
    },
    dialog: {
      sellTitle: 'Продать абонемент',
      sellSubmit: 'Продать',
      sellSubmitting: 'Продажа…',
      cancelTitle: 'Отменить абонемент?',
      cancelBody: 'Действие нельзя отменить. Абонемент будет переведён в статус «Отменён».',
      cancelReason: 'Причина отмены (необязательно)',
      cancelConfirm: 'Отменить абонемент',
      cancelAbort: 'Не отменять',
    },
    form: {
      planSelect: 'Выберите тариф',
      paidAt: 'Дата оплаты',
      notes: 'Заметки',
    },
    empty: {
      heading: 'Абонементов пока нет',
      body: 'Продайте первый абонемент клиенту, открыв его профиль.',
    },
    emptyExpiring: {
      heading: 'Нет абонементов, истекающих в ближайшие 7 дней',
    },
    error: {
      heading: 'Не удалось загрузить абонементы',
      body: 'Проверьте соединение или обновите страницу.',
    },
    filter: {
      expiring: 'Истекают через 7 дней',
    },
    toast: {
      sold: 'Абонемент продан',
      cancelled: 'Абонемент отменён',
    },
    errors: {
      planInUse: 'Тариф используется в активных абонементах и не может быть удалён.',
      invalidTransition: 'Невозможно отменить: абонемент уже истёк или отменён.',
      mockNotImplemented: 'Операция недоступна в демо-режиме. Используйте реальный API.',
    },
  },
  membershipPlans: {
    heading: 'Тарифы',
    daysUnit: 'дн.',
    actions: {
      create: 'Новый тариф',
    },
    columns: {
      name: 'Название',
      durationDays: 'Длительность',
      price: 'Цена',
      status: 'Статус',
    },
    dialog: {
      createTitle: 'Новый тариф',
      editTitle: 'Редактировать тариф',
      deleteTitle: 'Удалить тариф?',
      deleteBody: 'Тариф будет скрыт из списка продаж. Действие необратимо.',
      deleteConfirm: 'Удалить',
    },
    form: {
      name: 'Название',
      priceRoubles: 'Цена, ₽',
      durationDays: 'Длительность, дн.',
      active: 'Активный тариф',
      submitting: 'Сохраняется…',
      saveCreate: 'Добавить тариф',
      saveEdit: 'Сохранить изменения',
      cancel: 'Отмена',
      durationImmutable: 'Длительность нельзя изменить после создания',
    },
    toast: {
      created: 'Тариф добавлен',
      updated: 'Тариф сохранён',
      deleted: 'Тариф удалён',
    },
    status: {
      active: 'Активен',
      archived: 'Архивирован',
    },
    error: {
      heading: 'Не удалось загрузить тарифы',
      retry: 'Повторить загрузку',
    },
    empty: {
      heading: 'Тарифов пока нет',
      body: 'Добавьте первый тариф, нажав «Новый тариф».',
    },
  },
  clientProfile: {
    backLink: '← Клиенты',
    membershipsBlock: 'Абонементы',
    visitsBlock: 'Посещения',
  },
} as const

type Dict = typeof ru

type Join<K, P> = K extends string ? (P extends string ? `${K}.${P}` : K) : never

type Paths<T> = T extends object
  ? { [K in keyof T]: K extends string ? K | Join<K, Paths<T[K]>> : never }[keyof T]
  : never

export type TranslationKey = Paths<Dict>

export function t(path: TranslationKey): string {
  const segments = path.split('.')
  let cur: unknown = ru
  for (const seg of segments) {
    if (cur && typeof cur === 'object' && seg in (cur as Record<string, unknown>)) {
      cur = (cur as Record<string, unknown>)[seg]
    } else {
      return path
    }
  }
  return typeof cur === 'string' ? cur : path
}
