import { createContext, useContext } from 'react';

export interface SettingsCtx {
  /** Пометить раздел как изменённый (показывает save-bar). */
  markDirty: (sectionId: string) => void;
}

export const SettingsContext = createContext<SettingsCtx>({ markDirty: () => {} });

export const useSettingsDirty = () => useContext(SettingsContext);
