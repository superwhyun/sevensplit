import React, { useEffect, useState } from 'react';
import axios from 'axios';
import SplitCard from './SplitCard';
import Config from './Config';

const Dashboard = () => {
    const [status, setStatus] = useState(null);
    const [portfolio, setPortfolio] = useState(null);
    const [loading, setLoading] = useState(true);
    const [selectedTicker, setSelectedTicker] = useState("KRW-BTC");
    const [isPriceHeld, setIsPriceHeld] = useState(false);
    const [manualPrice, setManualPrice] = useState("");
    const [showApiModal, setShowApiModal] = useState(false);
    const [apiKeys, setApiKeys] = useState({ accessKey: '', secretKey: '' });
    const tickers = ["KRW-BTC", "KRW-ETH", "KRW-SOL"];

    const fetchStatus = async () => {
        try {
            const response = await axios.get(`http://127.0.0.1:8000/status?ticker=${selectedTicker}`);
            setStatus(response.data);
            setLoading(false);
        } catch (error) {
            console.error('Error fetching status:', error);
            setLoading(false);
        }
    };

    const fetchPortfolio = async () => {
        try {
            const response = await axios.get('http://127.0.0.1:8000/portfolio');
            setPortfolio(response.data);
        } catch (error) {
            console.error('Error fetching portfolio:', error);
        }
    };

    useEffect(() => {
        // Initial fetch
        fetchStatus();
        fetchPortfolio();

        // Check hold status on mount and ticker change
        const checkHoldStatus = async () => {
            try {
                const response = await axios.get(`http://127.0.0.1:8000/price-hold-status?ticker=${selectedTicker}`);
                setIsPriceHeld(response.data.is_held);
            } catch (error) {
                console.error('Error checking price hold status:', error);
            }
        };
        checkHoldStatus();

        const interval = setInterval(() => {
            fetchStatus();
            fetchPortfolio();
        }, 1000);
        return () => clearInterval(interval);
    }, [selectedTicker]); // Re-fetch when ticker changes

    const handleStart = async () => {
        try {
            await axios.post('http://127.0.0.1:8000/start', { ticker: selectedTicker });
            fetchStatus();
        } catch (error) {
            console.error('Error starting bot:', error);
        }
    };

    const handleStop = async () => {
        try {
            await axios.post('http://127.0.0.1:8000/stop', { ticker: selectedTicker });
            fetchStatus();
        } catch (error) {
            console.error('Error stopping bot:', error);
        }
    };

    const handleReset = async () => {
        if (!window.confirm('Are you sure you want to reset? This will delete all splits and restart.')) {
            return;
        }
        try {
            await axios.post('http://127.0.0.1:8000/reset');
            setIsPriceHeld(false);
            setManualPrice("");
            fetchStatus();
        } catch (error) {
            console.error('Error resetting bot:', error);
        }
    };

    const handlePriceOverride = async () => {
        if (!manualPrice || isNaN(parseFloat(manualPrice))) {
            alert('Please enter a valid price');
            return;
        }
        try {
            await axios.post('http://127.0.0.1:8000/override-price', {
                ticker: selectedTicker,
                price: parseFloat(manualPrice.replace(/,/g, ''))
            });
            fetchStatus();
        } catch (error) {
            console.error('Error overriding price:', error);
        }
    };

    const togglePriceHold = async () => {
        try {
            const newHoldState = !isPriceHeld;
            await axios.post('http://127.0.0.1:8000/toggle-price-hold', {
                ticker: selectedTicker,
                hold: newHoldState
            });
            setIsPriceHeld(newHoldState);
            if (newHoldState && status?.current_price) {
                setManualPrice(status.current_price.toString());
            }
        } catch (error) {
            console.error('Error toggling price hold:', error);
        }
    };

    const handleModeToggle = () => {
        if (portfolio.mode === "MOCK") {
            // Switch to REAL mode - show API key modal
            setShowApiModal(true);
        } else {
            // Switch back to MOCK mode
            handleSwitchToMock();
        }
    };

    const handleSwitchToMock = async () => {
        if (!window.confirm('Switch back to Mock mode? All real trading will be stopped.')) {
            return;
        }
        try {
            await axios.post('http://127.0.0.1:8000/switch-to-mock');
            fetchPortfolio();
            fetchStatus();
        } catch (error) {
            console.error('Error switching to mock mode:', error);
            alert('Failed to switch to Mock mode');
        }
    };

    const handleSubmitApiKeys = async (e) => {
        e.preventDefault();
        if (!apiKeys.accessKey || !apiKeys.secretKey) {
            alert('Please enter both Access Key and Secret Key');
            return;
        }
        try {
            const response = await axios.post('http://127.0.0.1:8000/set-api-keys', {
                access_key: apiKeys.accessKey,
                secret_key: apiKeys.secretKey
            });
            setShowApiModal(false);
            setApiKeys({ accessKey: '', secretKey: '' });
            fetchPortfolio();
            fetchStatus();
            alert(response.data.message);
        } catch (error) {
            console.error('Error setting API keys:', error);
            alert('Failed to switch to Real mode. Please check your API keys.');
        }
    };

    if (loading) return <div>Loading...</div>;
    if (!status || !portfolio) return <div>Error loading status</div>;

    return (
        <div className="dashboard-container">
            {/* Global Portfolio Header */}
            <header className="header" style={{
                padding: '1.5rem',
                backgroundColor: 'rgba(15, 23, 42, 0.9)',
                borderBottom: '2px solid #334155'
            }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
                    <h1 className="logo" style={{ margin: 0, fontSize: '1.75rem' }}>Seven Split Bot</h1>
                    <button
                        onClick={handleModeToggle}
                        style={{
                            backgroundColor: portfolio.mode === "MOCK" ? '#f59e0b' : '#10b981',
                            color: portfolio.mode === "MOCK" ? '#000' : '#fff',
                            padding: '0.5rem 1.25rem',
                            borderRadius: '0.5rem',
                            fontSize: '0.875rem',
                            fontWeight: 'bold',
                            letterSpacing: '0.05em',
                            border: 'none',
                            cursor: 'pointer',
                            transition: 'all 0.2s',
                            boxShadow: '0 2px 8px rgba(0,0,0,0.3)'
                        }}
                        onMouseEnter={(e) => e.target.style.opacity = '0.85'}
                        onMouseLeave={(e) => e.target.style.opacity = '1'}
                    >
                        {portfolio.mode === "MOCK" ? '🧪 MOCK MODE' : '🔴 REAL MODE'}
                    </button>
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
                    <div style={{ textAlign: 'center', padding: '0.5rem' }}>
                        <div style={{ fontSize: '0.75rem', color: '#94a3b8', marginBottom: '0.5rem' }}>Held BTC</div>
                        <div style={{ fontSize: '1.25rem', fontWeight: 'bold', color: '#f8fafc' }}>
                            ₩{Math.round(portfolio.coins.BTC?.value || 0)?.toLocaleString()}
                        </div>
                        <div style={{ fontSize: '0.75rem', color: '#64748b', marginTop: '0.25rem' }}>
                            {portfolio.coins.BTC?.balance?.toFixed(6)} BTC
                        </div>
                        <div style={{ fontSize: '0.7rem', color: '#475569' }}>
                            @₩{Math.round(portfolio.coins.BTC?.current_price || 0)?.toLocaleString()}
                        </div>
                    </div>
                    <div style={{ textAlign: 'center', padding: '0.5rem' }}>
                        <div style={{ fontSize: '0.75rem', color: '#94a3b8', marginBottom: '0.5rem' }}>Held ETH</div>
                        <div style={{ fontSize: '1.25rem', fontWeight: 'bold', color: '#f8fafc' }}>
                            ₩{Math.round(portfolio.coins.ETH?.value || 0)?.toLocaleString()}
                        </div>
                        <div style={{ fontSize: '0.75rem', color: '#64748b', marginTop: '0.25rem' }}>
                            {portfolio.coins.ETH?.balance?.toFixed(6)} ETH
                        </div>
                        <div style={{ fontSize: '0.7rem', color: '#475569' }}>
                            @₩{Math.round(portfolio.coins.ETH?.current_price || 0)?.toLocaleString()}
                        </div>
                    </div>
                    <div style={{ textAlign: 'center', padding: '0.5rem' }}>
                        <div style={{ fontSize: '0.75rem', color: '#94a3b8', marginBottom: '0.5rem' }}>Held SOL</div>
                        <div style={{ fontSize: '1.25rem', fontWeight: 'bold', color: '#f8fafc' }}>
                            ₩{Math.round(portfolio.coins.SOL?.value || 0)?.toLocaleString()}
                        </div>
                        <div style={{ fontSize: '0.75rem', color: '#64748b', marginTop: '0.25rem' }}>
                            {portfolio.coins.SOL?.balance?.toFixed(6)} SOL
                        </div>
                        <div style={{ fontSize: '0.7rem', color: '#475569' }}>
                            @₩{Math.round(portfolio.coins.SOL?.current_price || 0)?.toLocaleString()}
                        </div>
                    </div>
                    <div style={{ textAlign: 'center', padding: '0.5rem' }}>
                        <div style={{ fontSize: '0.75rem', color: '#94a3b8', marginBottom: '0.5rem' }}>Total Value</div>
                        <div style={{ fontSize: '1.25rem', color: '#10b981', fontWeight: 'bold' }}>
                            ₩{Math.round(portfolio.total_value)?.toLocaleString()}
                        </div>
                    </div>
                    <div style={{ textAlign: 'center', padding: '0.5rem' }}>
                        <div style={{ fontSize: '0.75rem', color: '#94a3b8', marginBottom: '0.5rem' }}>Total Profit</div>
                        <div style={{
                            fontSize: '1.25rem',
                            fontWeight: 'bold',
                            color: portfolio.total_profit_rate > 0 ? '#10b981' : portfolio.total_profit_rate < 0 ? '#ef4444' : '#f8fafc'
                        }}>
                            {portfolio.total_profit_rate?.toFixed(2)}%
                            <div style={{
                                fontSize: '0.875rem',
                                marginTop: '0.25rem',
                                color: '#94a3b8',
                                fontWeight: 'normal'
                            }}>
                                ₩{Math.round(portfolio.total_profit_amount)?.toLocaleString()}
                            </div>
                        </div>
                    </div>
                </div>
            </header>

            {/* Ticker Tabs */}
            <div className="tabs" style={{
                display: 'flex',
                gap: '0.5rem',
                padding: '1rem 1.5rem 0',
                borderBottom: '1px solid #334155'
            }}>
                {['KRW-BTC', 'KRW-ETH', 'KRW-SOL'].map(ticker => (
                    <button
                        key={ticker}
                        className={`tab-btn ${selectedTicker === ticker ? 'active' : ''}`}
                        onClick={() => {
                            setLoading(true);
                            setSelectedTicker(ticker);
                        }}
                        style={{
                            padding: '0.75rem 2rem',
                            borderRadius: '0.5rem 0.5rem 0 0',
                            border: 'none',
                            cursor: 'pointer',
                            fontWeight: '600',
                            fontSize: '1rem',
                            backgroundColor: selectedTicker === ticker ? '#1e293b' : 'transparent',
                            color: selectedTicker === ticker ? 'white' : '#94a3b8',
                            transition: 'all 0.2s',
                            borderBottom: selectedTicker === ticker ? '2px solid #3b82f6' : '2px solid transparent'
                        }}
                    >
                        {ticker.split('-')[1]}
                    </button>
                ))}
            </div>

            {/* Ticker-specific Stats */}
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

            {/* Ticker-specific Control Panel */}
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
                        {portfolio.mode === "MOCK" && (
                            <button className="btn btn-secondary" onClick={handleReset} style={{
                                padding: '0.65rem 1.75rem',
                                fontSize: '0.95rem'
                            }}>
                                🔄 Reset
                            </button>
                        )}
                    </div>

                    {/* Center: Current Price */}
                    <div style={{
                        padding: '0.85rem 2rem',
                        backgroundColor: 'rgba(59, 130, 246, 0.15)',
                        borderRadius: '0.5rem',
                        border: '2px solid rgba(59, 130, 246, 0.4)',
                        textAlign: 'center'
                    }}>
                        <div style={{ fontSize: '0.75rem', color: '#94a3b8', marginBottom: '0.35rem' }}>
                            {selectedTicker.split('-')[1]} Current Price
                        </div>
                        <div style={{ fontSize: '1.65rem', fontWeight: 'bold', color: '#3b82f6' }}>
                            ₩{status.current_price?.toLocaleString()}
                        </div>
                    </div>

                    {/* Right: Mock Price Control */}
                    {portfolio.mode === "MOCK" && (
                        <div style={{
                            display: 'flex',
                            alignItems: 'center',
                            gap: '0.75rem',
                            padding: '0.85rem 1.25rem',
                            backgroundColor: 'rgba(245, 158, 11, 0.1)',
                            borderRadius: '0.5rem',
                            border: '1px solid rgba(245, 158, 11, 0.35)',
                            flex: '1',
                            maxWidth: '650px'
                        }}>
                            <button
                                className={`btn ${isPriceHeld ? 'btn-danger' : 'btn-secondary'}`}
                                onClick={togglePriceHold}
                                style={{
                                    fontSize: '0.875rem',
                                    padding: '0.6rem 1.1rem',
                                    minWidth: '85px'
                                }}
                            >
                                {isPriceHeld ? '🔒 Held' : '▶️ Live'}
                            </button>

                            {isPriceHeld && (
                                <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
                                    <button
                                        onClick={() => {
                                            const currentPrice = parseFloat(manualPrice.replace(/,/g, '')) || status.current_price;
                                            const buyRate = status.config.buy_rate || 0.01;
                                            const newPrice = Math.round(currentPrice * (1 - buyRate));
                                            setManualPrice(newPrice.toString());
                                        }}
                                        style={{
                                            padding: '0.6rem 0.85rem',
                                            fontSize: '1.05rem',
                                            backgroundColor: '#ef4444',
                                            color: 'white',
                                            border: 'none',
                                            borderRadius: '0.375rem',
                                            cursor: 'pointer',
                                            fontWeight: 'bold'
                                        }}
                                        title="Decrease by buy rate"
                                    >
                                        ▼
                                    </button>
                                    <input
                                        type="text"
                                        value={manualPrice}
                                        onChange={(e) => setManualPrice(e.target.value)}
                                        placeholder="Enter price"
                                        style={{
                                            padding: '0.6rem 0.85rem',
                                            borderRadius: '0.375rem',
                                            border: '1px solid #475569',
                                            backgroundColor: '#1e293b',
                                            color: 'white',
                                            width: '170px',
                                            textAlign: 'center',
                                            fontSize: '0.95rem'
                                        }}
                                    />
                                    <button
                                        onClick={() => {
                                            const currentPrice = parseFloat(manualPrice.replace(/,/g, '')) || status.current_price;
                                            const sellRate = status.config.sell_rate || 0.01;
                                            const newPrice = Math.round(currentPrice * (1 + sellRate));
                                            setManualPrice(newPrice.toString());
                                        }}
                                        style={{
                                            padding: '0.6rem 0.85rem',
                                            fontSize: '1.05rem',
                                            backgroundColor: '#10b981',
                                            color: 'white',
                                            border: 'none',
                                            borderRadius: '0.375rem',
                                            cursor: 'pointer',
                                            fontWeight: 'bold'
                                        }}
                                        title="Increase by sell rate"
                                    >
                                        ▲
                                    </button>
                                    <button
                                        className="btn btn-primary"
                                        onClick={handlePriceOverride}
                                        style={{
                                            fontSize: '0.875rem',
                                            padding: '0.6rem 1.1rem',
                                            minWidth: '95px'
                                        }}
                                    >
                                        Set Price
                                    </button>
                                </div>
                            )}
                        </div>
                    )}
                </div>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '300px 1fr', gap: '2rem' }}>
                <div>
                    <Config config={status.config} onUpdate={fetchStatus} selectedTicker={selectedTicker} />
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
            {status.trade_history && status.trade_history.length > 0 && (
                <div className="card" style={{ marginTop: '2rem' }}>
                    <div className="card-header">
                        <span className="card-title">Recent Trades ({selectedTicker})</span>
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
                                    // Handle old trade history format (fallback)
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
            )}

            {/* API Keys Modal */}
            {showApiModal && (
                <div style={{
                    position: 'fixed',
                    top: 0,
                    left: 0,
                    right: 0,
                    bottom: 0,
                    backgroundColor: 'rgba(0, 0, 0, 0.75)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    zIndex: 1000
                }}>
                    <div style={{
                        backgroundColor: '#1e293b',
                        padding: '2rem',
                        borderRadius: '0.75rem',
                        width: '500px',
                        maxWidth: '90%',
                        border: '2px solid #334155',
                        boxShadow: '0 20px 50px rgba(0, 0, 0, 0.5)'
                    }}>
                        <h2 style={{ marginTop: 0, marginBottom: '1.5rem', color: '#f8fafc', fontSize: '1.5rem' }}>
                            Switch to Real Trading Mode
                        </h2>
                        <form onSubmit={handleSubmitApiKeys}>
                            <div style={{ marginBottom: '1.25rem' }}>
                                <label style={{ display: 'block', marginBottom: '0.5rem', color: '#94a3b8', fontSize: '0.875rem' }}>
                                    Upbit Access Key
                                </label>
                                <input
                                    type="text"
                                    value={apiKeys.accessKey}
                                    onChange={(e) => setApiKeys(prev => ({ ...prev, accessKey: e.target.value }))}
                                    placeholder="Enter your Upbit Access Key"
                                    style={{
                                        width: '100%',
                                        padding: '0.75rem',
                                        borderRadius: '0.375rem',
                                        border: '1px solid #475569',
                                        backgroundColor: '#0f172a',
                                        color: '#f8fafc',
                                        fontSize: '0.875rem'
                                    }}
                                />
                            </div>
                            <div style={{ marginBottom: '1.5rem' }}>
                                <label style={{ display: 'block', marginBottom: '0.5rem', color: '#94a3b8', fontSize: '0.875rem' }}>
                                    Upbit Secret Key
                                </label>
                                <input
                                    type="password"
                                    value={apiKeys.secretKey}
                                    onChange={(e) => setApiKeys(prev => ({ ...prev, secretKey: e.target.value }))}
                                    placeholder="Enter your Upbit Secret Key"
                                    style={{
                                        width: '100%',
                                        padding: '0.75rem',
                                        borderRadius: '0.375rem',
                                        border: '1px solid #475569',
                                        backgroundColor: '#0f172a',
                                        color: '#f8fafc',
                                        fontSize: '0.875rem'
                                    }}
                                />
                            </div>
                            <div style={{
                                padding: '1rem',
                                backgroundColor: 'rgba(239, 68, 68, 0.1)',
                                borderRadius: '0.5rem',
                                border: '1px solid rgba(239, 68, 68, 0.3)',
                                marginBottom: '1.5rem'
                            }}>
                                <p style={{ margin: 0, fontSize: '0.8rem', color: '#fca5a5', lineHeight: '1.5' }}>
                                    ⚠️ Warning: Real mode will execute actual trades with real money.
                                    Make sure you understand the risks before proceeding.
                                </p>
                            </div>
                            <div style={{ display: 'flex', gap: '1rem' }}>
                                <button
                                    type="button"
                                    onClick={() => {
                                        setShowApiModal(false);
                                        setApiKeys({ accessKey: '', secretKey: '' });
                                    }}
                                    className="btn btn-secondary"
                                    style={{ flex: 1, padding: '0.75rem' }}
                                >
                                    Cancel
                                </button>
                                <button
                                    type="submit"
                                    className="btn btn-primary"
                                    style={{ flex: 1, padding: '0.75rem', backgroundColor: '#10b981' }}
                                >
                                    Switch to Real Mode
                                </button>
                            </div>
                        </form>
                    </div>
                </div>
            )}
        </div>
    );
};

export default Dashboard;
