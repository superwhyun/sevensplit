import React, { useEffect, useState, useRef } from 'react';
import axios from 'axios';
import StrategyChart from './StrategyChart';
import Config from './Config';
import EventLog from './EventLog';
import StrategyStatusPanel from './StrategyStatusPanel';
import './Dashboard.css';

const AddStrategyModal = ({ isOpen, onClose, onAdd }) => {
    const [name, setName] = useState('');
    const [ticker, setTicker] = useState('KRW-BTC');
    const [budget, setBudget] = useState('1,000,000');

    if (!isOpen) return null;

    const handleSubmit = (e) => {
        e.preventDefault();
        onAdd({
            name,
            ticker,
            budget: parseFloat(budget.replace(/,/g, '')),
            config: {
                investment_per_split: 100000,
                min_price: 0,
                max_price: 0,
                buy_rate: 0.005,
                sell_rate: 0.005,
                fee_rate: 0.0005,
                tick_interval: 1.0,
                rebuy_strategy: "reset_on_clear",
                max_holdings: 20,
                price_segments: [
                    {
                        min_price: 0,
                        max_price: 1000000000,
                        investment_per_split: 100000,
                        max_splits: 20,
                    },
                ],
            }
        });
        onClose();
    };

    return (
        <div style={{
            position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
            backgroundColor: 'rgba(0,0,0,0.7)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000
        }}>
            <div style={{
                backgroundColor: '#1e293b', padding: '2rem', borderRadius: '0.5rem', width: '400px',
                border: '1px solid #334155', boxShadow: '0 10px 25px rgba(0,0,0,0.5)'
            }}>
                <h2 style={{ marginTop: 0, color: '#f8fafc' }}>Add New Strategy</h2>
                <form onSubmit={handleSubmit}>
                    <div style={{ marginBottom: '1rem' }}>
                        <label style={{ display: 'block', color: '#94a3b8', marginBottom: '0.5rem' }}>Strategy Name</label>
                        <input
                            type="text"
                            value={name}
                            onChange={(e) => setName(e.target.value)}
                            placeholder="e.g. BTC Aggressive"
                            required
                            style={{ width: '100%', padding: '0.5rem', borderRadius: '0.25rem', border: '1px solid #475569', backgroundColor: '#0f172a', color: 'white' }}
                        />
                    </div>
                    <div style={{ marginBottom: '1rem' }}>
                        <label style={{ display: 'block', color: '#94a3b8', marginBottom: '0.5rem' }}>Ticker</label>
                        <select
                            value={ticker}
                            onChange={(e) => setTicker(e.target.value)}
                            style={{ width: '100%', padding: '0.5rem', borderRadius: '0.25rem', border: '1px solid #475569', backgroundColor: '#0f172a', color: 'white' }}
                        >
                            <option value="KRW-BTC">KRW-BTC</option>
                            <option value="KRW-ETH">KRW-ETH</option>
                            <option value="KRW-SOL">KRW-SOL</option>
                            <option value="KRW-XRP">KRW-XRP</option>
                            <option value="KRW-DOGE">KRW-DOGE</option>
                        </select>
                    </div>
                    <div style={{ marginBottom: '1.5rem' }}>
                        <label style={{ display: 'block', color: '#94a3b8', marginBottom: '0.5rem' }}>Budget (KRW)</label>
                        <input
                            type="text"
                            value={budget}
                            onChange={(e) => setBudget(e.target.value.replace(/\D/g, '').replace(/\B(?=(\d{3})+(?!\d))/g, ","))}
                            required
                            style={{ width: '100%', padding: '0.5rem', borderRadius: '0.25rem', border: '1px solid #475569', backgroundColor: '#0f172a', color: 'white' }}
                        />
                    </div>
                    <div style={{ display: 'flex', gap: '1rem', justifyContent: 'flex-end' }}>
                        <button type="button" onClick={onClose} style={{ padding: '0.5rem 1rem', borderRadius: '0.25rem', border: 'none', backgroundColor: '#475569', color: 'white', cursor: 'pointer' }}>Cancel</button>
                        <button type="submit" style={{ padding: '0.5rem 1rem', borderRadius: '0.25rem', border: 'none', backgroundColor: '#3b82f6', color: 'white', cursor: 'pointer' }}>Create</button>
                    </div>
                </form>
            </div>
        </div>
    );
};

const ManualTargetModal = ({ isOpen, onClose, onSave, currentTarget }) => {
    const [price, setPrice] = useState('');

    useEffect(() => {
        if (currentTarget) {
            setPrice(Math.floor(currentTarget).toLocaleString());
        } else {
            setPrice('');
        }
    }, [currentTarget, isOpen]);

    if (!isOpen) return null;

    const handleSubmit = (e) => {
        e.preventDefault();
        const numericPrice = parseFloat(price.replace(/,/g, ''));
        onSave(isNaN(numericPrice) ? null : numericPrice);
        onClose();
    };

    return (
        <div style={{
            position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
            backgroundColor: 'rgba(0,0,0,0.7)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000
        }}>
            <div style={{
                backgroundColor: '#1e293b', padding: '2rem', borderRadius: '0.5rem', width: '400px',
                border: '1px solid #334155', boxShadow: '0 10px 25px rgba(0,0,0,0.5)'
            }}>
                <h2 style={{ marginTop: 0, color: '#f8fafc' }}>Set Manual Buy Target</h2>
                <p style={{ color: '#94a3b8', fontSize: '0.9rem', marginBottom: '1.5rem' }}>
                    The bot will ignore grid logic and buy exactly at this price.
                    (Leave empty to resume automatic grid logic)
                </p>
                <form onSubmit={handleSubmit}>
                    <div style={{ marginBottom: '1.5rem' }}>
                        <label style={{ display: 'block', color: '#94a3b8', marginBottom: '0.5rem' }}>Next Buy Target (KRW)</label>
                        <input
                            type="text"
                            value={price}
                            onChange={(e) => setPrice(e.target.value.replace(/\D/g, '').replace(/\B(?=(\d{3})+(?!\d))/g, ","))}
                            autoFocus
                            placeholder="e.g. 98,000,000"
                            style={{ width: '100%', padding: '0.5rem', borderRadius: '0.25rem', border: '1px solid #475569', backgroundColor: '#0f172a', color: 'white' }}
                        />
                    </div>
                    <div style={{ display: 'flex', gap: '1rem', justifyContent: 'flex-end' }}>
                        <button type="button" onClick={onClose} style={{ padding: '0.5rem 1rem', borderRadius: '0.25rem', border: 'none', backgroundColor: '#475569', color: 'white', cursor: 'pointer' }}>Cancel</button>
                        <button type="submit" style={{ padding: '0.5rem 1rem', borderRadius: '0.25rem', border: 'none', backgroundColor: '#3b82f6', color: 'white', cursor: 'pointer' }}>Save Target</button>
                    </div>
                </form>
            </div>
        </div>
    );
};

const RenameStrategyModal = ({ isOpen, onClose, onRename, currentName }) => {
    const [name, setName] = useState(currentName || '');

    useEffect(() => {
        setName(currentName || '');
    }, [currentName]);

    if (!isOpen) return null;

    const handleSubmit = (e) => {
        e.preventDefault();
        onRename(name);
        onClose();
    };

    return (
        <div style={{
            position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
            backgroundColor: 'rgba(0,0,0,0.7)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000
        }}>
            <div style={{
                backgroundColor: '#1e293b', padding: '2rem', borderRadius: '0.5rem', width: '400px',
                border: '1px solid #334155', boxShadow: '0 10px 25px rgba(0,0,0,0.5)'
            }}>
                <h2 style={{ marginTop: 0, color: '#f8fafc' }}>Rename Strategy</h2>
                <form onSubmit={handleSubmit}>
                    <div style={{ marginBottom: '1rem' }}>
                        <label style={{ display: 'block', color: '#94a3b8', marginBottom: '0.5rem' }}>New Name</label>
                        <input
                            type="text"
                            value={name}
                            onChange={(e) => setName(e.target.value)}
                            autoFocus
                            required
                            style={{ width: '100%', padding: '0.5rem', borderRadius: '0.25rem', border: '1px solid #475569', backgroundColor: '#0f172a', color: 'white' }}
                        />
                    </div>
                    <div style={{ display: 'flex', gap: '1rem', justifyContent: 'flex-end' }}>
                        <button type="button" onClick={onClose} style={{ padding: '0.5rem 1rem', borderRadius: '0.25rem', border: 'none', backgroundColor: '#475569', color: 'white', cursor: 'pointer' }}>Cancel</button>
                        <button type="submit" style={{ padding: '0.5rem 1rem', borderRadius: '0.25rem', border: 'none', backgroundColor: '#3b82f6', color: 'white', cursor: 'pointer' }}>Save</button>
                    </div>
                </form>
            </div>
        </div>
    );
};

const StatusPeekModal = ({ isOpen, onClose, statusMsg, ticker }) => {
    if (!isOpen) return null;
    return (
        <div style={{
            position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
            backgroundColor: 'rgba(0,0,0,0.7)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 10001
        }}>
            <div style={{
                backgroundColor: '#1e293b', padding: '1.5rem', borderRadius: '0.5rem', width: '450px',
                border: '1px solid #334155', boxShadow: '0 10px 25px rgba(0,0,0,0.5)'
            }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
                    <h3 style={{ margin: 0, color: '#f8fafc' }}>{ticker} Bot Status Peek</h3>
                    <button onClick={onClose} style={{ background: 'none', border: 'none', color: '#94a3b8', fontSize: '1.5rem', cursor: 'pointer' }}>×</button>
                </div>
                <div style={{
                    backgroundColor: '#0f172a', padding: '1rem', borderRadius: '0.375rem',
                    border: '1px solid #334155', color: '#e2e8f0', minHeight: '80px',
                    fontFamily: 'monospace', fontSize: '0.9rem', whiteSpace: 'pre-wrap'
                }}>
                    {statusMsg || "No status information available yet."}
                </div>
                <div style={{ marginTop: '1.5rem', display: 'flex', justifyContent: 'flex-end' }}>
                    <button onClick={onClose} style={{ padding: '0.5rem 1.5rem', borderRadius: '0.25rem', border: 'none', backgroundColor: '#3b82f6', color: 'white', cursor: 'pointer' }}>Close</button>
                </div>
            </div>
        </div>
    );
};

const StartBotModal = ({ isOpen, onClose, onStart, loading, strategyMode }) => {
    if (!isOpen) return null;

    const isRSI = strategyMode === 'RSI';

    const priceOptions = [
        { key: 'live', label: 'Live (Now)', desc: 'Start from current market and run continuously' },
        { key: '1d', label: 'Replay 1d', desc: 'Replay from 1 day ago to now' },
        { key: '3d', label: 'Replay 3d', desc: 'Replay from 3 days ago to now' },
        { key: '7d', label: 'Replay 7d', desc: 'Replay from 7 days ago to now' },
    ];

    const rsiOptions = [
        { key: 'live', label: 'Live (Now)', desc: 'Start from current market and run continuously' },
        { key: '1m', label: 'Replay 1 Month', desc: 'Replay ~30 daily candles, then continue live' },
        { key: '3m', label: 'Replay 3 Months', desc: 'Replay ~90 daily candles, then continue live' },
        { key: '6m', label: 'Replay 6 Months', desc: 'Replay ~180 daily candles, then continue live' },
        { key: '9m', label: 'Replay 9 Months', desc: 'Replay ~270 daily candles, then continue live' },
        { key: '12m', label: 'Replay 12 Months', desc: 'Replay ~365 daily candles, then continue live' },
        { key: '15m', label: 'Replay 15 Months', desc: 'Replay ~455 daily candles, then continue live' },
        { key: '18m', label: 'Replay 18 Months', desc: 'Replay ~548 daily candles, then continue live' },
        { key: '21m', label: 'Replay 21 Months', desc: 'Replay ~638 daily candles, then continue live' },
    ];

    const options = isRSI ? rsiOptions : priceOptions;

    return (
        <div style={{
            position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
            backgroundColor: 'rgba(0,0,0,0.7)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000
        }}>
            <div style={{
                backgroundColor: '#1e293b', padding: '1.5rem', borderRadius: '0.5rem', width: '460px',
                maxHeight: '85vh', overflowY: 'auto',
                border: '1px solid #334155', boxShadow: '0 10px 25px rgba(0,0,0,0.5)'
            }}>
                <h2 style={{ marginTop: 0, color: '#f8fafc', marginBottom: '0.4rem' }}>Start Dev Bot</h2>
                <p style={{ marginTop: 0, color: '#94a3b8', fontSize: '0.85rem' }}>
                    {isRSI
                        ? 'RSI Mode: Choose a replay window. Longer periods provide more signal history.'
                        : 'Choose where to start from. Replay starts from past candles, then continues with live ticks.'}
                </p>
                <div style={{ display: 'grid', gap: '0.6rem', marginTop: '1rem' }}>
                    {options.map((opt) => (
                        <button
                            key={opt.key}
                            onClick={() => onStart(opt.key)}
                            disabled={loading}
                            style={{
                                textAlign: 'left',
                                padding: '0.75rem 0.9rem',
                                borderRadius: '0.45rem',
                                border: '1px solid #334155',
                                backgroundColor: '#0f172a',
                                color: '#e2e8f0',
                                cursor: loading ? 'not-allowed' : 'pointer'
                            }}
                        >
                            <div style={{ fontWeight: 700, fontSize: '0.9rem' }}>{opt.label}</div>
                            <div style={{ fontSize: '0.75rem', color: '#94a3b8', marginTop: '0.15rem' }}>{opt.desc}</div>
                        </button>
                    ))}
                </div>
                <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: '1rem' }}>
                    <button
                        type="button"
                        onClick={onClose}
                        disabled={loading}
                        style={{ padding: '0.5rem 1rem', borderRadius: '0.25rem', border: 'none', backgroundColor: '#475569', color: 'white', cursor: loading ? 'not-allowed' : 'pointer' }}
                    >
                        Close
                    </button>
                </div>
            </div>
        </div>
    );
};

const formatTime = (t) => {
    if (!t) return '-';
    // Use ko-KR locale and Asia/Seoul timeZone to ensure KST
    const options = {
        year: 'numeric', month: '2-digit', day: '2-digit',
        hour: '2-digit', minute: '2-digit', second: '2-digit',
        hour12: false,
        timeZone: 'Asia/Seoul'
    };

    if (typeof t === 'number') {
        return new Date(t * 1000).toLocaleString('ko-KR', options);
    }

    // Ensure UTC if missing timezone info
    let timeStr = t;
    if (!timeStr.endsWith('Z') && !timeStr.includes('+')) {
        timeStr += 'Z';
    }
    return new Date(timeStr).toLocaleString('ko-KR', options);
};

const Dashboard = () => {
    const [status, setStatus] = useState(null);
    const [portfolio, setPortfolio] = useState(null);
    const [strategies, setStrategies] = useState([]);
    const [strategyConfig, setStrategyConfig] = useState(null);
    const [loading, setLoading] = useState(true);
    const [selectedStrategyId, setSelectedStrategyId] = useState(null);
    const [isModalOpen, setIsModalOpen] = useState(false);
    const [isRenameModalOpen, setIsRenameModalOpen] = useState(false);
    const [isManualTargetModalOpen, setIsManualTargetModalOpen] = useState(false);
    const [isStatusPeekModalOpen, setIsStatusPeekModalOpen] = useState(false);
    const [isStartBotModalOpen, setIsStartBotModalOpen] = useState(false);
    const [tradesPage, setTradesPage] = useState(1);
    const [simActionLoading, setSimActionLoading] = useState(false);
    const [liveSessionId, setLiveSessionId] = useState(null);
    const [liveSessionState, setLiveSessionState] = useState(null);
    const [liveError, setLiveError] = useState('');
    const [simOverlayState, setSimOverlayState] = useState(null);
    const [simMeta, setSimMeta] = useState(null);
    const [simSystemEvents, setSimSystemEvents] = useState([]);
    const [strategyEvents, setStrategyEvents] = useState([]);
    const TRADES_PER_PAGE = 10;

    const selectedStrategyIdRef = useRef(selectedStrategyId);
    const simOverlayActiveRef = useRef(false);

    // Keep ref in sync with state
    useEffect(() => {
        selectedStrategyIdRef.current = selectedStrategyId;
    }, [selectedStrategyId]);

    useEffect(() => {
        simOverlayActiveRef.current = !!simOverlayState;
    }, [simOverlayState]);

    // If running on Vite dev server (port 5173), point to backend port 8000.
    // Otherwise (Docker/Production), use relative path (same origin).
    const API_BASE_URL = window.location.port === '5173'
        ? `http://${window.location.hostname}:8000`
        : '';
    const getReplaySnapshotKey = (strategyId) => `devReplaySnapshot:${strategyId}`;

    const saveReplaySnapshot = (strategyId, payload) => {
        try {
            if (!strategyId || !payload) return;
            localStorage.setItem(getReplaySnapshotKey(strategyId), JSON.stringify(payload));
        } catch (e) {
            console.warn('Failed to persist replay snapshot:', e);
        }
    };

    const loadReplaySnapshot = (strategyId) => {
        try {
            if (!strategyId) return null;
            const raw = localStorage.getItem(getReplaySnapshotKey(strategyId));
            if (!raw) return null;
            const parsed = JSON.parse(raw);
            if (!parsed || typeof parsed !== 'object') return null;
            return parsed;
        } catch (e) {
            console.warn('Failed to load replay snapshot:', e);
            return null;
        }
    };

    const clearReplaySnapshot = (strategyId) => {
        try {
            if (!strategyId) return;
            localStorage.removeItem(getReplaySnapshotKey(strategyId));
        } catch (e) {
            console.warn('Failed to clear replay snapshot:', e);
        }
    };

    const fetchStrategies = async () => {
        try {
            const response = await axios.get(`${API_BASE_URL}/strategies`);
            setStrategies(response.data);

            // Try to restore selection from localStorage
            const savedId = localStorage.getItem('selectedStrategyId');
            if (response.data.length > 0) {
                if (savedId && response.data.find(s => s.id === parseInt(savedId))) {
                    setSelectedStrategyId(parseInt(savedId));
                } else if (!selectedStrategyId) {
                    setSelectedStrategyId(response.data[0].id);
                }
            } else {
                setLoading(false);
            }
        } catch (error) {
            console.error('Error fetching strategies:', error);
            setLoading(false);
        }
    };

    const fetchStatus = async () => {
        if (!selectedStrategyIdRef.current) return;
        try {
            const currentId = selectedStrategyIdRef.current;
            const response = await axios.get(`${API_BASE_URL}/strategies/${currentId}/status`);
            const { config, ...restStatus } = response.data;
            setStatus(restStatus);
            // Include budget in config to prevent WebSocket updates from triggering Config component re-renders
            const safeConfig = config && typeof config === 'object' ? config : {};
            setStrategyConfig({ strategy_mode: 'PRICE', ...safeConfig, budget: response.data.budget });
            setLoading(false);
        } catch (error) {
            console.error('Error fetching status:', error);
            setLoading(false);
        }
    };

    const fetchStrategyEvents = async (strategyId = null) => {
        const id = strategyId || selectedStrategyIdRef.current;
        if (!id) return;
        try {
            const response = await axios.get(`${API_BASE_URL}/strategies/${id}/events?page=1&limit=200`);
            setStrategyEvents(response.data?.events || []);
        } catch (error) {
            console.error('Error fetching strategy events:', error);
        }
    };

    const fetchPortfolio = async () => {
        try {
            const response = await axios.get(`${API_BASE_URL}/portfolio`);
            setPortfolio(response.data);
        } catch (error) {
            console.error('Error fetching portfolio:', error);
        }
    };

    const wsRef = useRef(null);

    useEffect(() => {
        // Initial fetch
        fetchStrategies();
        fetchPortfolio();

        // Set up websocket connection for live updates
        const wsProtocol = window.location.protocol === 'https:' ? 'wss' : 'ws';
        const wsHost = window.location.port === '5173'
            ? `${window.location.hostname}:8000`
            : window.location.host;

        let retryTimer;
        let fallbackTimer;

        const startFallback = () => {
            if (fallbackTimer) return;
            fallbackTimer = setInterval(() => {
                fetchStatus();
                fetchPortfolio();
            }, 2000);
        };

        const stopFallback = () => {
            if (fallbackTimer) {
                clearInterval(fallbackTimer);
                fallbackTimer = null;
            }
        };

        const connect = () => {
            try {
                const wsUrl = `${wsProtocol}://${wsHost}/ws`;
                const ws = new WebSocket(wsUrl);
                wsRef.current = ws;

                ws.onopen = () => {
                    stopFallback();
                    if (retryTimer) {
                        clearTimeout(retryTimer);
                    }
                };

                ws.onmessage = (event) => {
                    try {
                        const data = JSON.parse(event.data);
                        if (data?.strategies) {
                            const currentId = selectedStrategyIdRef.current;
                            // strategies is an array, find the one with matching id
                            const strategy = data.strategies.find(s => s.id === currentId);
                            if (strategy) {
                                if (!simOverlayActiveRef.current) {
                                    setStatus(prev => {
                                        if (!prev || prev.id !== strategy.id) return strategy;
                                        // Preserve existing config if the incoming update doesn't have it
                                        return {
                                            ...prev,
                                            ...strategy,
                                            config: strategy.config || prev.config || {} // Ensure config is at least {}
                                        };
                                    });
                                }
                                setLoading(false);
                            }
                        }
                        if (data?.portfolio) {
                            setPortfolio(data.portfolio);
                        }
                    } catch (err) {
                        console.error('WS parse error', err);
                    }
                };

                ws.onclose = () => {
                    startFallback();
                    retryTimer = setTimeout(connect, 2000);
                };

                ws.onerror = () => {
                    startFallback();
                };
            } catch (err) {
                console.error('WS init error', err);
                startFallback();
                retryTimer = setTimeout(connect, 2000);
            }
        };

        connect();

        return () => {
            if (wsRef.current) {
                wsRef.current.close();
            }
            stopFallback();
            if (retryTimer) {
                clearTimeout(retryTimer);
            }
        };
    }, []);

    // When strategy changes, fetch the new status and save to localStorage
    useEffect(() => {
        if (selectedStrategyId) {
            localStorage.setItem('selectedStrategyId', selectedStrategyId);
            fetchStatus();
            setTradesPage(1); // Reset page when strategy changes
        }
    }, [selectedStrategyId]);

    const handleStart = async () => {
        if (portfolio?.mode === 'DEV') {
            setIsStartBotModalOpen(true);
            return;
        }
        try {
            await axios.post(`${API_BASE_URL}/bot/start`, { strategy_id: selectedStrategyId });
            fetchStatus();
        } catch (error) {
            console.error('Error starting bot:', error);
        }
    };

    const handleStop = async () => {
        if (portfolio?.mode === 'DEV') {
            setSimActionLoading(true);
            try {
                if (liveSessionId) {
                    try {
                        console.log("[SIM] Force stopping simulation session:", liveSessionId);
                        await axios.post(`${API_BASE_URL}/simulations/live/${liveSessionId}/stop`);
                        await fetchLiveSessionStatus(liveSessionId);
                    } catch (simErr) {
                        console.warn('Simulation stop failed (continuing with bot stop):', simErr);
                    }
                }
                await axios.post(`${API_BASE_URL}/bot/stop`, { strategy_id: selectedStrategyId });
            } catch (error) {
                console.error('Error stopping dev runtime:', error);
                alert(`Stop failed: ${error.response?.data?.detail || error.message}`);
            } finally {
                setLiveError('');
                setSimActionLoading(false);
                fetchStatus();
            }
            return;
        }
        try {
            await axios.post(`${API_BASE_URL}/bot/stop`, { strategy_id: selectedStrategyId });
            fetchStatus();
        } catch (error) {
            console.error('Error stopping bot:', error);
            alert(`Stop failed: ${error.response?.data?.detail || error.message}`);
        }
    };

    const handleHardStop = async () => {
        if (!window.confirm('Stop Trading will cancel both pending BUY and SELL orders. Continue?')) {
            return;
        }

        if (portfolio?.mode === 'DEV') {
            setSimActionLoading(true);
            try {
                if (liveSessionId) {
                    try {
                        console.log("[SIM] Force stopping simulation session:", liveSessionId);
                        await axios.post(`${API_BASE_URL}/simulations/live/${liveSessionId}/stop`);
                        await fetchLiveSessionStatus(liveSessionId);
                    } catch (simErr) {
                        console.warn('Simulation stop failed (continuing with hard stop):', simErr);
                    }
                }
                await axios.post(`${API_BASE_URL}/bot/hard-stop`, { strategy_id: selectedStrategyId });
            } catch (error) {
                console.error('Error hard-stopping dev runtime:', error);
                alert(`Stop Trading failed: ${error.response?.data?.detail || error.message}`);
            } finally {
                setLiveError('');
                setSimActionLoading(false);
                fetchStatus();
            }
            return;
        }

        try {
            await axios.post(`${API_BASE_URL}/bot/hard-stop`, { strategy_id: selectedStrategyId });
            fetchStatus();
        } catch (error) {
            console.error('Error hard-stopping bot:', error);
            alert(`Stop Trading failed: ${error.response?.data?.detail || error.message}`);
        }
    };

    const handleReset = async () => {
        if (!window.confirm(`Are you sure you want to reset this strategy?\n\nThis will:\n- Cancel all active orders for this strategy\n- Clear active splits (positions)\n- DELETE all trade history\n\n(Your wallet balance will NOT be reset)`)) {
            return;
        }
        try {
            // Stop simulation if active in DEV mode
            if (portfolio?.mode === 'DEV' && liveSessionId) {
                try {
                    await axios.post(`${API_BASE_URL}/simulations/live/${liveSessionId}/stop`);
                } catch (e) {
                    console.warn('Failed to stop simulation session on reset:', e);
                }
            }

            await axios.post(`${API_BASE_URL}/bot/reset`, { strategy_id: selectedStrategyId });

            // Clear Simulation UI State
            if (portfolio?.mode === 'DEV') {
                setLiveError('');
                setSimOverlayState(null);
                setLiveSessionId(null);
                setLiveSessionState(null);
            }

            fetchStatus();
            fetchPortfolio();
        } catch (error) {
            console.error('Error resetting bot:', error);
            alert(`Reset failed: ${error.response?.data?.detail || error.message}`);
        }
    };

    const handleAddStrategy = async (strategyData) => {
        try {
            const response = await axios.post(`${API_BASE_URL}/strategies`, strategyData);
            await fetchStrategies();
            setSelectedStrategyId(response.data.strategy_id);
        } catch (error) {
            console.error('Error creating strategy:', error);
            alert('Failed to create strategy');
        }
    };

    const handleDeleteStrategy = async () => {
        if (!window.confirm(`Are you sure you want to DELETE this strategy? This cannot be undone.`)) {
            return;
        }
        try {
            await axios.delete(`${API_BASE_URL}/strategies/${selectedStrategyId}`);
            const newStrategies = strategies.filter(s => s.id !== selectedStrategyId);
            setStrategies(newStrategies);
            if (newStrategies.length > 0) {
                setSelectedStrategyId(newStrategies[0].id);
            } else {
                setSelectedStrategyId(null);
                setStatus(null);
            }
        } catch (error) {
            console.error('Error deleting strategy:', error);
            alert('Failed to delete strategy');
        }
    };

    const handleExport = () => {
        const isSimulationView = isDevMode && (!!simOverlayState || !!liveSessionId);
        if (!isSimulationView) {
            window.open(`${API_BASE_URL}/strategies/${selectedStrategyId}/export`, '_blank');
            return;
        }

        const trades = displayedStatus?.trade_history || [];
        if (!trades.length) {
            alert('No simulation trades to export.');
            return;
        }

        const escapeCsv = (value) => {
            if (value === null || value === undefined) return '';
            const str = String(value);
            if (str.includes('"') || str.includes(',') || str.includes('\n')) {
                return `"${str.replace(/"/g, '""')}"`;
            }
            return str;
        };

        const header = [
            'Split ID', 'Ticker', 'Buy Price', 'Sell Price', 'Volume',
            'Buy Amount', 'Sell Amount', 'Gross Profit', 'Net Profit', 'Fee',
            'Profit Rate', 'Bought At', 'Closed At'
        ];
        const rows = trades.map((t) => ([
            t.split_id ?? '',
            displayedStatus?.ticker ?? '',
            t.buy_price ?? '',
            t.sell_price ?? '',
            t.volume ?? '',
            t.buy_amount ?? '',
            t.sell_amount ?? '',
            t.gross_profit ?? '',
            t.net_profit ?? '',
            t.total_fee ?? '',
            t.profit_rate ?? '',
            t.bought_at ?? '',
            t.timestamp ?? '',
        ]));

        const csv = [header, ...rows]
            .map((row) => row.map(escapeCsv).join(','))
            .join('\n');

        const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
        const url = URL.createObjectURL(blob);
        const link = document.createElement('a');
        const stamp = new Date().toISOString().replace(/[:.]/g, '-');
        link.href = url;
        link.download = `simulation_trades_strategy_${selectedStrategyId}_${stamp}.csv`;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        URL.revokeObjectURL(url);
    };



    const handleRenameStrategy = () => {
        setIsRenameModalOpen(true);
    };

    const performRename = async (newName) => {
        if (newName && newName.trim() !== "") {
            try {
                // If running on Vite dev server (port 5173), point to backend port 8000.
                const API_BASE_URL = window.location.port === '5173'
                    ? `http://${window.location.hostname}:8000`
                    : '';

                await axios.patch(`${API_BASE_URL}/strategies/${selectedStrategyId}`, { name: newName });
                fetchStatus(); // Refresh current view
                fetchStrategies(); // Refresh tab list
            } catch (error) {
                console.error("Failed to rename strategy:", error);
                alert("Failed to rename strategy");
            }
        }
    };

    const handleSetManualTarget = async (price) => {
        try {
            await axios.post(`${API_BASE_URL}/strategies/${selectedStrategyId}/manual-target`, {
                target_price: price
            });
            fetchStatus(); // Refresh base status UI
            if (liveSessionId) {
                await fetchLiveSessionStatus(liveSessionId);
            }
        } catch (error) {
            console.error('Error setting manual target:', error);
            alert('Failed to set manual target price');
        }
    };

    const findLiveSessionForStrategy = async (strategyId) => {
        if (!strategyId) return null;
        try {
            const response = await axios.get(`${API_BASE_URL}/simulations/live`);
            const sessions = response?.data?.sessions || [];
            const target = sessions.find(s => s.strategy_id === strategyId && s.status === 'running')
                || sessions.find(s => s.strategy_id === strategyId);
            return target || null;
        } catch (error) {
            console.error('Error listing live simulations:', error);
            return null;
        }
    };

    const fetchLiveSessionStatus = async (sessionId) => {
        if (!sessionId) return;
        try {
            const response = await axios.get(`${API_BASE_URL}/simulations/live/${sessionId}`);
            setLiveSessionState(response.data);
            if (response.data?.final_state) {
                setSimOverlayState({
                    ...response.data.final_state,
                    is_running: true,
                    status: 'Simulation (Live)',
                });
                setSimMeta({
                    mode: response.data?.replay_days ? `replay+live-${response.data.replay_days}d` : 'live',
                    trades: response.data?.trades ?? 0,
                    realized_profit: response.data?.realized_profit ?? 0,
                    cumulative_buy_amount: response.data?.cumulative_buy_amount ?? 0,
                    cumulative_sell_amount: response.data?.cumulative_sell_amount ?? 0,
                    max_invested_amount: response.data?.max_invested_amount ?? 0,
                    source: 'live'
                });
                setSimSystemEvents(response.data?.sim_events || []);
            }
            setLiveError('');
        } catch (error) {
            const detail = error.response?.data?.detail || '';
            const notFound = String(detail).toLowerCase().includes('not found');
            if (!notFound) {
                console.error('Error fetching live simulation status:', error);
            }
            setLiveSessionState(null);
            setLiveSessionId(null);
            // Session can disappear after backend restart or stale client state.
            // Clear it silently to avoid noisy UX.
            if (notFound) {
                setLiveError('');
                return;
            }
            setLiveError(detail || 'Failed to fetch live simulation status');
        }
    };

    const handleStartDevBot = async (startOption) => {
        if (!selectedStrategyId) return;
        setSimActionLoading(true);
        setLiveError('');
        setIsStartBotModalOpen(false);
        try {
            // Ensure real strategy loop is not running in parallel with live simulation.
            await axios.post(`${API_BASE_URL}/bot/stop`, { strategy_id: selectedStrategyId });
            clearReplaySnapshot(selectedStrategyId);
            const replayDays = startOption === 'live' ? 0
                : startOption.endsWith('m') ? parseInt(startOption) * 30
                    : parseInt(startOption.replace('d', ''), 10);
            const response = await axios.post(`${API_BASE_URL}/simulations/live/start`, {
                strategy_id: selectedStrategyId,
                replay_days: replayDays > 0 ? replayDays : null,
                poll_seconds: 1
            });
            const sessionId = response.data?.session_id;
            setLiveSessionId(sessionId || null);
            setSimMeta({
                mode: replayDays > 0 ? `replay+live-${replayDays}d` : 'live',
                trades: 0,
                realized_profit: 0,
                cumulative_buy_amount: 0,
                cumulative_sell_amount: 0,
                max_invested_amount: 0,
                source: 'live'
            });
            setSimSystemEvents([]);
            if (sessionId) {
                await fetchLiveSessionStatus(sessionId);
            }
        } catch (error) {
            console.error('Error starting dev bot simulation:', error);
            const msg = error.response?.data?.detail || 'Failed to start simulation';
            setLiveError(msg);
            alert(msg);
        } finally {
            setSimActionLoading(false);
        }
    };

    const getNextBuyTarget = (statusData) => {
        if (!statusData) return null;

        const effectiveNext = Number(statusData.next_buy_target_price);
        if (Number.isFinite(effectiveNext) && effectiveNext > 0) {
            return Math.floor(effectiveNext);
        }

        // Calculate from last_buy_price
        const lastBuy = Number(statusData.last_buy_price);
        if (!Number.isFinite(lastBuy) || lastBuy <= 0) return null;

        const buyRate = Number(statusData.config?.buy_rate ?? strategyConfig?.buy_rate);
        const resolvedBuyRate = Number.isFinite(buyRate) ? buyRate : 0.005;

        return Math.floor(lastBuy * (1 - resolvedBuyRate));
    };

    const displayedStatus = simOverlayState || status;
    const resolvedConfig = strategyConfig ?? displayedStatus?.config ?? {};
    const isDevMode = portfolio?.mode === 'DEV';
    const isDevSimulationActive = isDevMode && (liveSessionState?.status === 'running');
    const isDevBotRunning = isDevMode && !!displayedStatus?.is_running;
    const canStartInDev = isDevMode && !isDevSimulationActive && !isDevBotRunning;
    const gateEventTypes = new Set(['BUY_GATE', 'WATCH_START', 'WATCH_END']);
    const simEventsForLog = (simSystemEvents || []).filter((e) => gateEventTypes.has(e?.event_type));

    useEffect(() => {
        let mounted = true;
        const load = async () => {
            if (!selectedStrategyId) {
                setLiveSessionId(null);
                setLiveSessionState(null);
                setSimOverlayState(null);
                setSimMeta(null);
                setSimSystemEvents([]);
                setStrategyEvents([]);
                return;
            }
            await fetchStrategyEvents(selectedStrategyId);
            const session = await findLiveSessionForStrategy(selectedStrategyId);
            if (!mounted) return;
            if (session?.session_id) {
                setLiveSessionId(session.session_id);
                await fetchLiveSessionStatus(session.session_id);
            } else {
                setLiveSessionId(null);
                setLiveSessionState(null);
                const replay = loadReplaySnapshot(selectedStrategyId);
                if (replay?.overlay_state) {
                    setSimOverlayState(replay.overlay_state);
                    setSimMeta(replay.meta || null);
                    setSimSystemEvents(replay.sim_events || []);
                } else {
                    setSimOverlayState(null);
                    setSimMeta(null);
                    setSimSystemEvents([]);
                }
            }
        };
        load();
        return () => {
            mounted = false;
        };
    }, [selectedStrategyId]);

    useEffect(() => {
        if (!liveSessionId) return;
        const timer = setInterval(() => {
            fetchLiveSessionStatus(liveSessionId);
        }, 5000);
        return () => clearInterval(timer);
    }, [liveSessionId]);

    useEffect(() => {
        if (!selectedStrategyId) return;
        const timer = setInterval(() => {
            if (!simOverlayState) {
                fetchStrategyEvents(selectedStrategyId);
            }
        }, 10000);
        return () => clearInterval(timer);
    }, [selectedStrategyId, simOverlayState]);

    if (!displayedStatus && strategies.length > 0) return <div style={{ padding: '2rem', color: 'white' }}>Loading Strategy...</div>;
    if (!portfolio) return <div style={{ padding: '2rem', color: 'white' }}>Loading Portfolio...</div>;

    return (
        <div className="dashboard-container" style={{ position: 'relative' }}>

            <AddStrategyModal isOpen={isModalOpen} onClose={() => setIsModalOpen(false)} onAdd={handleAddStrategy} />
            <RenameStrategyModal
                isOpen={isRenameModalOpen}
                onClose={() => setIsRenameModalOpen(false)}
                onRename={performRename}
                currentName={displayedStatus?.name}
            />

            <StatusPeekModal
                isOpen={isStatusPeekModalOpen}
                onClose={() => setIsStatusPeekModalOpen(false)}
                statusMsg={displayedStatus?.status_msg}
                ticker={displayedStatus?.ticker}
            />

            <ManualTargetModal
                isOpen={isManualTargetModalOpen}
                onClose={() => setIsManualTargetModalOpen(false)}
                onSave={handleSetManualTarget}
                currentTarget={getNextBuyTarget(displayedStatus)}
            />
            <StartBotModal
                isOpen={isStartBotModalOpen}
                onClose={() => setIsStartBotModalOpen(false)}
                onStart={handleStartDevBot}
                loading={simActionLoading}
                strategyMode={resolvedConfig?.strategy_mode || 'PRICE'}
            />

            {/* Global Portfolio Header */}
            <header className="header" style={{
                display: 'block',
                padding: '1.5rem',
                backgroundColor: 'rgba(15, 23, 42, 0.9)',
                borderBottom: '2px solid #334155'
            }}>
                <div className="header-top-row">
                    <h1 className="logo" style={{ margin: 0, fontSize: '1.75rem' }}>Seven Split Bot</h1>

                    {/* Mode Indicator */}
                    <div className="mode-indicator" style={{
                        backgroundColor: portfolio?.mode === 'REAL' ? '#ef4444' : '#0ea5e9',
                    }}>
                        <div className="mode-dot" />
                        {portfolio?.mode === 'REAL' ? 'REAL TRADING' : 'DEV SIMULATION'}
                    </div>
                </div>

                {/* Overall Portfolio Stats - Compact Card */}
                <div className="portfolio-summary-card">
                    <div className="portfolio-main-stats">
                        <div className="total-value-section">
                            <span className="label">Total Assets</span>
                            <span className="value">₩{Math.round(portfolio.total_value)?.toLocaleString()}</span>
                        </div>
                        <div className="profit-section">
                            <span className="label">Realized Profit</span>
                            <span className="value" style={{ color: (portfolio.total_realized_profit || 0) >= 0 ? '#10b981' : '#ef4444' }}>
                                {new Intl.NumberFormat('ko-KR', { style: 'currency', currency: 'KRW' }).format(portfolio.total_realized_profit || 0)}
                            </span>
                        </div>
                    </div>

                    <div className="assets-scroll-container">
                        {/* KRW Chip */}
                        <div className="asset-chip krw">
                            <span className="asset-name">🇰🇷 KRW</span>
                            <span className="asset-value">₩{Math.round(portfolio.balance_krw || 0).toLocaleString()}</span>
                            <span className="asset-amount">Cash</span>
                        </div>

                        {/* Coin Chips */}
                        {Object.entries(portfolio.coins)
                            .sort(([, a], [, b]) => b.value - a.value)
                            .slice(0, 3)
                            .map(([coin, data]) => (
                                <div key={coin} className="asset-chip">
                                    <span className="asset-name">{coin}</span>
                                    <span className="asset-value">₩{Math.round(data.value || 0).toLocaleString()}</span>
                                    <span className="asset-amount">{data.balance?.toFixed(4)} {coin}</span>
                                </div>
                            ))}
                    </div>
                </div>
            </header>

            {/* Strategy Tabs */}
            <div className="tabs" style={{
                display: 'flex',
                gap: '0.5rem',
                overflowX: 'auto',
                padding: '0 1.5rem',
                borderBottom: '1px solid #334155',
                backgroundColor: 'rgba(15, 23, 42, 0.8)'
            }}>
                {strategies.map(s => (
                    <button
                        key={s.id}
                        className={`tab-btn ${selectedStrategyId === s.id ? 'active' : ''}`}
                        onClick={() => {
                            setLoading(true);
                            setSelectedStrategyId(s.id);
                        }}
                        style={{
                            padding: '0.75rem 1.25rem',
                            backgroundColor: selectedStrategyId === s.id ? '#3b82f6' : 'transparent',
                            color: selectedStrategyId === s.id ? 'white' : '#94a3b8',
                            border: 'none',
                            borderTopLeftRadius: '0.5rem',
                            borderTopRightRadius: '0.5rem',
                            cursor: 'pointer',
                            fontWeight: selectedStrategyId === s.id ? 'bold' : 'normal',
                            whiteSpace: 'nowrap',
                            display: 'flex',
                            flexDirection: 'column',
                            alignItems: 'center',
                            gap: '0.1rem',
                            minWidth: '100px'
                        }}
                    >
                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                            <span style={{ fontSize: '0.9rem' }}>{s.name}</span>
                            {selectedStrategyId === s.id && (
                                <span
                                    onClick={(e) => {
                                        e.stopPropagation();
                                        handleRenameStrategy();
                                    }}
                                    style={{
                                        cursor: 'pointer',
                                        opacity: 0.6,
                                        fontSize: '0.8rem',
                                        padding: '0 0.2rem',
                                        color: 'white'
                                    }}
                                    title="Rename Strategy"
                                >
                                    ✎
                                </span>
                            )}
                        </div>
                        <span style={{ fontSize: '0.7rem', opacity: 0.8 }}>{s.ticker}</span>
                    </button>
                ))}
                <button
                    onClick={() => setIsModalOpen(true)}
                    style={{
                        padding: '0.75rem 1rem',
                        backgroundColor: 'transparent',
                        color: '#3b82f6',
                        border: 'none',
                        cursor: 'pointer',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '0.5rem',
                        fontSize: '0.9rem'
                    }}
                >
                    + New
                </button>
            </div>

            {displayedStatus && (
                <>
                    {/* Strategy Stats (Top Row) */}
                    <div style={{
                        padding: '1.5rem',
                        backgroundColor: 'rgba(15, 23, 42, 0.7)',
                        borderBottom: '1px solid #334155'
                    }}>
                        <div className="strategy-stats-grid">
                            <div style={{
                                padding: '1rem',
                                backgroundColor: 'rgba(59, 130, 246, 0.1)',
                                borderRadius: '0.5rem',
                                border: '1px solid rgba(59, 130, 246, 0.3)'
                            }}>
                                <div style={{ fontSize: '0.75rem', color: '#94a3b8', marginBottom: '0.5rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                                    <span>Current Price</span>
                                </div>
                                <div style={{ fontSize: '1.5rem', fontWeight: 'bold', color: '#3b82f6' }}>
                                    ₩{displayedStatus?.current_price?.toLocaleString()}
                                </div>
                                <div style={{
                                    marginTop: '0.5rem',
                                    paddingTop: '0.5rem',
                                    borderTop: '1px solid rgba(59, 130, 246, 0.2)',
                                    display: 'flex',
                                    alignItems: 'center',
                                    justifyContent: 'space-between',
                                    fontSize: '0.85rem'
                                }}>
                                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.5rem', width: '100%' }}>
                                        {/* 5m RSI */}
                                        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.1rem' }}>
                                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '0.8rem' }}>
                                                <span style={{ color: '#94a3b8' }}>RSI(14)/5m</span>
                                                <span style={{ fontWeight: 'bold', color: (displayedStatus.rsi >= 70) ? '#ef4444' : (displayedStatus.rsi <= 30 && displayedStatus.rsi != null) ? '#10b981' : '#f59e0b' }}>
                                                    {(displayedStatus.rsi !== undefined && displayedStatus.rsi !== null) ? Math.round(displayedStatus.rsi) : '-'}
                                                </span>
                                            </div>
                                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '0.8rem' }}>
                                                <span style={{ color: '#94a3b8' }}>RSI(5)/5m</span>
                                                <span style={{ fontWeight: 'bold', color: (displayedStatus.rsi_short >= 70) ? '#ef4444' : (displayedStatus.rsi_short <= 30 && displayedStatus.rsi_short != null) ? '#10b981' : '#f59e0b' }}>
                                                    {(displayedStatus.rsi_short !== undefined && displayedStatus.rsi_short !== null) ? Math.round(displayedStatus.rsi_short) : '-'}
                                                </span>
                                            </div>
                                        </div>

                                        {/* Daily RSI */}
                                        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.1rem', borderLeft: '1px solid rgba(255,255,255,0.1)', paddingLeft: '0.5rem' }}>
                                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '0.8rem' }}>
                                                <span style={{ color: '#94a3b8' }}>RSI({displayedStatus?.config?.rsi_period ?? 14})/D</span>
                                                <span style={{ fontWeight: 'bold', color: (displayedStatus.rsi_daily >= 70) ? '#ef4444' : (displayedStatus.rsi_daily <= 30 && displayedStatus.rsi_daily != null) ? '#10b981' : '#f59e0b' }}>
                                                    {(displayedStatus.rsi_daily !== undefined && displayedStatus.rsi_daily !== null) ? Math.round(displayedStatus.rsi_daily) : '-'}
                                                </span>
                                            </div>
                                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '0.8rem' }}>
                                                <span style={{ color: '#94a3b8' }}>RSI(4)/D</span>
                                                <span style={{ fontWeight: 'bold', color: (displayedStatus.rsi_daily_short >= 70) ? '#ef4444' : (displayedStatus.rsi_daily_short <= 30 && displayedStatus.rsi_daily_short != null) ? '#10b981' : '#f59e0b' }}>
                                                    {(displayedStatus.rsi_daily_short !== undefined && displayedStatus.rsi_daily_short !== null) ? Math.round(displayedStatus.rsi_daily_short) : '-'}
                                                </span>
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            </div>
                            <div style={{
                                padding: '1rem',
                                backgroundColor: 'rgba(139, 92, 246, 0.1)',
                                borderRadius: '0.5rem',
                                border: '1px solid rgba(139, 92, 246, 0.3)'
                            }}>
                                <div style={{ fontSize: '0.75rem', color: '#94a3b8', marginBottom: '0.5rem' }}>Coin Holdings</div>
                                <div style={{ fontSize: '1.25rem', fontWeight: 'bold', color: '#a78bfa' }}>
                                    {(displayedStatus.total_coin_volume || 0).toFixed(8)}
                                </div>
                                <div style={{ fontSize: '0.7rem', color: '#94a3b8', marginTop: '0.25rem' }}>
                                    {displayedStatus.ticker?.split('-')[1] || 'Coin'}
                                </div>
                            </div>
                            {/* Valuation Card */}
                            <div style={{
                                padding: '1rem',
                                backgroundColor: 'rgba(16, 185, 129, 0.1)',
                                borderRadius: '0.5rem',
                                border: '1px solid rgba(16, 185, 129, 0.3)'
                            }}>
                                <div style={{ fontSize: '0.75rem', color: '#94a3b8', marginBottom: '0.5rem' }}>Market Value</div>
                                <div style={{ fontSize: '1.25rem', fontWeight: 'bold', color: '#10b981' }}>
                                    ₩{Math.round(displayedStatus.total_valuation || 0).toLocaleString()}
                                </div>
                                <div style={{ fontSize: '0.7rem', color: '#94a3b8', marginTop: '0.25rem' }}>
                                    {`Invested Amount: ₩${Math.round(displayedStatus.total_invested || 0).toLocaleString()}`}
                                </div>
                            </div>

                            {/* Profit Card */}
                            <div style={{
                                padding: '1rem',
                                backgroundColor: (displayedStatus.total_profit_amount || 0) >= 0
                                    ? 'rgba(16, 185, 129, 0.1)'
                                    : 'rgba(239, 68, 68, 0.1)',
                                borderRadius: '0.5rem',
                                border: (displayedStatus.total_profit_amount || 0) >= 0
                                    ? '1px solid rgba(16, 185, 129, 0.3)'
                                    : '1px solid rgba(239, 68, 68, 0.3)'
                            }}>
                                <div style={{ fontSize: '0.75rem', color: '#94a3b8', marginBottom: '0.5rem' }}>Unrealized P/L</div>
                                <div style={{
                                    fontSize: '1.25rem',
                                    fontWeight: 'bold',
                                    color: (displayedStatus.total_profit_amount || 0) >= 0 ? '#10b981' : '#ef4444'
                                }}>
                                    {(displayedStatus.total_profit_amount || 0) >= 0 ? '+' : ''}
                                    ₩{Math.round(displayedStatus.total_profit_amount || 0).toLocaleString()}
                                </div>
                                <div style={{
                                    fontSize: '0.875rem',
                                    color: (displayedStatus.total_profit_amount || 0) >= 0 ? '#10b981' : '#ef4444',
                                    marginTop: '0.25rem'
                                }}>
                                    ({(displayedStatus.total_profit_rate || 0).toFixed(2)}%)
                                </div>
                            </div>
                        </div>
                    </div>
                    <div className="dashboard-layout">
                        {/* Right Content: Controls, Chart, Tables */}
                        <main className="dashboard-main">
                            <div className="strategy-config-container">
                                <Config
                                    config={strategyConfig}
                                    onUpdate={() => {
                                        fetchStatus();
                                        fetchStrategies();
                                    }}
                                    strategyId={selectedStrategyId}
                                    currentPrice={displayedStatus?.current_price}
                                />
                            </div>
                            {/* Control Panel */}
                            {/* Control Panel */}
                            <div style={{
                                padding: '1rem',
                                backgroundColor: 'rgba(30, 41, 59, 0.5)',
                                borderRadius: '0.5rem',
                                border: '1px solid #334155'
                            }}>
                                <div className="controls-container" style={{
                                    display: 'grid',
                                    gridTemplateColumns: 'repeat(5, 1fr)',
                                    gap: '0.75rem',
                                    alignItems: 'stretch'
                                }}>
                                    {/* 1. Start/Stop Bot */}
                                    {((isDevMode && canStartInDev) || (!isDevMode && !displayedStatus.is_running)) ? (
                                        <button className="btn btn-primary" onClick={handleStart} style={{
                                            padding: '0',
                                            height: '60px',
                                            fontSize: '0.95rem',
                                            width: '100%',
                                            display: 'flex',
                                            flexDirection: 'column',
                                            alignItems: 'center',
                                            justifyContent: 'center',
                                            gap: '0.25rem'
                                        }}>
                                            <span style={{ fontSize: '1.2rem' }}>▶</span>
                                            <span>{isDevMode ? 'Start Simulation' : 'Start Bot'}</span>
                                        </button>
                                    ) : (
                                        <button className="btn btn-danger" onClick={handleStop} style={{
                                            padding: '0',
                                            height: '60px',
                                            fontSize: '0.95rem',
                                            width: '100%',
                                            display: 'flex',
                                            flexDirection: 'column',
                                            alignItems: 'center',
                                            justifyContent: 'center',
                                            gap: '0.25rem'
                                        }}>
                                            <span style={{ fontSize: '1.2rem' }}>⏸</span>
                                            <span>{isDevMode ? (isDevSimulationActive ? 'Stop Simulation' : 'Stop Buying') : 'Stop Buying'}</span>
                                        </button>
                                    )}

                                    {/* 2. Hard Stop */}
                                    <button className="btn btn-danger" onClick={handleHardStop} style={{
                                        padding: '0',
                                        height: '60px',
                                        fontSize: '0.95rem',
                                        width: '100%',
                                        display: 'flex',
                                        flexDirection: 'column',
                                        alignItems: 'center',
                                        justifyContent: 'center',
                                        gap: '0.25rem',
                                        backgroundColor: '#b91c1c',
                                        borderColor: '#b91c1c',
                                        color: 'white'
                                    }}>
                                        <span style={{ fontSize: '1.2rem' }}>⛔</span>
                                        <span>Stop Trading</span>
                                    </button>

                                    {/* 3. Reset */}
                                    <button className="btn btn-secondary" onClick={handleReset} style={{
                                        padding: '0',
                                        height: '60px',
                                        fontSize: '0.95rem',
                                        width: '100%',
                                        display: 'flex',
                                        flexDirection: 'column',
                                        alignItems: 'center',
                                        justifyContent: 'center',
                                        gap: '0.25rem',
                                        backgroundColor: '#f1f5f9',
                                        color: '#334155',
                                        border: '1px solid #cbd5e1'
                                    }}>
                                        <span style={{ fontSize: '1.2rem' }}>🔄</span>
                                        <span>Reset</span>
                                    </button>
                                    {/* 4. Export CSV */}
                                    <button className="btn btn-secondary" onClick={handleExport} style={{
                                        padding: '0',
                                        height: '60px',
                                        fontSize: '0.95rem',
                                        width: '100%',
                                        display: 'flex',
                                        flexDirection: 'column',
                                        alignItems: 'center',
                                        justifyContent: 'center',
                                        gap: '0.25rem',
                                        backgroundColor: '#0f766e',
                                        borderColor: '#0f766e',
                                        color: 'white'
                                    }}>
                                        <span style={{ fontSize: '1.2rem' }}>⬇</span>
                                        <span>Export CSV</span>
                                    </button>

                                    {/* 5. Delete Strategy (Always Last) */}
                                    <button onClick={handleDeleteStrategy} style={{
                                        padding: '0',
                                        height: '60px',
                                        fontSize: '0.9rem',
                                        width: '100%',
                                        display: 'flex',
                                        flexDirection: 'column',
                                        alignItems: 'center',
                                        justifyContent: 'center',
                                        gap: '0.25rem',
                                        backgroundColor: 'transparent',
                                        border: '1px solid #ef4444',
                                        color: '#ef4444',
                                        borderRadius: '0.375rem',
                                        cursor: 'pointer'
                                    }}>
                                        <span style={{ fontSize: '1.2rem' }}>🗑</span>
                                        <span>Delete</span>
                                    </button>
                                </div>
                                {(portfolio?.mode === 'DEV' && (simMeta || liveError)) && (
                                    <div style={{
                                        marginTop: '0.75rem',
                                        padding: '0.75rem',
                                        borderRadius: '0.5rem',
                                        border: '1px solid #334155',
                                        backgroundColor: 'rgba(2, 132, 199, 0.08)',
                                        fontSize: '0.8rem',
                                        color: '#e2e8f0'
                                    }}>
                                        {simMeta && (
                                            <div style={{ display: 'flex', gap: '0.9rem', flexWrap: 'wrap' }}>
                                                <span>{`Mode: ${simMeta.mode}`}</span>
                                                <span>{`Trades: ${simMeta.trades}`}</span>
                                                <span style={{ color: (simMeta.realized_profit || 0) >= 0 ? '#10b981' : '#ef4444' }}>
                                                    {`P/L: ${(simMeta.realized_profit || 0) >= 0 ? '+' : ''}₩${Math.round(simMeta.realized_profit || 0).toLocaleString()}`}
                                                </span>
                                                <span>{`누적 매수: ₩${Math.round(simMeta.cumulative_buy_amount || 0).toLocaleString()}`}</span>
                                                <span>{`누적 매도: ₩${Math.round(simMeta.cumulative_sell_amount || 0).toLocaleString()}`}</span>
                                                <span>{`최대 투자금액: ₩${Math.round(simMeta.max_invested_amount || 0).toLocaleString()}`}</span>
                                                {simMeta.candles ? <span>{`Candles: ${simMeta.candles}`}</span> : null}
                                                {liveSessionState?.status ? <span>{`Live: ${liveSessionState.status}`}</span> : null}
                                            </div>
                                        )}
                                        {liveError && (
                                            <div style={{ marginTop: simMeta ? '0.35rem' : 0, fontSize: '0.76rem', color: '#f87171' }}>{liveError}</div>
                                        )}
                                    </div>
                                )}
                            </div>

                            {/* Price Chart */}
                            <div style={{ position: 'relative', zIndex: 1 }}>
                                <StrategyChart
                                    key={selectedStrategyId}
                                    ticker={displayedStatus?.ticker}
                                    splits={displayedStatus?.splits || []}
                                    config={resolvedConfig}
                                    tradeHistory={displayedStatus?.trade_history || []}
                                    trailingBuyState={{
                                        isWatching: displayedStatus.is_watching,
                                        watchLowestPrice: displayedStatus.watch_lowest_price,
                                        pendingBuyUnits: displayedStatus.pending_buy_units
                                    }}
                                    systemEvents={simOverlayState ? simSystemEvents : strategyEvents}
                                    nextBuyTargetPrice={getNextBuyTarget(displayedStatus)}
                                />
                            </div>

                            {/* Segment Summary (PRICE mode only) */}
                            {(resolvedConfig?.strategy_mode || 'PRICE') !== 'RSI' && strategyConfig?.price_segments?.length > 0 && (
                                <div className="card segment-status-card" style={{ marginBottom: '1rem' }}>
                                    <div className="card-header">
                                        <span className="card-title">Segment Status</span>
                                    </div>
                                    <div style={{ padding: '1rem', display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))', gap: '0.75rem' }}>
                                        {strategyConfig?.price_segments?.map((segment, index) => {
                                            const splits = displayedStatus?.splits || [];
                                            const segmentSplits = splits.filter(s =>
                                                s.status !== "SELL_FILLED" &&
                                                s.buy_price >= segment.min_price &&
                                                s.buy_price <= segment.max_price
                                            );
                                            const totalInvested = segmentSplits.reduce((sum, s) => sum + (s.buy_amount || 0), 0);

                                            return (
                                                <div key={index} style={{
                                                    padding: '0.75rem',
                                                    background: '#1e293b',
                                                    borderRadius: '0.5rem',
                                                    border: '1px solid #475569',
                                                    borderLeft: `4px solid hsl(${210 + index * 30}, 70%, 50%)`
                                                }}>
                                                    <div style={{ fontSize: '0.75rem', color: '#94a3b8', marginBottom: '0.25rem' }}>
                                                        Segment {index + 1}
                                                    </div>
                                                    <div style={{ fontSize: '0.85rem', color: '#e2e8f0', marginBottom: '0.5rem', fontWeight: 'bold' }}>
                                                        ₩{segment.min_price.toLocaleString()} - ₩{segment.max_price.toLocaleString()}
                                                    </div>
                                                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.5rem', fontSize: '0.75rem' }}>
                                                        <div>
                                                            <div style={{ color: '#94a3b8' }}>Active Splits</div>
                                                            <div style={{ fontWeight: 'bold' }}>
                                                                <span style={{ color: segmentSplits.length > segment.max_splits ? '#ef4444' : '#e2e8f0' }}>
                                                                    {segmentSplits.length}
                                                                </span>
                                                                <span style={{ color: '#e2e8f0' }}> / {segment.max_splits}</span>
                                                            </div>
                                                        </div>
                                                        <div>
                                                            <div style={{ color: '#94a3b8' }}>Invested Amount</div>
                                                            <div style={{ color: '#10b981', fontWeight: 'bold' }}>
                                                                ₩{totalInvested.toLocaleString()}
                                                            </div>
                                                        </div>
                                                    </div>
                                                </div>
                                            );
                                        })}
                                        {(() => {
                                            const allSegments = strategyConfig?.price_segments || [];
                                            const splits = displayedStatus?.splits || [];
                                            const outOfRangeSplits = splits.filter(s =>
                                                s.status !== "SELL_FILLED" &&
                                                !allSegments.some(seg => s.buy_price >= seg.min_price && s.buy_price <= seg.max_price)
                                            );
                                            const outOfRangeInvested = outOfRangeSplits.reduce((sum, s) => sum + (s.buy_amount || 0), 0);

                                            if (outOfRangeSplits.length === 0) return null;

                                            return (
                                                <div style={{
                                                    padding: '0.75rem',
                                                    background: '#1e293b',
                                                    borderRadius: '0.5rem',
                                                    border: '1px solid #ef4444',
                                                    borderLeft: `4px solid #ef4444`
                                                }}>
                                                    <div style={{ fontSize: '0.75rem', color: '#94a3b8', marginBottom: '0.25rem' }}>
                                                        Out of Range
                                                    </div>
                                                    <div style={{ fontSize: '0.85rem', color: '#ef4444', marginBottom: '0.5rem', fontWeight: 'bold' }}>
                                                        Positions outside defined segments
                                                    </div>
                                                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.5rem', fontSize: '0.75rem' }}>
                                                        <div>
                                                            <div style={{ color: '#94a3b8' }}>Count</div>
                                                            <div style={{ fontWeight: 'bold', color: '#e2e8f0' }}>
                                                                {outOfRangeSplits.length}
                                                            </div>
                                                        </div>
                                                        <div>
                                                            <div style={{ color: '#94a3b8' }}>Invested Amount</div>
                                                            <div style={{ color: '#ef4444', fontWeight: 'bold' }}>
                                                                ₩{outOfRangeInvested.toLocaleString()}
                                                            </div>
                                                        </div>
                                                    </div>
                                                </div>
                                            );
                                        })()}
                                    </div>
                                </div>
                            )}

                            <StrategyStatusPanel
                                strategyMode={resolvedConfig?.strategy_mode || 'PRICE'}
                                status={displayedStatus}
                                strategyConfig={strategyConfig}
                                onManualTargetClick={() => setIsManualTargetModalOpen(true)}
                                onPeekClick={() => setIsStatusPeekModalOpen(true)}
                            />

                            {/* Recent Trades Section */}
                            {displayedStatus?.trade_history && displayedStatus?.trade_history.length > 0 && (
                                <div className="trades-container">
                                    <div className="card">
                                        <div className="card-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                                            <span className="card-title">
                                                {`Recent Trades (${displayedStatus?.name})`}
                                            </span>
                                            <div className="pagination" style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
                                                <button
                                                    onClick={() => setTradesPage(p => Math.max(1, p - 1))}
                                                    disabled={tradesPage === 1}
                                                    style={{
                                                        padding: '0.25rem 0.6rem',
                                                        backgroundColor: tradesPage === 1 ? '#334155' : '#3b82f6',
                                                        color: 'white', border: 'none', borderRadius: '0.25rem', cursor: tradesPage === 1 ? 'default' : 'pointer'
                                                    }}
                                                >
                                                    &lt;
                                                </button>
                                                <span style={{ fontSize: '0.85rem', color: '#cbd5e1' }}>
                                                    Page {tradesPage} / {Math.ceil((displayedStatus?.trade_history || []).length / TRADES_PER_PAGE) || 1}
                                                </span>
                                                <button
                                                    onClick={() => setTradesPage(p => Math.min(Math.ceil((displayedStatus?.trade_history || []).length / TRADES_PER_PAGE), p + 1))}
                                                    disabled={tradesPage >= Math.ceil((displayedStatus?.trade_history || []).length / TRADES_PER_PAGE)}
                                                    style={{
                                                        padding: '0.25rem 0.6rem',
                                                        backgroundColor: tradesPage >= Math.ceil((displayedStatus?.trade_history || []).length / TRADES_PER_PAGE) ? '#334155' : '#3b82f6',
                                                        color: 'white', border: 'none', borderRadius: '0.25rem', cursor: tradesPage >= Math.ceil((displayedStatus?.trade_history || []).length / TRADES_PER_PAGE) ? 'default' : 'pointer'
                                                    }}
                                                >
                                                    &gt;
                                                </button>
                                            </div>
                                        </div>
                                        <div style={{ overflowX: 'auto' }}>
                                            <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left' }}>
                                                <thead>
                                                    <tr style={{ borderBottom: '2px solid #334155', color: '#94a3b8' }}>
                                                        <th style={{ padding: '1rem' }}>Buy Time</th>
                                                        <th style={{ padding: '1rem' }}>Sell Time</th>
                                                        <th style={{ padding: '1rem' }}>Split</th>
                                                        <th style={{ padding: '1rem' }}>Info</th>
                                                        <th style={{ padding: '1rem', textAlign: 'right' }}>Buy Amount</th>
                                                        <th style={{ padding: '1rem', textAlign: 'right' }}>Sell Amount</th>
                                                        <th style={{ padding: '1rem', textAlign: 'right' }}>Gross Profit</th>
                                                        <th style={{ padding: '1rem', textAlign: 'right' }}>Total Fee</th>
                                                        <th style={{ padding: '1rem', textAlign: 'right' }}>Net Profit</th>
                                                        <th style={{ padding: '1rem', textAlign: 'right' }}>Rate</th>
                                                    </tr>
                                                </thead>
                                                <tbody>
                                                    {(displayedStatus?.trade_history || [])
                                                        .slice((tradesPage - 1) * TRADES_PER_PAGE, tradesPage * TRADES_PER_PAGE)
                                                        .map((trade, index) => {
                                                            const buyAmount = trade.buy_amount || 0;
                                                            const sellAmount = trade.sell_amount || 0;
                                                            const grossProfit = trade.gross_profit || (sellAmount - buyAmount);
                                                            const totalFee = trade.total_fee || 0;
                                                            const netProfit = trade.net_profit || (grossProfit - totalFee);
                                                            const profitRate = trade.profit_rate || 0;

                                                            return (
                                                                <tr key={index} style={{ borderBottom: '1px solid #1e293b' }}>
                                                                    <td style={{ padding: '1rem', fontSize: '0.875rem', color: '#94a3b8' }}>
                                                                        {formatTime(trade.bought_at)}
                                                                    </td>
                                                                    <td style={{ padding: '1rem', fontSize: '0.875rem' }}>
                                                                        {formatTime(trade.timestamp)}
                                                                    </td>
                                                                    <td style={{ padding: '1rem', fontWeight: 'bold' }}>#{trade.split_id}</td>
                                                                    <td style={{ padding: '1rem' }}>
                                                                        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem', alignItems: 'flex-start' }}>
                                                                            {(() => {
                                                                                const segments = strategyConfig?.price_segments;
                                                                                if (segments && segments.length > 0 && trade.buy_price) {
                                                                                    const segmentIndex = segments.findIndex(seg =>
                                                                                        trade.buy_price >= seg.min_price && trade.buy_price <= seg.max_price
                                                                                    );
                                                                                    if (segmentIndex !== -1) {
                                                                                        const colors = [
                                                                                            '#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6',
                                                                                            '#ec4899', '#14b8a6', '#f97316', '#6366f1', '#84cc16'
                                                                                        ];
                                                                                        return (
                                                                                            <span style={{
                                                                                                fontSize: '0.7rem',
                                                                                                backgroundColor: colors[segmentIndex % colors.length],
                                                                                                color: 'white',
                                                                                                padding: '0.1rem 0.4rem',
                                                                                                borderRadius: '0.2rem'
                                                                                            }}>
                                                                                                Seg {segmentIndex + 1}
                                                                                            </span>
                                                                                        );
                                                                                    }
                                                                                }
                                                                                return null;
                                                                            })()}
                                                                            {trade.is_accumulated && (
                                                                                <span style={{
                                                                                    fontSize: '0.7rem',
                                                                                    backgroundColor: '#8b5cf6',
                                                                                    color: 'white',
                                                                                    padding: '0.1rem 0.4rem',
                                                                                    borderRadius: '0.2rem'
                                                                                }}>
                                                                                    Accumulated
                                                                                </span>
                                                                            )}
                                                                            {trade.buy_rsi !== undefined && trade.buy_rsi !== null && (
                                                                                <span style={{ fontSize: '0.75rem', color: '#cbd5e1' }}>
                                                                                    RSI: {trade.buy_rsi.toFixed(1)}
                                                                                </span>
                                                                            )}
                                                                            {!trade.is_accumulated && (trade.buy_rsi === undefined || trade.buy_rsi === null) && (
                                                                                (() => {
                                                                                    const segments = strategyConfig?.price_segments;
                                                                                    const hasSegmentBadge = segments && segments.length > 0 && trade.buy_price && segments.some(seg =>
                                                                                        trade.buy_price >= seg.min_price && trade.buy_price <= seg.max_price
                                                                                    );
                                                                                    return hasSegmentBadge ? null : <span style={{ fontSize: '0.75rem', color: '#64748b' }}>-</span>;
                                                                                })()
                                                                            )}
                                                                        </div>
                                                                    </td>
                                                                    <td style={{ padding: '1rem', textAlign: 'right' }}>
                                                                        <div style={{ fontSize: '0.875rem', color: '#94a3b8' }}>
                                                                            ₩{Math.round(buyAmount).toLocaleString()}
                                                                        </div>
                                                                        <div style={{ fontSize: '0.75rem', color: '#64748b' }}>
                                                                            @₩{trade.buy_price?.toLocaleString()}
                                                                        </div>
                                                                    </td>
                                                                    <td style={{ padding: '1rem', textAlign: 'right' }}>
                                                                        <div style={{ fontSize: '0.875rem', color: '#94a3b8' }}>
                                                                            ₩{Math.round(sellAmount).toLocaleString()}
                                                                        </div>
                                                                        <div style={{ fontSize: '0.75rem', color: '#64748b' }}>
                                                                            @₩{trade.sell_price?.toLocaleString()}
                                                                        </div>
                                                                    </td>
                                                                    <td style={{
                                                                        padding: '1rem',
                                                                        textAlign: 'right',
                                                                        color: grossProfit > 0 ? '#10b981' : grossProfit < 0 ? '#ef4444' : '#94a3b8',
                                                                        fontSize: '0.875rem'
                                                                    }}>
                                                                        {grossProfit > 0 ? '+' : ''}₩{Math.round(grossProfit).toLocaleString()}
                                                                    </td>
                                                                    <td style={{
                                                                        padding: '1rem',
                                                                        textAlign: 'right',
                                                                        color: '#ef4444',
                                                                        fontSize: '0.875rem'
                                                                    }}>
                                                                        -₩{Math.round(totalFee).toLocaleString()}
                                                                    </td>
                                                                    <td style={{
                                                                        padding: '1rem',
                                                                        textAlign: 'right',
                                                                        fontWeight: 'bold',
                                                                        fontSize: '0.95rem',
                                                                        color: netProfit > 0 ? '#10b981' : netProfit < 0 ? '#ef4444' : '#94a3b8'
                                                                    }}>
                                                                        {netProfit > 0 ? '+' : ''}₩{Math.round(netProfit).toLocaleString()}
                                                                    </td>
                                                                    <td style={{
                                                                        padding: '1rem',
                                                                        textAlign: 'right',
                                                                        color: profitRate > 0 ? '#10b981' : profitRate < 0 ? '#ef4444' : '#94a3b8',
                                                                        fontWeight: 'bold'
                                                                    }}>
                                                                        {profitRate.toFixed(2)}%
                                                                    </td>
                                                                </tr>
                                                            );
                                                        })}
                                                </tbody>
                                            </table>
                                        </div>
                                    </div>
                                </div>
                            )}

                            {/* System Event Log */}
                            <div className="event-log-container">
                                <EventLog
                                    strategyId={selectedStrategyId}
                                    apiBaseUrl={API_BASE_URL}
                                    status={displayedStatus?.status}
                                    simulationEvents={simOverlayState ? simEventsForLog : null}
                                />
                            </div>
                        </main>
                    </div>
                </>
            )}

        </div>
    );
};

export default Dashboard;
