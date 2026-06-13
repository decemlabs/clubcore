/**
 * Тонкая обёртка над fetch. Пока backend нет — внутри хуков из features/*
 * используем мок-данные; этот модуль готов принять реальный baseURL и заголовки.
 */
const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? '/api';

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...(init?.headers ?? {}),
    },
  });
  if (!res.ok) {
    throw new ApiError(res.status, res.statusText);
  }
  return (await res.json()) as T;
}

/**
 * Хелпер для слоя моков: имитирует асинхронный ответ.
 */
export function mockResponse<T>(value: T, delay = 0): Promise<T> {
  return new Promise((resolve) => setTimeout(() => resolve(value), delay));
}
