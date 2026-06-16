import { useMemo, useState, type ReactNode } from 'react';
import { CLUBS, ClubContext, type ClubContextValue } from './club-context';

/**
 * Поднимает активный филиал в контекст, чтобы и селектор в сайдбаре, и хлебные
 * крошки в шапке читали одно состояние (а не хардкодили «Тверская»). Будет питаться из API.
 */
export function ClubProvider({ children }: { children: ReactNode }) {
  const [activeId, setActiveId] = useState(CLUBS[0]!.id);

  const value = useMemo<ClubContextValue>(() => {
    const active = CLUBS.find((club) => club.id === activeId) ?? CLUBS[0]!;
    return { clubs: CLUBS, activeId, active, setActiveId };
  }, [activeId]);

  return <ClubContext.Provider value={value}>{children}</ClubContext.Provider>;
}
