/** Сид-данные экрана «Настройки системы» (System-Settings.html). */
import type { SystemSettingsData } from '@/features/system-settings/types';

export const systemSettingsData: SystemSettingsData = {
  sessions: [
    {
      id: 's1',
      device: 'monitor',
      name: 'Chrome · macOS',
      current: true,
      meta: 'Москва · 31.184.220.14 · сейчас',
    },
    {
      id: 's2',
      device: 'phone',
      name: 'Safari · iPhone',
      meta: 'Москва · последняя активность 2 ч назад',
    },
    { id: 's3', device: 'monitor', name: 'Chrome · Windows', meta: 'Сокольники · вчера, 21:30' },
  ],
  integrations: [
    {
      id: 'i1',
      logo: '1С',
      logoBg: '#fbbf24',
      logoFg: '#1c1917',
      name: '1С:Бухгалтерия',
      desc: 'Синхронизация платежей · обновлено 10 мин назад',
      connected: true,
    },
    {
      id: 'i2',
      logo: 'aC',
      logoBg: 'linear-gradient(135deg,#0ea5e9,#38bdf8)',
      name: 'amoCRM',
      desc: 'Лиды и сделки',
      connected: true,
    },
    {
      id: 'i3',
      logo: 'G',
      logoBg: '#4285f4',
      name: 'Google Calendar',
      desc: 'Двусторонняя синхронизация расписания',
      connected: false,
    },
    {
      id: 'i4',
      logo: 'TG',
      logoBg: '#229ED9',
      name: 'Telegram-бот',
      desc: 'Уведомления и запись через бота',
      connected: false,
    },
  ],
  apiKeys: [
    {
      id: 'k1',
      key: 'sk_live_••••••••3a9f',
      sub: 'Основной · создан 12 фев 2026 · использован сегодня',
      tone: 'live',
    },
    {
      id: 'k2',
      key: 'sk_test_••••••••71c2',
      sub: 'Тестовый · создан 03 янв 2026 · не используется 40 дней',
      tone: 'test',
    },
  ],
  webhooks: [
    {
      id: 'w1',
      url: 'https://crm.moizal.ru/hook/payments',
      sub: 'payment.success, payment.refund · 2 380 доставок',
      state: 'active',
    },
    {
      id: 'w2',
      url: 'https://hooks.zapier.com/••/client',
      sub: 'client.created · последняя ошибка 503',
      state: 'errors',
    },
  ],
};
