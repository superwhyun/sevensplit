import { createContext, useContext } from 'react';

export const AppSettingsContext = createContext(null);

export function useAppSettings() {
    const ctx = useContext(AppSettingsContext);
    if (!ctx) throw new Error('useAppSettings must be used inside AppSettingsProvider');
    return ctx;
}
