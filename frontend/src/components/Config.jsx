import React, { useState } from 'react';
import axios from 'axios';

const Config = ({ config, onUpdate, strategyId, currentPrice, budget }) => {
    const [formData, setFormData] = useState(config);
    const [isEditing, setIsEditing] = useState(false);

    const lastStrategyIdRef = React.useRef(strategyId);

    // Update form data when config changes, BUT ONLY if not editing
    React.useEffect(() => {
        if (!isEditing || lastStrategyIdRef.current !== strategyId) {
            setFormData({ ...config, budget });
            lastStrategyIdRef.current = strategyId;
            setIsEditing(false);
        }
    }, [config, budget, isEditing, strategyId]);

    // Helper to format number with commas
    const formatNumber = (num) => {
        if (num === null || num === undefined) return '';
        return num.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ",");
    };

    // Helper to parse number from comma string
    const parseNumber = (str) => {
        if (!str) return 0;
        return parseFloat(str.replace(/,/g, ''));
    };

    const handleChange = (e) => {
        setIsEditing(true);
        const { name, value } = e.target;

        // Fields that should be treated as floats/ints directly
        const floatFields = [
            'fee_rate', 'buy_rate', 'sell_rate', 'tick_interval',
            'rsi_buy_max', 'rsi_buy_first_threshold', 'rsi_buy_next_threshold',
            'rsi_sell_min', 'rsi_sell_first_threshold', 'rsi_sell_next_threshold',
            'stop_loss'
        ];

        const intFields = [
            'max_trades_per_day', 'rsi_period',
            'rsi_buy_first_amount', 'rsi_buy_next_amount',
            'rsi_sell_first_amount', 'rsi_sell_next_amount',
            'max_holdings'
        ];

        if (floatFields.includes(name)) {
            setFormData(prev => ({ ...prev, [name]: parseFloat(value) }));
        } else if (intFields.includes(name)) {
            setFormData(prev => ({ ...prev, [name]: parseInt(value) }));
        } else if (name === 'strategy_mode' || name === 'rsi_timeframe' || name === 'rebuy_strategy') {
            setFormData(prev => ({ ...prev, [name]: value }));
        } else {
            // Comma separated number fields
            const numValue = parseNumber(value);
            if (!isNaN(numValue)) {
                setFormData(prev => ({ ...prev, [name]: numValue }));
            }
        }
    };

    const handleSubmit = async (e) => {
        e.preventDefault();
        try {
            const API_BASE_URL = window.location.port === '5173'
                ? `http://${window.location.hostname}:8000`
                : '';

            const { budget: newBudget, ...configData } = formData;
            await axios.post(`${API_BASE_URL}/config`, {
                strategy_id: strategyId,
                config: configData,
                budget: newBudget
            });
            setIsEditing(false);
            onUpdate();
            alert(`Configuration updated!`);
        } catch (error) {
            console.error('Error updating config:', error);
            alert('Failed to update config');
        }
    };

    const renderClassicConfig = () => (
        <>
            <div className="input-group">
                <label>Min Price (KRW)</label>
                <input
                    type="text"
                    name="min_price"
                    value={formatNumber(formData.min_price)}
                    onChange={handleChange}
                    placeholder="e.g. 50,000,000"
                />
            </div>
            <div className="input-group">
                <label>Max Price (KRW)</label>
                <input
                    type="text"
                    name="max_price"
                    value={formatNumber(formData.max_price)}
                    onChange={handleChange}
                    placeholder="e.g. 100,000,000"
                />
            </div>
            <div className="input-group">
                <label>Buy Rate (% price drop to buy)</label>
                <input
                    type="number"
                    step="0.001"
                    name="buy_rate"
                    value={formData.buy_rate ?? 0.005}
                    onChange={handleChange}
                />
                <small style={{ color: '#94a3b8', fontSize: '0.75rem' }}>
                    {((formData.buy_rate ?? 0.005) * 100).toFixed(2)}% drop triggers buy
                </small>
            </div>
            <div className="input-group">
                <label>Sell Rate (% profit to sell)</label>
                <input
                    type="number"
                    step="0.001"
                    name="sell_rate"
                    value={formData.sell_rate ?? 0.005}
                    onChange={handleChange}
                />
                <small style={{ color: '#94a3b8', fontSize: '0.75rem' }}>
                    {((formData.sell_rate ?? 0.005) * 100).toFixed(2)}% profit triggers sell
                </small>
            </div>
            <div className="input-group">
                <label>Rebuy Strategy</label>
                <select
                    name="rebuy_strategy"
                    value={formData.rebuy_strategy || 'reset_on_clear'}
                    onChange={handleChange}
                    className="form-select"
                    style={{
                        width: '100%',
                        padding: '0.5rem',
                        borderRadius: '0.375rem',
                        border: '1px solid #334155',
                        backgroundColor: '#1e293b',
                        color: '#e2e8f0'
                    }}
                >
                    <option value="reset_on_clear">Reset & Start at Current</option>
                    <option value="last_sell_price">Continue from Last Sell</option>
                    <option value="last_buy_price">Continue from Last Buy</option>
                </select>
            </div>
        </>
    );

    const renderRSIConfig = () => (
        <>
            {/* Indicator Settings */}
            <div style={{ marginTop: '1rem', marginBottom: '0.5rem', fontWeight: 'bold', color: '#60a5fa' }}>Indicator Settings</div>
            <div className="input-group">
                <label>Period</label>
                <select
                    name="rsi_period"
                    value={formData.rsi_period || 14}
                    onChange={handleChange}
                    style={{ width: '100%', padding: '0.5rem', borderRadius: '0.375rem', border: '1px solid #334155', backgroundColor: '#1e293b', color: '#e2e8f0' }}
                >
                    <option value={14}>14</option>
                    <option value={7}>7</option>
                    <option value={4}>4</option>
                </select>
            </div>

            {/* Buying Conditions */}
            <div style={{ marginTop: '1rem', marginBottom: '0.5rem', fontWeight: 'bold', color: '#4ade80' }}>Buying (Accumulation)</div>
            <div className="input-group">
                <label>Max Buy RSI (Underground)</label>
                <input type="number" name="rsi_buy_max" value={formData.rsi_buy_max ?? 30} onChange={handleChange} />
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem' }}>
                <div className="input-group">
                    <label>First Rebound (+)</label>
                    <input type="number" name="rsi_buy_first_threshold" value={formData.rsi_buy_first_threshold ?? 5} onChange={handleChange} />
                </div>
                <div className="input-group">
                    <label>Amount (Splits)</label>
                    <input type="number" name="rsi_buy_first_amount" value={formData.rsi_buy_first_amount ?? 1} onChange={handleChange} />
                </div>
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem' }}>
                <div className="input-group">
                    <label>Next Step (+)</label>
                    <input type="number" name="rsi_buy_next_threshold" value={formData.rsi_buy_next_threshold ?? 1} onChange={handleChange} />
                </div>
                <div className="input-group">
                    <label>Amount (Splits)</label>
                    <input type="number" name="rsi_buy_next_amount" value={formData.rsi_buy_next_amount ?? 1} onChange={handleChange} />
                </div>
            </div>

            {/* Selling Conditions */}
            <div style={{ marginTop: '1rem', marginBottom: '0.5rem', fontWeight: 'bold', color: '#f87171' }}>Selling (Distribution)</div>
            <div className="input-group">
                <label>Min Sell RSI (Overbought)</label>
                <input type="number" name="rsi_sell_min" value={formData.rsi_sell_min ?? 70} onChange={handleChange} />
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem' }}>
                <div className="input-group">
                    <label>First Drop (-)</label>
                    <input type="number" name="rsi_sell_first_threshold" value={formData.rsi_sell_first_threshold ?? 5} onChange={handleChange} />
                </div>
                <div className="input-group">
                    <label>Amount (Splits)</label>
                    <input type="number" name="rsi_sell_first_amount" value={formData.rsi_sell_first_amount ?? 1} onChange={handleChange} />
                </div>
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem' }}>
                <div className="input-group">
                    <label>Next Step (-)</label>
                    <input type="number" name="rsi_sell_next_threshold" value={formData.rsi_sell_next_threshold ?? 1} onChange={handleChange} />
                </div>
                <div className="input-group">
                    <label>Amount (Splits)</label>
                    <input type="number" name="rsi_sell_next_amount" value={formData.rsi_sell_next_amount ?? 1} onChange={handleChange} />
                </div>
            </div>

            {/* Risk Management */}
            <div style={{ marginTop: '1rem', marginBottom: '0.5rem', fontWeight: 'bold', color: '#fbbf24' }}>Risk Management</div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem' }}>
                <div className="input-group">
                    <label>Min Profit (%)</label>
                    <input type="number" step="0.1" name="sell_rate" value={((formData.sell_rate ?? 0.005) * 100).toFixed(1)}
                        onChange={(e) => handleChange({ target: { name: 'sell_rate', value: parseFloat(e.target.value) / 100 } })}
                    />
                </div>
                <div className="input-group">
                    <label>Stop Loss (%)</label>
                    <input type="number" step="0.1" name="stop_loss" value={formData.stop_loss ?? -10} onChange={handleChange} />
                </div>
            </div>
            <div className="input-group">
                <label>Max Holdings (Splits)</label>
                <input type="number" name="max_holdings" value={formData.max_holdings ?? 20} onChange={handleChange} />
            </div>
        </>
    );

    return (
        <div className="card">
            <div className="card-header">
                <span className="card-title">Strategy Configuration</span>
            </div>
            <form onSubmit={handleSubmit}>
                {/* Strategy Mode Toggle */}
                <div style={{ marginBottom: '1.5rem', display: 'flex', gap: '1rem', padding: '0.5rem', background: '#1e293b', borderRadius: '0.5rem' }}>
                    <label style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', cursor: 'pointer', color: formData.strategy_mode === 'PRICE' ? '#60a5fa' : '#94a3b8' }}>
                        <input
                            type="radio"
                            name="strategy_mode"
                            value="PRICE"
                            checked={formData.strategy_mode !== 'RSI'}
                            onChange={handleChange}
                        />
                        Classic (Price Grid)
                    </label>
                    <label style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', cursor: 'pointer', color: formData.strategy_mode === 'RSI' ? '#60a5fa' : '#94a3b8' }}>
                        <input
                            type="radio"
                            name="strategy_mode"
                            value="RSI"
                            checked={formData.strategy_mode === 'RSI'}
                            onChange={handleChange}
                        />
                        RSI Reversal
                    </label>
                </div>

                {/* Common Settings */}
                <div className="input-group">
                    <label>Total Budget (KRW)</label>
                    <input
                        type="text"
                        name="budget"
                        value={formatNumber(formData.budget)}
                        onChange={handleChange}
                        placeholder="e.g. 1,000,000"
                    />
                </div>
                <div className="input-group">
                    <label>Investment per Split (KRW)</label>
                    <input
                        type="text"
                        name="investment_per_split"
                        value={formatNumber(formData.investment_per_split)}
                        onChange={handleChange}
                        placeholder="e.g. 100,000"
                    />
                </div>

                {/* Conditional Settings */}
                {formData.strategy_mode === 'RSI' ? renderRSIConfig() : renderClassicConfig()}

                {/* Common Footer Settings */}
                <hr style={{ borderColor: '#334155', margin: '1.5rem 0' }} />

                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem' }}>
                    <div className="input-group">
                        <label>Tick Interval (s)</label>
                        <input
                            type="number"
                            step="0.1"
                            name="tick_interval"
                            value={formData.tick_interval ?? 1.0}
                            onChange={handleChange}
                        />
                    </div>
                    <div className="input-group">
                        <label>Max Trades/Day</label>
                        <input
                            type="number"
                            name="max_trades_per_day"
                            value={formData.max_trades_per_day ?? 100}
                            onChange={handleChange}
                        />
                    </div>
                    <div className="input-group" style={{ gridColumn: 'span 2' }}>
                        <label>Fee Rate</label>
                        <input
                            type="number"
                            step="0.0001"
                            name="fee_rate"
                            value={formData.fee_rate || 0.0005}
                            onChange={handleChange}
                            placeholder="0.0005"
                        />
                    </div>
                </div>

                <button type="submit" className="btn btn-primary" style={{ width: '100%', marginTop: '1rem' }}>
                    Save Configuration
                </button>
            </form>
        </div>
    );
};

export default Config;
