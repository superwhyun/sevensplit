import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { settingsApi } from '../lib/api';
import { AppSettingsContext } from './appSettingsStore';

export function AppSettingsProvider({ children }) {
    const [settings, setSettings] = useState(null);
    const [setupStatus, setSetupStatus] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState('');

    const refresh = useCallback(async () => {
        try {
            const [nextSettings, nextStatus] = await Promise.all([settingsApi.get(), settingsApi.setupStatus()]);
            setSettings(nextSettings);
            setSetupStatus(nextStatus);
            setError('');
            return { settings: nextSettings, setupStatus: nextStatus };
        } catch (err) {
            // A 401 here is handled by the password gate; other errors surface in the UI.
            if (err?.response?.status !== 401) {
                setError(err?.response?.data?.detail || err?.message || '설정을 불러오지 못했습니다.');
            }
            return null;
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        refresh();
    }, [refresh]);

    const value = useMemo(
        () => ({ settings, setupStatus, loading, error, refresh, setSettings }),
        [settings, setupStatus, loading, error, refresh],
    );

    return <AppSettingsContext.Provider value={value}>{children}</AppSettingsContext.Provider>;
}
