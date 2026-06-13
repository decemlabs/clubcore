/**
 * Доменные типы экрана «Настройки системы» (System-Settings.html).
 * Статичные подписи/опции полей живут в компонентах разделов; здесь — только
 * списочные данные (сессии, интеграции, API-ключи, webhooks).
 */

export interface SysSession {
  id: string;
  device: 'monitor' | 'phone';
  name: string;
  /** Текущая сессия — нельзя завершить, помечена пилюлей. */
  current?: boolean;
  meta: string;
}

export interface SysIntegration {
  id: string;
  /** Короткая подпись логотипа (1С, aC, G, TG). */
  logo: string;
  /** CSS-фон логотипа (бренд-цвет/градиент — per-entity, не токен). */
  logoBg: string;
  /** Цвет текста логотипа (по умолчанию белый). */
  logoFg?: string;
  name: string;
  desc: string;
  /** Подключено → пилюля; иначе → кнопка «Подключить». */
  connected: boolean;
}

export interface ApiKey {
  id: string;
  /** Маскированный ключ (mono). */
  key: string;
  sub: string;
  tone: 'live' | 'test';
}

export interface Webhook {
  id: string;
  url: string;
  sub: string;
  /** active → «Активен», errors → «Ошибки». */
  state: 'active' | 'errors';
}

export interface SystemSettingsData {
  sessions: SysSession[];
  integrations: SysIntegration[];
  apiKeys: ApiKey[];
  webhooks: Webhook[];
}
