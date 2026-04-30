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
      clients: 'Клиенты',
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
