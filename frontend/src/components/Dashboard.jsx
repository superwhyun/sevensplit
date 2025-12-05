import React, { useEffect, useState, useRef } from 'react';
import axios from 'axios';
import StrategyChart from './StrategyChart';
import Config from './Config';
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
                rebuy_strategy: "reset_on_clear"
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

const Dashboard = () => {
    const [status, setStatus] = useState(null);
    const [portfolio, setPortfolio] = useState(null);
    const [strategies, setStrategies] = useState([]);
    const [loading, setLoading] = useState(true);
    const [selectedStrategyId, setSelectedStrategyId] = useState(null);
    const [isModalOpen, setIsModalOpen] = useState(false);
    const [isRenameModalOpen, setIsRenameModalOpen] = useState(false);
    const [isSimulating, setIsSimulating] = useState(false);
    const [simResult, setSimResult] = useState(null);

    const selectedStrategyIdRef = useRef(selectedStrategyId);

    // Keep ref in sync with state
    useEffect(() => {
        selectedStrategyIdRef.current = selectedStrategyId;
    }, [selectedStrategyId]);

    // If running on Vite dev server (port 5173), point to backend port 8000.
    // Otherwise (Docker/Production), use relative path (same origin).
    const API_BASE_URL = window.location.port === '5173'
        ? `http://${window.location.hostname}:8000`
        : '';

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
            }
        } catch (error) {
            console.error('Error fetching strategies:', error);
        }
    };

    const fetchStatus = async () => {
        if (!selectedStrategyIdRef.current) return;
        try {
            const currentId = selectedStrategyIdRef.current;
            const response = await axios.get(`${API_BASE_URL}/status?strategy_id=${currentId}`);
            setStatus(response.data);
            setLoading(false);
        } catch (error) {
            console.error('Error fetching status:', error);
            setLoading(false);
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
                console.log('Attempting WS connection to:', wsUrl);
                const ws = new WebSocket(wsUrl);
                wsRef.current = ws;

                ws.onopen = () => {
                    console.log('WS connected');
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
                            if (currentId && data.strategies[currentId]) {
                                setStatus(data.strategies[currentId]);
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
                    console.log('WS disconnected, retrying...');
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
        }
    }, [selectedStrategyId]);

    const handleStart = async () => {
        try {
            await axios.post(`${API_BASE_URL}/start`, { strategy_id: selectedStrategyId });
            fetchStatus();
        } catch (error) {
            console.error('Error starting bot:', error);
        }
    };

    const handleStop = async () => {
        try {
            await axios.post(`${API_BASE_URL}/stop`, { strategy_id: selectedStrategyId });
            fetchStatus();
        } catch (error) {
            console.error('Error stopping bot:', error);
        }
    };

    const handleReset = async () => {
        if (!window.confirm(`Are you sure you want to reset this strategy?\n\nThis will:\n- Cancel all active orders for this strategy\n- Clear active splits (positions)\n- DELETE all trade history\n\n(Your wallet balance will NOT be reset)`)) {
            return;
        }
        try {
            await axios.post(`${API_BASE_URL}/reset`, { strategy_id: selectedStrategyId });
            fetchStatus();
            fetchPortfolio();
        } catch (error) {
            console.error('Error resetting bot:', error);
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
        window.open(`${API_BASE_URL}/strategies/${selectedStrategyId}/export`, '_blank');
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

    const handleChartClick = async (time) => {
        if (!isSimulating) return;

        console.log("[Dashboard] handleChartClick received time:", time);

        // time is in seconds (UNIX timestamp)
        // Convert to ISO string for backend
        const date = new Date(time * 1000);
        const startTime = date.toISOString();
        console.log("[Dashboard] Converted to startTime:", startTime);

        try {
            // Show loading state or toast?
            // For now, let's just run it.
            const response = await axios.post(`${API_BASE_URL}/strategies/${selectedStrategyId}/simulate`, {
                start_time: startTime
            });

            if (response.data.debug_logs) {
                console.log("Simulation Logs:", response.data.debug_logs.join('\n'));
            }

            if (response.data.trades && response.data.trades.length === 0) {
                alert(`Simulation finished with 0 trades.\nCheck console for logs.\n\nLogs:\n${response.data.debug_logs ? response.data.debug_logs.join('\n') : 'No logs'}`);
            }

            setSimResult(response.data);
        } catch (error) {
            console.error("Simulation failed:", error);
            alert("Simulation failed. Check console for details.");
        }
    };

    if (loading && !status) return <div style={{ padding: '2rem', color: 'white' }}>Loading...</div>;
    if (!status && strategies.length > 0) return <div style={{ padding: '2rem', color: 'white' }}>Loading Strategy...</div>;
    if (!portfolio) return <div style={{ padding: '2rem', color: 'white' }}>Loading Portfolio...</div>;

    return (
        <div className="dashboard-container" style={{ position: 'relative' }}>
            {isSimulating && (
                <div style={{
                    position: 'fixed',
                    top: 0, left: 0, right: 0, bottom: 0,
                    backgroundColor: 'rgba(0,0,0,0.8)',
                    zIndex: 9999,
                    pointerEvents: 'auto' // Block clicks on background
                }}>
                    <div style={{
                        position: 'absolute',
                        top: '10%',
                        left: '50%',
                        transform: 'translateX(-50%)',
                        color: 'white',
                        fontSize: '1.5rem',
                        fontWeight: 'bold',
                        textAlign: 'center'
                    }}>
                        <div>🧪 Simulation Mode</div>
                        <div style={{ fontSize: '1rem', fontWeight: 'normal', marginTop: '0.5rem', color: '#cbd5e1' }}>
                            Click any point on the chart to start simulation from that date.
                        </div>
                        <button
                            onClick={() => setIsSimulating(false)}
                            style={{
                                marginTop: '1.5rem',
                                padding: '0.75rem 2rem',
                                fontSize: '1rem',
                                fontWeight: 'bold',
                                backgroundColor: '#ef4444',
                                color: 'white',
                                border: 'none',
                                borderRadius: '0.5rem',
                                cursor: 'pointer',
                                pointerEvents: 'auto'
                            }}
                        >
                            Cancel
                        </button>
                    </div>
                </div>
            )}

            {/* Simulation Result Banner */}
            {simResult && (
                <div style={{
                    backgroundColor: '#eab308',
                    color: '#000',
                    padding: '0.75rem',
                    textAlign: 'center',
                    fontWeight: 'bold',
                    display: 'flex',
                    justifyContent: 'center',
                    alignItems: 'center',
                    gap: '1rem'
                }}>
                    <span>🧪 VIEWING SIMULATION RESULTS</span>
                    <button
                        onClick={() => setSimResult(null)}
                        style={{
                            padding: '0.25rem 0.75rem',
                            backgroundColor: '#000',
                            color: '#eab308',
                            border: 'none',
                            borderRadius: '0.25rem',
                            cursor: 'pointer',
                            fontWeight: 'bold'
                        }}
                    >
                        Exit Simulation View
                    </button>
                </div>
            )}

            <AddStrategyModal isOpen={isModalOpen} onClose={() => setIsModalOpen(false)} onAdd={handleAddStrategy} />
            <RenameStrategyModal
                isOpen={isRenameModalOpen}
                onClose={() => setIsRenameModalOpen(false)}
                onRename={performRename}
                currentName={status?.name}
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
                        backgroundColor: portfolio.mode === "MOCK" ? '#f59e0b' : '#ef4444',
                    }}>
                        <div className="mode-dot" />
                        {portfolio.mode === "MOCK" ? 'MOCK MODE' : 'REAL TRADING'}
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

            {status && (
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
                                <div style={{ fontSize: '0.75rem', color: '#94a3b8', marginBottom: '0.5rem' }}>Current Price</div>
                                <div style={{ fontSize: '1.5rem', fontWeight: 'bold', color: '#3b82f6' }}>
                                    ₩{status.current_price?.toLocaleString()}
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
                                        {/* Hourly RSI */}
                                        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.1rem' }}>
                                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '0.8rem' }}>
                                                <span style={{ color: '#94a3b8' }}>RSI(14)/H</span>
                                                <span style={{ fontWeight: 'bold', color: (status.rsi >= 70) ? '#ef4444' : (status.rsi <= 30 && status.rsi != null) ? '#10b981' : '#f59e0b' }}>
                                                    {(status.rsi !== undefined && status.rsi !== null) ? Math.round(status.rsi) : '-'}
                                                </span>
                                            </div>
                                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '0.8rem' }}>
                                                <span style={{ color: '#94a3b8' }}>RSI(4)/H</span>
                                                <span style={{ fontWeight: 'bold', color: (status.rsi_short >= 70) ? '#ef4444' : (status.rsi_short <= 30 && status.rsi_short != null) ? '#10b981' : '#f59e0b' }}>
                                                    {(status.rsi_short !== undefined && status.rsi_short !== null) ? Math.round(status.rsi_short) : '-'}
                                                </span>
                                            </div>
                                        </div>

                                        {/* Daily RSI */}
                                        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.1rem', borderLeft: '1px solid rgba(255,255,255,0.1)', paddingLeft: '0.5rem' }}>
                                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '0.8rem' }}>
                                                <span style={{ color: '#94a3b8' }}>RSI(14)/D</span>
                                                <span style={{ fontWeight: 'bold', color: (status.rsi_daily >= 70) ? '#ef4444' : (status.rsi_daily <= 30 && status.rsi_daily != null) ? '#10b981' : '#f59e0b' }}>
                                                    {(status.rsi_daily !== undefined && status.rsi_daily !== null) ? Math.round(status.rsi_daily) : '-'}
                                                </span>
                                            </div>
                                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '0.8rem' }}>
                                                <span style={{ color: '#94a3b8' }}>RSI(4)/D</span>
                                                <span style={{ fontWeight: 'bold', color: (status.rsi_daily_short >= 70) ? '#ef4444' : (status.rsi_daily_short <= 30 && status.rsi_daily_short != null) ? '#10b981' : '#f59e0b' }}>
                                                    {(status.rsi_daily_short !== undefined && status.rsi_daily_short !== null) ? Math.round(status.rsi_daily_short) : '-'}
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
                                    {(status.total_coin_volume || 0).toFixed(8)}
                                </div>
                                <div style={{ fontSize: '0.7rem', color: '#94a3b8', marginTop: '0.25rem' }}>
                                    {status.ticker?.split('-')[1] || 'Coin'}
                                </div>
                            </div>
                            <div style={{
                                padding: '1rem',
                                backgroundColor: 'rgba(16, 185, 129, 0.1)',
                                borderRadius: '0.5rem',
                                border: '1px solid rgba(16, 185, 129, 0.3)'
                            }}>
                                <div style={{ fontSize: '0.75rem', color: '#94a3b8', marginBottom: '0.5rem' }}>Current Valuation</div>
                                <div style={{ fontSize: '1.25rem', fontWeight: 'bold', color: '#10b981' }}>
                                    ₩{Math.round(status.total_valuation || 0).toLocaleString()}
                                </div>
                                <div style={{ fontSize: '0.7rem', color: '#94a3b8', marginTop: '0.25rem' }}>
                                    Invested: ₩{Math.round(status.total_invested || 0).toLocaleString()}
                                </div>
                            </div>
                            <div style={{
                                padding: '1rem',
                                backgroundColor: (status.total_profit_amount || 0) >= 0
                                    ? 'rgba(16, 185, 129, 0.1)'
                                    : 'rgba(239, 68, 68, 0.1)',
                                borderRadius: '0.5rem',
                                border: (status.total_profit_amount || 0) >= 0
                                    ? '1px solid rgba(16, 185, 129, 0.3)'
                                    : '1px solid rgba(239, 68, 68, 0.3)'
                            }}>
                                <div style={{ fontSize: '0.75rem', color: '#94a3b8', marginBottom: '0.5rem' }}>Unrealized P/L</div>
                                <div style={{
                                    fontSize: '1.25rem',
                                    fontWeight: 'bold',
                                    color: (status.total_profit_amount || 0) >= 0 ? '#10b981' : '#ef4444'
                                }}>
                                    {(status.total_profit_amount || 0) >= 0 ? '+' : ''}₩{Math.round(status.total_profit_amount || 0).toLocaleString()}
                                </div>
                                <div style={{
                                    fontSize: '0.875rem',
                                    color: (status.total_profit_rate || 0) >= 0 ? '#10b981' : '#ef4444',
                                    marginTop: '0.25rem'
                                }}>
                                    ({(status.total_profit_rate || 0) >= 0 ? '+' : ''}{(status.total_profit_rate || 0).toFixed(2)}%)
                                </div>
                            </div>
                        </div>
                    </div>

                    {/* Main Content Grid */}
                    <div className="dashboard-layout">
                        {/* Left Sidebar: Config */}
                        <aside className="dashboard-sidebar">
                            <Config
                                config={status.config}
                                onUpdate={fetchStatus}
                                strategyId={selectedStrategyId}
                                currentPrice={status.current_price}
                                budget={status.budget}
                            />
                            <div style={{ padding: '1rem', backgroundColor: '#1e293b', borderRadius: '0.5rem', border: '1px solid #334155' }}>
                                <div style={{ color: '#94a3b8', fontSize: '0.875rem', marginBottom: '0.5rem' }}>Budget</div>
                                <div style={{ fontSize: '1.25rem', fontWeight: 'bold', color: '#f8fafc' }}>
                                    ₩{status.budget?.toLocaleString()}
                                </div>
                            </div>
                        </aside>

                        {/* Right Content: Controls, Chart, Tables */}
                        <main className="dashboard-main">
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
                                    gridTemplateColumns: portfolio.mode === "MOCK" ? 'repeat(6, 1fr)' : 'repeat(5, 1fr)',
                                    gap: '0.75rem',
                                    alignItems: 'stretch'
                                }}>
                                    {/* 1. Start/Stop Bot */}
                                    {!status.is_running ? (
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
                                            <span>Start Bot</span>
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
                                            <span>Stop Bot</span>
                                        </button>
                                    )}

                                    {/* 2. Reset */}
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

                                    {/* 3. Simulate */}
                                    <button className="btn btn-secondary" onClick={() => setIsSimulating(!isSimulating)} style={{
                                        padding: '0',
                                        height: '60px',
                                        fontSize: '0.95rem',
                                        width: '100%',
                                        display: 'flex',
                                        flexDirection: 'column',
                                        alignItems: 'center',
                                        justifyContent: 'center',
                                        gap: '0.25rem',
                                        backgroundColor: isSimulating ? '#eab308' : '#6366f1',
                                        borderColor: isSimulating ? '#eab308' : '#6366f1',
                                        color: 'white'
                                    }}>
                                        <span style={{ fontSize: '1.2rem' }}>{isSimulating ? '❌' : '🧪'}</span>
                                        <span>{isSimulating ? 'Exit Sim' : 'Simulate'}</span>
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

                                    {/* 5. Delete Strategy (Moved to end if not mock, or before exchange UI? Request said Delete at the END) */}
                                    {/* Wait, user said "Delete to the very end". So Exchange UI should be before Delete? */}
                                    {/* Let's check the image. The image shows: Stop | Reset | Simulate | Export | Delete | Exchange UI */}
                                    {/* BUT the text request says: "Delete를 제일 끝으로 보내." (Send Delete to the very end) */}
                                    {/* So the order should be: ... | Exchange UI | Delete */}

                                    {/* 5. Exchange UI (Mock Only) */}
                                    {portfolio.mode === "MOCK" && (
                                        <a
                                            href={`http://${window.location.hostname}:5001`}
                                            target="_blank"
                                            rel="noopener noreferrer"
                                            style={{
                                                padding: '0',
                                                height: '60px',
                                                fontSize: '0.9rem',
                                                width: '100%',
                                                display: 'flex',
                                                flexDirection: 'column',
                                                alignItems: 'center',
                                                justifyContent: 'center',
                                                gap: '0.25rem',
                                                backgroundColor: '#8b5cf6',
                                                color: 'white',
                                                borderRadius: '0.375rem',
                                                textDecoration: 'none',
                                                fontWeight: '600',
                                                border: '1px solid #7c3aed'
                                            }}
                                        >
                                            <span style={{ fontSize: '1.2rem' }}>🏦</span>
                                            <span>Exchange UI</span>
                                        </a>
                                    )}

                                    {/* 6. Delete Strategy (Always Last) */}
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
                            </div>

                            {/* Price Chart */}
                            <div style={{ position: 'relative', zIndex: isSimulating ? 10000 : 1 }}>
                                <StrategyChart
                                    ticker={status.ticker}
                                    splits={simResult ? simResult.splits : status.splits}
                                    config={simResult ? simResult.config : status.config}
                                    tradeHistory={simResult ? simResult.trades : status.trade_history}
                                    isSimulating={isSimulating}
                                    simResult={simResult}
                                    onSimulationComplete={(result) => {
                                        setSimResult(result);
                                        setIsSimulating(false);
                                    }}
                                    onChartClick={handleChartClick}
                                />
                            </div>

                            {/* Grid Status List */}
                            <div className="card" style={{ maxHeight: '600px', overflowY: 'auto', overflowX: 'auto' }}>
                                <div className="card-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                                    <span className="card-title">
                                        {simResult ? 'Simulated Grid Status' : 'Grid Status'} ({simResult ? simResult.splits.length : status.splits.length} Lines)
                                    </span>
                                    {!simResult && status.last_buy_price && (
                                        <span style={{ fontSize: '0.9rem', color: '#94a3b8' }}>
                                            Next Buy Target: <span style={{ color: '#3b82f6', fontWeight: 'bold' }}>
                                                ₩{Math.floor(status.last_buy_price * (1 - status.config.buy_rate)).toLocaleString()}
                                            </span>
                                        </span>
                                    )}
                                </div>
                                <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left' }}>
                                    <thead style={{ position: 'sticky', top: 0, backgroundColor: '#1e293b', zIndex: 10 }}>
                                        <tr style={{ borderBottom: '1px solid #334155', color: '#94a3b8' }}>
                                            <th style={{ padding: '1rem' }}>ID</th>
                                            <th style={{ padding: '1rem' }}>Status</th>
                                            <th style={{ padding: '1rem' }}>Buy Price (vs Current)</th>
                                            <th style={{ padding: '1rem' }}>Sell Target (vs Current)</th>
                                            <th style={{ padding: '1rem' }}>Current P/L</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {(simResult ? simResult.splits : status.splits).map(split => {
                                            const isBought = split.status === "BUY_FILLED" || split.status === "PENDING_SELL";
                                            // Use current price from status for calculation even in sim view for now, 
                                            // or use the last close price from sim? 
                                            // Sim result doesn't return "current_price" explicitly but we can use status.current_price for reference
                                            // or better, use the last candle close from chart? 
                                            // Let's use status.current_price for consistency with the view.

                                            const profitRate = isBought ? ((status.current_price - split.buy_price) / split.buy_price * 100) : 0;

                                            // Calculate rate vs current price
                                            const buyPriceRate = ((split.buy_price - status.current_price) / status.current_price * 100);
                                            const sellTargetPrice = split.target_sell_price > 0
                                                ? split.target_sell_price
                                                : split.buy_price * (1 + (simResult ? simResult.config.sell_rate : status.config.sell_rate));
                                            const sellTargetRate = ((sellTargetPrice - status.current_price) / status.current_price * 100);

                                            return (
                                                <tr key={split.id} style={{ borderBottom: '1px solid #1e293b', backgroundColor: isBought ? 'rgba(16, 185, 129, 0.1)' : 'transparent' }}>
                                                    <td style={{ padding: '1rem' }}>#{split.id}</td>
                                                    <td style={{ padding: '1rem' }}>
                                                        <span style={{
                                                            padding: '0.25rem 0.5rem',
                                                            borderRadius: '0.25rem',
                                                            fontSize: '0.75rem',
                                                            fontWeight: 'bold',
                                                            backgroundColor: isBought ? '#10b981' : '#64748b',
                                                            color: 'white'
                                                        }}>
                                                            {split.status}
                                                        </span>
                                                    </td>
                                                    <td style={{ padding: '1rem' }}>
                                                        <div>₩{split.buy_price.toLocaleString()}</div>
                                                        <div style={{
                                                            fontSize: '0.75rem',
                                                            color: buyPriceRate < 0 ? '#10b981' : buyPriceRate > 0 ? '#ef4444' : '#94a3b8'
                                                        }}>
                                                            {buyPriceRate > 0 ? '+' : ''}{buyPriceRate.toFixed(2)}%
                                                        </div>
                                                    </td>
                                                    <td style={{ padding: '1rem' }}>
                                                        <div>₩{sellTargetPrice.toLocaleString()}</div>
                                                        <div style={{
                                                            fontSize: '0.75rem',
                                                            color: sellTargetRate < 0 ? '#ef4444' : sellTargetRate > 0 ? '#10b981' : '#94a3b8'
                                                        }}>
                                                            {sellTargetRate > 0 ? '+' : ''}{sellTargetRate.toFixed(2)}%
                                                        </div>
                                                    </td>
                                                    <td style={{ padding: '1rem', color: profitRate > 0 ? '#10b981' : profitRate < 0 ? '#ef4444' : '#94a3b8' }}>
                                                        {isBought ? `${profitRate.toFixed(2)}%` : '-'}
                                                    </td>
                                                </tr>
                                            );
                                        })}
                                    </tbody>
                                </table>
                            </div>

                            {/* Recent Trades Section */}
                            {(simResult ? simResult.trades : status.trade_history) && (simResult ? simResult.trades : status.trade_history).length > 0 && (
                                <div className="card">
                                    <div className="card-header">
                                        <span className="card-title">
                                            {simResult ? 'Simulated Trades' : `Recent Trades (${status.name})`}
                                        </span>
                                    </div>
                                    <div style={{ overflowX: 'auto' }}>
                                        <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left' }}>
                                            <thead>
                                                <tr style={{ borderBottom: '2px solid #334155', color: '#94a3b8' }}>
                                                    <th style={{ padding: '1rem' }}>Buy Time</th>
                                                    <th style={{ padding: '1rem' }}>Sell Time</th>
                                                    <th style={{ padding: '1rem' }}>Split</th>
                                                    <th style={{ padding: '1rem', textAlign: 'right' }}>Buy Amount</th>
                                                    <th style={{ padding: '1rem', textAlign: 'right' }}>Sell Amount</th>
                                                    <th style={{ padding: '1rem', textAlign: 'right' }}>Gross Profit</th>
                                                    <th style={{ padding: '1rem', textAlign: 'right' }}>Total Fee</th>
                                                    <th style={{ padding: '1rem', textAlign: 'right' }}>Net Profit</th>
                                                    <th style={{ padding: '1rem', textAlign: 'right' }}>Rate</th>
                                                </tr>
                                            </thead>
                                            <tbody>
                                                {(simResult ? simResult.trades : status.trade_history).map((trade, index) => {
                                                    const buyAmount = trade.buy_amount || 0;
                                                    const sellAmount = trade.sell_amount || 0;
                                                    const grossProfit = trade.gross_profit || (sellAmount - buyAmount);
                                                    const totalFee = trade.total_fee || 0;
                                                    const netProfit = trade.net_profit || (grossProfit - totalFee);
                                                    const profitRate = trade.profit_rate || 0;

                                                    // Helper to format time (handle both ISO string and unix timestamp)
                                                    const formatTime = (t) => {
                                                        if (!t) return '-';
                                                        if (typeof t === 'number') return new Date(t * 1000).toLocaleString();
                                                        return new Date(t).toLocaleString();
                                                    };

                                                    return (
                                                        <tr key={index} style={{ borderBottom: '1px solid #1e293b' }}>
                                                            <td style={{ padding: '1rem', fontSize: '0.875rem', color: '#94a3b8' }}>
                                                                {formatTime(trade.bought_at)}
                                                            </td>
                                                            <td style={{ padding: '1rem', fontSize: '0.875rem' }}>
                                                                {formatTime(trade.timestamp)}
                                                            </td>
                                                            <td style={{ padding: '1rem', fontWeight: 'bold' }}>#{trade.split_id}</td>
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
                            )}
                        </main>
                    </div>
                </>
            )}
        </div>
    );
};

export default Dashboard;
