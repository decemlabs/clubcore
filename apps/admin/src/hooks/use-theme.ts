import { useCallback, useSyncExternalStore } from 'react';

/**
 * Тема приложения. Общий контракт всех HTML-прототипов:
 * ключ localStorage['admin-theme'] + атрибут [data-theme] на <html>.
 * Тёмные токены в tokens.css переопределяются под [data-theme="dark"],
 * поэтому семантические классы переключаются автоматически — `dark:`-вариант не нужен.
 *
 * Состояние держим в модульном сторе (а не в стейте компонента), чтобы все
 * потребители useTheme() оставались синхронными, без провайдера. Анти-флэш-скрипт
 * в index.html выставляет атрибут до маунта React — здесь мы просто его подхватываем.
 */
export type Theme = 'light' | 'dark';

const STORAGE_KEY = 'admin-theme';

function isTheme(value: unknown): value is Theme {
  return value === 'light' || value === 'dark';
}

function readInitial(): Theme {
  if (typeof document !== 'undefined') {
    const applied = document.documentElement.dataset.theme;
    if (isTheme(applied)) return applied;
  }
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (isTheme(stored)) return stored;
  } catch {
    /* localStorage недоступен — игнорируем */
  }
  if (
    typeof window !== 'undefined' &&
    window.matchMedia?.('(prefers-color-scheme: dark)').matches
  ) {
    return 'dark';
  }
  return 'light';
}

let current: Theme = readInitial();
const listeners = new Set<() => void>();

function apply(theme: Theme): void {
  if (typeof document !== 'undefined') {
    document.documentElement.dataset.theme = theme;
  }
}

function commit(theme: Theme): void {
  if (theme === current) return;
  current = theme;
  apply(theme);
  try {
    localStorage.setItem(STORAGE_KEY, theme);
  } catch {
    /* localStorage недоступен — игнорируем */
  }
  listeners.forEach((listener) => listener());
}

// Синхронизация между вкладками — регистрируем один раз на уровне модуля.
if (typeof window !== 'undefined') {
  window.addEventListener('storage', (event) => {
    if (event.key === STORAGE_KEY && isTheme(event.newValue) && event.newValue !== current) {
      current = event.newValue;
      apply(current);
      listeners.forEach((listener) => listener());
    }
  });
}

function subscribe(callback: () => void): () => void {
  listeners.add(callback);
  return () => listeners.delete(callback);
}

export interface UseThemeResult {
  theme: Theme;
  setTheme: (theme: Theme) => void;
  toggleTheme: () => void;
}

export function useTheme(): UseThemeResult {
  const theme = useSyncExternalStore(
    subscribe,
    () => current,
    () => current,
  );
  const setTheme = useCallback((next: Theme) => commit(next), []);
  const toggleTheme = useCallback(() => commit(current === 'dark' ? 'light' : 'dark'), []);
  return { theme, setTheme, toggleTheme };
}
