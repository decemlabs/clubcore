import { createContext, useContext } from 'react';

export interface Club {
  id: string;
  name: string;
  sub: string;
}

// Локальный список филиалов. При появлении backend заменяется на useClubs().
export const CLUBS: Club[] = [
  { id: 'tver', name: 'Тверская', sub: 'м. Тверская · 247 клиентов' },
  { id: 'sokol', name: 'Сокольники', sub: 'м. Сокольники · 312 клиентов' },
  { id: 'novok', name: 'Новокосино', sub: 'м. Новокосино · 288 клиентов' },
];

export interface ClubContextValue {
  clubs: Club[];
  activeId: string;
  active: Club;
  setActiveId: (id: string) => void;
}

export const ClubContext = createContext<ClubContextValue | null>(null);

/** Активный филиал — общий для селектора в сайдбаре и хлебных крошек в шапке. */
export function useActiveClub(): ClubContextValue {
  const ctx = useContext(ClubContext);
  if (!ctx) throw new Error('useActiveClub must be used within <ClubProvider>');
  return ctx;
}
