import React, { useCallback, useEffect, useState } from 'react';
import Dashboard from './components/Dashboard';
import TopBar from './components/layout/TopBar';
import SetupWizard from './components/setup/SetupWizard';
import SettingsPage from './components/settings/SettingsPage';
import PasswordGate from './components/auth/PasswordGate';
import { AppSettingsProvider } from './context/AppSettingsContext';
import { useAppSettings } from './context/appSettingsStore';
import { getStoredPassword, onAuthRequired, settingsApi } from './lib/api';
import './styles/app-shell.css';

const VIEW_STORAGE_KEY = 'sevensplit.view';

function readStoredView() {
    try {
        const v = localStorage.getItem(VIEW_STORAGE_KEY);
        return v === 'settings' ? 'settings' : 'dashboard';
    } catch {
        return 'dashboard';
    }
}

function AppShell() {
    const { settings, setupStatus, loading, error, refresh } = useAppSettings();
    const [authState, setAuthState] = useState({ required: null, locked: false });
    const [view, setView] = useState(readStoredView);
    const [setupDismissed, setSetupDismissed] = useState(false);
    const [dashboardKey, setDashboardKey] = useState(0);

    // Password handling: ask once up front when the server requires it, and again on any 401.
    useEffect(() => {
        let mounted = true;
        settingsApi.authStatus().then(async (data) => {
            if (!mounted) return;
            const required = !!data.password_required;
            let locked = false;
            if (required) {
                const stored = getStoredPassword();
                if (!stored) {
                    locked = true;
                } else {
                    try {
                        await settingsApi.authCheck(stored);
                    } catch {
                        locked = true;
                    }
                }
            }
            setAuthState({ required, locked });
        }).catch(() => setAuthState({ required: false, locked: false }));
        return () => { mounted = false; };
    }, []);

    useEffect(() => onAuthRequired(() => setAuthState((s) => ({ ...s, required: true, locked: true }))), []);

    const navigate = useCallback((next) => {
        setView(next);
        try {
            localStorage.setItem(VIEW_STORAGE_KEY, next);
        } catch {
            // ignore storage failures
        }
        if (next === 'dashboard') {
            // Remount so the dashboard reloads strategies for the current mode.
            setDashboardKey((k) => k + 1);
        }
    }, []);

    const handleUnlocked = useCallback(async () => {
        setAuthState((s) => ({ ...s, locked: false }));
        await refresh();
    }, [refresh]);

    const showWizard = !loading && setupStatus?.needs_setup && !setupDismissed && view !== 'settings';

    if (authState.required === null || loading) {
        return <div className="app-loading">불러오는 중…</div>;
    }

    return (
        <>
            {authState.locked && <PasswordGate onUnlocked={handleUnlocked} />}
            {!showWizard && (
                <TopBar
                    mode={settings?.mode || 'DEV'}
                    view={view}
                    onNavigate={navigate}
                    passwordRequired={authState.required}
                    keyValid={settings?.key_valid}
                    hasKeys={settings?.has_keys}
                />
            )}
            {error && !settings && (
                <div className="app-error">
                    서버에 연결할 수 없습니다. 백엔드가 떠 있는지 확인하세요. ({error})
                </div>
            )}
            {showWizard ? (
                <SetupWizard
                    settings={settings}
                    onSettingsChanged={refresh}
                    onSkip={() => { setSetupDismissed(true); navigate('dashboard'); }}
                    onFinished={async () => {
                        await refresh();
                        setSetupDismissed(true);
                        navigate('dashboard');
                    }}
                />
            ) : view === 'settings' ? (
                <SettingsPage
                    settings={settings}
                    passwordRequired={authState.required}
                    onChanged={refresh}
                    onNavigate={navigate}
                />
            ) : (
                <Dashboard
                    key={dashboardKey}
                    heldOnBootIds={settings?.held_on_boot_ids || []}
                    onOpenSettings={() => navigate('settings')}
                    onStartSetup={() => { setSetupDismissed(false); refresh(); }}
                />
            )}
        </>
    );
}

export default function App() {
    return (
        <AppSettingsProvider>
            <AppShell />
        </AppSettingsProvider>
    );
}
