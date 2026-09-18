import axios from 'axios';

// Vite dev server (5173) talks to the backend on 8000; any other origin is same-origin (Docker).
export const API_BASE_URL = window.location.port === '5173'
    ? `http://${window.location.hostname}:8000`
    : '';

const PASSWORD_STORAGE_KEY = 'sevensplit.dashboardPassword';
const PASSWORD_HEADER = 'X-Dashboard-Password';
const AUTH_REQUIRED_EVENT = 'sevensplit:auth-required';

export function getStoredPassword() {
    try {
        return localStorage.getItem(PASSWORD_STORAGE_KEY) || '';
    } catch {
        return '';
    }
}

export function applyPasswordHeader() {
    const password = getStoredPassword();
    if (password) {
        axios.defaults.headers.common[PASSWORD_HEADER] = password;
    } else {
        delete axios.defaults.headers.common[PASSWORD_HEADER];
    }
}

export function setStoredPassword(password) {
    try {
        if (password) {
            localStorage.setItem(PASSWORD_STORAGE_KEY, password);
        } else {
            localStorage.removeItem(PASSWORD_STORAGE_KEY);
        }
    } catch {
        // Storage may be unavailable (private mode); the header still applies for this session.
    }
    applyPasswordHeader();
}

// Every axios call in the app (including legacy components) inherits the password header
// and reports 401s through one event, so a single gate can prompt for the password.
applyPasswordHeader();
axios.interceptors.response.use(
    (response) => response,
    (error) => {
        if (error?.response?.status === 401) {
            window.dispatchEvent(new CustomEvent(AUTH_REQUIRED_EVENT));
        }
        return Promise.reject(error);
    },
);

export function onAuthRequired(handler) {
    window.addEventListener(AUTH_REQUIRED_EVENT, handler);
    return () => window.removeEventListener(AUTH_REQUIRED_EVENT, handler);
}

export function errorMessage(error, fallback = '요청에 실패했습니다.') {
    return error?.response?.data?.detail || error?.message || fallback;
}

const url = (path) => `${API_BASE_URL}${path}`;

export const api = {
    get: (path, config) => axios.get(url(path), config),
    post: (path, body, config) => axios.post(url(path), body, config),
    put: (path, body, config) => axios.put(url(path), body, config),
    delete: (path, config) => axios.delete(url(path), config),
};

export const settingsApi = {
    authStatus: () => api.get('/auth/status').then((r) => r.data),
    authCheck: (password) => api.post('/auth/check', { password }).then((r) => r.data),
    setupStatus: () => api.get('/setup/status').then((r) => r.data),
    get: () => api.get('/settings').then((r) => r.data),
    validateKeys: (accessKey, secretKey) =>
        api.post('/settings/validate', { access_key: accessKey || null, secret_key: secretKey || null }).then((r) => r.data),
    saveKeys: (accessKey, secretKey) =>
        api.put('/settings', { access_key: accessKey, secret_key: secretKey, validate_keys: true }).then((r) => r.data),
    deleteKeys: () => api.delete('/settings/keys').then((r) => r.data),
    setPaperInitialKrw: (amount) => api.put('/settings', { paper_initial_krw: amount }).then((r) => r.data),
    setResumeOnBoot: (enabled) => api.put('/settings', { resume_strategies_on_boot: enabled }).then((r) => r.data),
    switchMode: (mode) => api.post('/settings/mode', { mode }).then((r) => r.data),
};

export const marketApi = {
    tickers: () => api.get('/market/tickers').then((r) => r.data),
    price: (ticker) => api.get(`/market/price?ticker=${encodeURIComponent(ticker)}`).then((r) => r.data),
};

export const strategyApi = {
    list: () => api.get('/strategies').then((r) => r.data),
    create: (payload) => api.post('/strategies', payload).then((r) => r.data),
    start: (strategyId) => api.post('/bot/start', { strategy_id: strategyId }).then((r) => r.data),
    // Paper mode runs as a live simulation session (same path the dashboard uses).
    startSimulation: (strategyId) =>
        api.post('/simulations/live/start', { strategy_id: strategyId, replay_days: null, poll_seconds: 1 }).then((r) => r.data),
};
