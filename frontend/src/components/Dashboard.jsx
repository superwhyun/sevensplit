import React, { useEffect, useState, useRef } from 'react';
import axios from 'axios';
import Config from './Config';

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

const Dashboard = () => {
    const [status, setStatus] = useState(null);
    const [portfolio, setPortfolio] = useState(null);
    const [strategies, setStrategies] = useState([]);
    const [loading, setLoading] = useState(true);
    const [selectedStrategyId, setSelectedStrategyId] = useState(null);
    const [isModalOpen, setIsModalOpen] = useState(false);

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
            if (response.data.length > 0 && !selectedStrategyId) {
                setSelectedStrategyId(response.data[0].id);
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

    // When strategy changes, fetch the new status
    useEffect(() => {
        if (selectedStrategyId) {
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
        if (!window.confirm(`Are you sure you want to reset this strategy? This will cancel all orders and delete all splits/trades.`)) {
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

    if (loading && !status) return <div style={{ padding: '2rem', color: 'white' }}>Loading...</div>;
    if (!status && strategies.length > 0) return <div style={{ padding: '2rem', color: 'white' }}>Loading Strategy...</div>;
    if (!portfolio) return <div style={{ padding: '2rem', color: 'white' }}>Loading Portfolio...</div>;

    return (
        <div className="dashboard-container" style={{ position: 'relative' }}>
            <AddStrategyModal isOpen={isModalOpen} onClose={() => setIsModalOpen(false)} onAdd={handleAddStrategy} />

            {/* Mode Indicator - Fixed Top Right */}
            <div
                style={{
                    position: 'fixed',
                    top: '1rem',
                    right: '1rem',
                    zIndex: 9999,
                    backgroundColor: portfolio.mode === "MOCK" ? '#f59e0b' : '#ef4444',
                    color: '#fff',
                    padding: '0.5rem 1rem',
                    borderRadius: '0.5rem',
                    fontSize: '0.875rem',
                    fontWeight: 'bold',
                    letterSpacing: '0.05em',
                    boxShadow: '0 4px 12px rgba(0,0,0,0.4)',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '0.5rem'
                }}
            >
                <div style={{
                    width: '8px',
                    height: '8px',
                    borderRadius: '50%',
                    backgroundColor: 'white',
                    animation: 'pulse 2s infinite'
                }} />
                {portfolio.mode === "MOCK" ? 'MOCK MODE' : 'REAL TRADING'}
            </div>

            {/* Global Portfolio Header */}
            <header className="header" style={{
                padding: '1.5rem',
                backgroundColor: 'rgba(15, 23, 42, 0.9)',
                borderBottom: '2px solid #334155'
            }}>
                <div style={{ marginBottom: '1rem' }}>
                    <h1 className="logo" style={{ margin: 0, fontSize: '1.75rem' }}>Seven Split Bot</h1>
                </div>

                {/* Overall Portfolio Stats */}
                <div style={{
                    display: 'grid',
                    gridTemplateColumns: 'repeat(6, 1fr)',
                    gap: '1rem',
                    padding: '1.25rem',
                    backgroundColor: 'rgba(255, 255, 255, 0.05)',
                    borderRadius: '0.5rem',
                    border: '1px solid #334155'
                }}>
                    <div style={{ textAlign: 'center', padding: '0.5rem' }}>
                        <div style={{ fontSize: '0.75rem', color: '#94a3b8', marginBottom: '0.5rem' }}>Available KRW</div>
                        <div style={{ fontSize: '1.25rem', color: '#3b82f6', fontWeight: 'bold' }}>
                            ₩{portfolio.balance_krw?.toLocaleString()}
                        </div>
                    </div>
                    {/* Dynamic Coin Stats (Top 3 by value) */}
                    {Object.entries(portfolio.coins)
                        .sort(([, a], [, b]) => b.value - a.value)
                        .slice(0, 3)
                        .map(([coin, data]) => (
                            <div key={coin} style={{ textAlign: 'center', padding: '0.5rem' }}>
                                <div style={{ fontSize: '0.75rem', color: '#94a3b8', marginBottom: '0.5rem' }}>Held {coin}</div>
                                <div style={{ fontSize: '1.25rem', fontWeight: 'bold', color: '#f8fafc' }}>
                                    ₩{Math.round(data.value || 0)?.toLocaleString()}
                                </div>
                                <div style={{ fontSize: '0.75rem', color: '#64748b', marginTop: '0.25rem' }}>
                                    {data.balance?.toFixed(4)} {coin}
                                </div>
                            </div>
                        ))}

                    <div style={{ textAlign: 'center', padding: '0.5rem' }}>
                        <div style={{ fontSize: '0.75rem', color: '#94a3b8', marginBottom: '0.5rem' }}>Total Value</div>
                        <div style={{ fontSize: '1.25rem', color: '#10b981', fontWeight: 'bold' }}>
                            ₩{Math.round(portfolio.total_value)?.toLocaleString()}
                        </div>
                    </div>
                    <div style={{ textAlign: 'center', padding: '0.5rem' }}>
                        <div style={{ fontSize: '0.75rem', color: '#94a3b8', marginBottom: '0.5rem' }}>Total Realized Profit</div>
                        <div style={{
                            fontSize: '1.25rem',
                            fontWeight: 'bold',
                            color: (portfolio.total_realized_profit || 0) >= 0 ? '#10b981' : '#ef4444'
                        }}>
                            {new Intl.NumberFormat('ko-KR', { style: 'currency', currency: 'KRW' }).format(portfolio.total_realized_profit || 0)}
                        </div>
                    </div>
                </div>
            </header>

            {/* Strategy Tabs */}
            <div className="tabs" style={{
                display: 'flex',
                gap: '0.5rem',
                padding: '1rem 1.5rem 0',
                borderBottom: '1px solid #334155',
                overflowX: 'auto'
            }}>
                {strategies.map(strategy => (
                    <button
                        key={strategy.id}
                        className={`tab-btn`}
                        onClick={() => {
                            setLoading(true);
                            setSelectedStrategyId(strategy.id);
                        }}
                        style={{
                            padding: '0.75rem 1.5rem',
                            borderRadius: '0.5rem 0.5rem 0 0',
                            border: 'none',
                            cursor: 'pointer',
                            fontWeight: '600',
                            fontSize: '0.9rem',
                            backgroundColor: selectedStrategyId === strategy.id ? '#1e293b' : 'transparent',
                            color: selectedStrategyId === strategy.id ? 'white' : '#94a3b8',
                            transition: 'all 0.2s',
                            borderBottom: selectedStrategyId === strategy.id ? '2px solid #3b82f6' : '2px solid transparent',
                            whiteSpace: 'nowrap'
                        }}
                    >
                        {strategy.name} <span style={{ fontSize: '0.8em', opacity: 0.7 }}>({strategy.ticker})</span>
                    </button>
                ))}
                <button
                    onClick={() => setIsModalOpen(true)}
                    style={{
                        padding: '0.75rem 1rem',
                        borderRadius: '0.5rem 0.5rem 0 0',
                        border: 'none',
                        cursor: 'pointer',
                        backgroundColor: 'rgba(59, 130, 246, 0.1)',
                        color: '#3b82f6',
                        fontWeight: 'bold'
                    }}
                >
                    + New Strategy
                </button>
            </div>

            {/* Strategy Content */}
            {status && (
                <>
                    {/* Strategy Stats */}
                    <div style={{
                        padding: '1.5rem',
                        backgroundColor: 'rgba(15, 23, 42, 0.7)',
                        borderBottom: '1px solid #334155'
                    }}>
                        <div style={{
                            display: 'grid',
                            gridTemplateColumns: 'repeat(4, 1fr)',
                            gap: '1rem'
                        }}>
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

                    {/* Control Panel */}
                    <div style={{
                        padding: '1.5rem',
                        backgroundColor: 'rgba(30, 41, 59, 0.5)',
                        borderBottom: '1px solid #334155'
                    }}>
                        <div style={{
                            display: 'flex',
                            justifyContent: 'space-between',
                            alignItems: 'center',
                            gap: '1.5rem'
                        }}>
                            {/* Left: Bot Controls */}
                            <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
                                {!status.is_running ? (
                                    <button className="btn btn-primary" onClick={handleStart} style={{
                                        padding: '0.65rem 1.75rem',
                                        fontSize: '0.95rem'
                                    }}>
                                        ▶ Start Bot
                                    </button>
                                ) : (
                                    <button className="btn btn-danger" onClick={handleStop} style={{
                                        padding: '0.65rem 1.75rem',
                                        fontSize: '0.95rem'
                                    }}>
                                        ⏸ Stop Bot
                                    </button>
                                )}
                                <button className="btn btn-secondary" onClick={handleReset} style={{
                                    padding: '0.65rem 1.75rem',
                                    fontSize: '0.95rem'
                                }}>
                                    🔄 Reset
                                </button>
                                <button className="btn btn-secondary" onClick={handleExport} style={{
                                    padding: '0.65rem 1.75rem',
                                    fontSize: '0.95rem',
                                    backgroundColor: '#0f766e',
                                    borderColor: '#0f766e'
                                }}>
                                    ⬇ Export CSV
                                </button>
                            </div>

                            {/* Right: Delete & Exchange Link */}
                            <div style={{ display: 'flex', gap: '1rem', alignItems: 'center' }}>
                                <button onClick={handleDeleteStrategy} style={{
                                    padding: '0.65rem 1rem',
                                    fontSize: '0.85rem',
                                    backgroundColor: 'transparent',
                                    border: '1px solid #ef4444',
                                    color: '#ef4444',
                                    borderRadius: '0.375rem',
                                    cursor: 'pointer'
                                }}>
                                    🗑 Delete Strategy
                                </button>

                                {portfolio.mode === "MOCK" && (
                                    <a
                                        href={`http://${window.location.hostname}:5001`}
                                        target="_blank"
                                        rel="noopener noreferrer"
                                        style={{
                                            padding: '0.6rem 1.25rem',
                                            backgroundColor: '#8b5cf6',
                                            color: 'white',
                                            borderRadius: '0.375rem',
                                            textDecoration: 'none',
                                            fontWeight: '600',
                                            fontSize: '0.9rem'
                                        }}
                                    >
                                        🏦 Exchange UI
                                    </a>
                                )}
                            </div>
                        </div>
                    </div>

                    <div style={{ display: 'grid', gridTemplateColumns: '300px 1fr', gap: '2rem' }}>
                        <div>
                            <Config
                                config={status.config}
                                onUpdate={fetchStatus}
                                strategyId={selectedStrategyId}
                                currentPrice={status.current_price}
                                budget={status.budget}
                            />
                            <div style={{ marginTop: '1rem', padding: '1rem', backgroundColor: '#1e293b', borderRadius: '0.5rem', border: '1px solid #334155' }}>
                                <div style={{ color: '#94a3b8', fontSize: '0.875rem', marginBottom: '0.5rem' }}>Budget</div>
                                <div style={{ fontSize: '1.25rem', fontWeight: 'bold', color: '#f8fafc' }}>
                                    ₩{status.budget?.toLocaleString()}
                                </div>
                            </div>
                        </div>

                        <div>
                            {/* Grid Status List */}
                            <div className="card" style={{ maxHeight: '600px', overflowY: 'auto' }}>
                                <div className="card-header">
                                    <span className="card-title">Grid Status ({status.splits.length} Lines)</span>
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
                                        {status.splits.map(split => {
                                            const isBought = split.status === "BUY_FILLED" || split.status === "PENDING_SELL";
                                            const profitRate = isBought ? ((status.current_price - split.buy_price) / split.buy_price * 100) : 0;

                                            // Calculate rate vs current price
                                            const buyPriceRate = ((split.buy_price - status.current_price) / status.current_price * 100);
                                            const sellTargetPrice = split.target_sell_price > 0
                                                ? split.target_sell_price
                                                : split.buy_price * (1 + status.config.sell_rate);
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
                        </div>
                    </div>

                    {/* Recent Trades Section */}
                    {
                        status.trade_history && status.trade_history.length > 0 && (
                            <div className="card" style={{ marginTop: '2rem' }}>
                                <div className="card-header">
                                    <span className="card-title">Recent Trades ({status.name})</span>
                                </div>
                                <div style={{ overflowX: 'auto' }}>
                                    <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left' }}>
                                        <thead>
                                            <tr style={{ borderBottom: '2px solid #334155', color: '#94a3b8' }}>
                                                <th style={{ padding: '1rem' }}>Time</th>
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
                                            {status.trade_history.map((trade, index) => {
                                                const buyAmount = trade.buy_amount || 0;
                                                const sellAmount = trade.sell_amount || 0;
                                                const grossProfit = trade.gross_profit || (sellAmount - buyAmount);
                                                const totalFee = trade.total_fee || 0;
                                                const netProfit = trade.net_profit || (grossProfit - totalFee);
                                                const profitRate = trade.profit_rate || 0;

                                                return (
                                                    <tr key={index} style={{ borderBottom: '1px solid #1e293b' }}>
                                                        <td style={{ padding: '1rem', fontSize: '0.875rem' }}>
                                                            {new Date(trade.timestamp).toLocaleString()}
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
                                                            fontWeight: 'bold',
                                                            fontSize: '0.95rem',
                                                            color: profitRate > 0 ? '#10b981' : profitRate < 0 ? '#ef4444' : '#94a3b8'
                                                        }}>
                                                            {profitRate > 0 ? '+' : ''}{profitRate.toFixed(2)}%
                                                        </td>
                                                    </tr>
                                                );
                                            })}
                                        </tbody>
                                    </table>
                                </div>
                            </div>
                        )
                    }
                </>
            )}
        </div>
    );
};

export default Dashboard;
