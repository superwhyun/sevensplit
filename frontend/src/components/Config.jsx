import React, { useState } from 'react';
import axios from 'axios';
import Slider from 'rc-slider';
import 'rc-slider/assets/index.css';

const Config = ({ config, onUpdate, strategyId, currentPrice }) => {


    const [formData, setFormData] = useState(config || {});
    const [isEditing, setIsEditing] = useState(false);

    const lastStrategyIdRef = React.useRef(strategyId);
    const isEditingRef = React.useRef(isEditing);

    // Keep ref in sync
    React.useEffect(() => {
        isEditingRef.current = isEditing;
    }, [isEditing]);

    React.useEffect(() => {
        // Only update if not editing and we have a valid config object
        if (!isEditingRef.current || lastStrategyIdRef.current !== strategyId) {
            if (config && Object.keys(config).length > 0) {
                setFormData(config);
                lastStrategyIdRef.current = strategyId;
                setIsEditing(false);
            }
        }
    }, [config, strategyId]);

    // Helper to format number with commas
    const formatNumber = (num) => {
        if (num === null || num === undefined) return '';
        return num.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ",");
    };

    // Helper to parse number from comma string
    const parseNumber = (val) => {
        if (val === null || val === undefined) return 0;
        if (typeof val === 'number') return val;
        return parseFloat(val.toString().replace(/,/g, ''));
    };

    const handleChange = (e) => {
        setIsEditing(true);
        const { name, value, type, checked } = e.target;

        // Fields that should be treated as floats/ints directly
        const floatFields = [
            'fee_rate', 'buy_rate', 'sell_rate', 'tick_interval',
            'rsi_buy_max', 'rsi_buy_first_threshold', 'rsi_buy_next_threshold',
            'rsi_sell_min', 'rsi_sell_first_threshold', 'rsi_sell_next_threshold',
            'stop_loss',
            'trailing_buy_rebound_percent'
        ];

        const intFields = [
            'max_trades_per_day', 'rsi_period',
            'rsi_buy_first_amount', 'rsi_buy_next_amount',
            'rsi_sell_first_amount', 'rsi_sell_next_amount',
            'max_holdings'
        ];

        if (type === 'checkbox') {
            setFormData(prev => ({ ...prev, [name]: checked }));
        } else if (name === 'use_trailing_buy') {
            // Checkbox fallback if type check fails (unlikely in React but safe)
            setFormData(prev => ({ ...prev, [name]: checked }));
        } else if (floatFields.includes(name)) {
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
            await axios.post(`${API_BASE_URL}/strategies/config`, {
                strategy_id: strategyId,
                config: configData,
                budget: newBudget
            });
            setIsEditing(false);
            onUpdate();
            alert(`Configuration updated!`);
        } catch (error) {
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

            {/* Price Segments Editor - Visual Bar Split Mode */}
            <div style={{ marginTop: '1.5rem', marginBottom: '0.5rem', fontWeight: 'bold', color: '#60a5fa', borderTop: '1px solid #334155', paddingTop: '1rem' }}>
                Price Segments (Advanced Grid)
            </div>
            <div style={{ marginBottom: '1rem', background: '#0f172a', padding: '1rem', borderRadius: '0.5rem', border: '1px solid #334155' }}>
                {/* Segment Count Selector */}
                <div style={{ marginBottom: '1.5rem' }}>
                    <label style={{ fontSize: '0.9rem', color: '#e2e8f0', marginBottom: '0.5rem', display: 'block' }}>
                        Number of Segments: {formData.price_segments?.length || 0}
                    </label>
                    <div style={{ padding: '0 10px', marginBottom: '0.5rem' }}>
                        <Slider
                            min={0}
                            max={10}
                            value={formData.price_segments?.length || 0}
                            onChange={(count) => {
                                setIsEditing(true);
                                if (count === 0) {
                                    setFormData(prev => ({ ...prev, price_segments: [] }));
                                    return;
                                }

                                const minPrice = formData.min_price || 0;
                                const maxPrice = formData.max_price || 100000000;
                                const range = maxPrice - minPrice;
                                const segmentSize = range / count;

                                const newSegments = [];
                                for (let i = 0; i < count; i++) {
                                    newSegments.push({
                                        min_price: Math.round(minPrice + (segmentSize * i)),
                                        max_price: Math.round(minPrice + (segmentSize * (i + 1))),
                                        investment_per_split: 100000,
                                        max_splits: 5
                                    });
                                }
                                setFormData(prev => ({ ...prev, price_segments: newSegments }));
                            }}
                            trackStyle={{ backgroundColor: '#3b82f6' }}
                            handleStyle={{ borderColor: '#3b82f6', backgroundColor: '#3b82f6' }}
                            railStyle={{ backgroundColor: '#334155' }}
                        />
                    </div>
                    <div style={{ fontSize: '0.75rem', color: '#94a3b8', textAlign: 'center' }}>
                        Drag to set segment count (0 = disabled)
                    </div>
                </div>

                {formData.price_segments && formData.price_segments.length > 0 ? (
                    <>
                        {/* Visual Range Divider */}
                        <div style={{ marginBottom: '1.5rem', padding: '1rem', background: '#1e293b', borderRadius: '0.5rem', border: '1px solid #475569' }}>
                            <label style={{ fontSize: '0.8rem', color: '#94a3b8', marginBottom: '0.75rem', display: 'block' }}>
                                Price Range Dividers (Drag to adjust boundaries)
                            </label>
                            <div style={{ padding: '0 10px' }}>
                                <Slider
                                    range
                                    min={formData.min_price || 0}
                                    max={formData.max_price || 100000000}
                                    value={(() => {
                                        // Build array: [seg0.min, seg1.min, seg2.min, ..., lastSeg.max]
                                        const values = formData.price_segments.map(seg => seg.min_price);
                                        values.push(formData.price_segments[formData.price_segments.length - 1].max_price);
                                        return values;
                                    })()}
                                    onChange={(values) => {
                                        setIsEditing(true);

                                        if (!Array.isArray(values) || values.length < 2) {
                                            return;
                                        }

                                        // CRITICAL: Only proceed if values length matches expected length
                                        const expectedLength = formData.price_segments.length + 1;
                                        if (values.length !== expectedLength) {
                                            console.warn('[Segment Divider] Length mismatch, ignoring:', values.length, 'vs expected', expectedLength);
                                            return;
                                        }

                                        const newSegments = [];
                                        for (let i = 0; i < values.length - 1; i++) {
                                            const existingSegment = formData.price_segments[i] || {};
                                            newSegments.push({
                                                min_price: values[i],
                                                max_price: values[i + 1],
                                                investment_per_split: existingSegment.investment_per_split || 100000,
                                                max_splits: existingSegment.max_splits || 5
                                            });
                                        }
                                        setFormData(prev => ({ ...prev, price_segments: newSegments }));
                                    }}
                                    trackStyle={formData.price_segments.map((_, i) => ({ backgroundColor: `hsl(${210 + i * 30}, 70%, 50%)` }))}
                                    handleStyle={(() => {
                                        // Generate handle styles for all values (segments + 1)
                                        const handles = [];
                                        for (let i = 0; i <= formData.price_segments.length; i++) {
                                            handles.push({ borderColor: '#3b82f6', backgroundColor: '#3b82f6' });
                                        }
                                        return handles;
                                    })()}
                                    railStyle={{ backgroundColor: '#334155' }}
                                />
                            </div>
                            <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: '0.5rem', fontSize: '0.75rem', color: '#94a3b8' }}>
                                <span>₩{formatNumber(formData.min_price || 0)}</span>
                                <span>₩{formatNumber(formData.max_price || 100000000)}</span>
                            </div>
                        </div>

                        {/* Segment Details */}
                        <div style={{ marginBottom: '1rem' }}>
                            <div style={{ fontSize: '0.9rem', color: '#e2e8f0', marginBottom: '0.75rem', fontWeight: 'bold' }}>
                                Segment Settings
                            </div>
                            {formData.price_segments.map((segment, index) => (
                                <div key={index} style={{ marginBottom: '1rem', padding: '0.75rem', background: '#1e293b', borderRadius: '0.5rem', border: '1px solid #475569' }}>
                                    <div style={{ fontSize: '0.85rem', color: '#cbd5e1', marginBottom: '0.5rem', fontWeight: 'bold' }}>
                                        Segment {index + 1}: ₩{formatNumber(segment.min_price)} - ₩{formatNumber(segment.max_price)}
                                    </div>

                                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem' }}>
                                        <div>
                                            <label style={{ fontSize: '0.75rem', color: '#94a3b8', marginBottom: '0.25rem', display: 'block' }}>
                                                Invest per Split
                                            </label>
                                            <div style={{ marginBottom: '0.25rem', padding: '0 5px' }}>
                                                <Slider
                                                    min={10000}
                                                    max={500000}
                                                    step={10000}
                                                    value={segment.investment_per_split}
                                                    onChange={(val) => {
                                                        setIsEditing(true);
                                                        const newSegments = [...formData.price_segments];
                                                        newSegments[index] = { ...newSegments[index], investment_per_split: val };
                                                        setFormData(prev => ({ ...prev, price_segments: newSegments }));
                                                    }}
                                                    trackStyle={{ backgroundColor: '#10b981' }}
                                                    handleStyle={{ borderColor: '#10b981', backgroundColor: '#10b981' }}
                                                    railStyle={{ backgroundColor: '#334155' }}
                                                />
                                            </div>
                                            <input
                                                type="text"
                                                value={formatNumber(segment.investment_per_split)}
                                                onChange={(e) => {
                                                    setIsEditing(true);
                                                    const val = parseNumber(e.target.value);
                                                    const newSegments = [...formData.price_segments];
                                                    newSegments[index] = { ...newSegments[index], investment_per_split: val };
                                                    setFormData(prev => ({ ...prev, price_segments: newSegments }));
                                                }}
                                                style={{ width: '100%', padding: '0.25rem', background: '#0f172a', border: '1px solid #475569', color: 'white', borderRadius: '0.25rem', fontSize: '0.8rem' }}
                                            />
                                        </div>

                                        <div>
                                            <label style={{ fontSize: '0.75rem', color: '#94a3b8', marginBottom: '0.25rem', display: 'block' }}>
                                                Max Splits
                                            </label>
                                            <div style={{ marginBottom: '0.25rem', padding: '0 5px' }}>
                                                <Slider
                                                    min={1}
                                                    max={20}
                                                    value={segment.max_splits}
                                                    onChange={(val) => {
                                                        setIsEditing(true);
                                                        const newSegments = [...formData.price_segments];
                                                        newSegments[index] = { ...newSegments[index], max_splits: val };
                                                        setFormData(prev => ({ ...prev, price_segments: newSegments }));
                                                    }}
                                                    trackStyle={{ backgroundColor: '#8b5cf6' }}
                                                    handleStyle={{ borderColor: '#8b5cf6', backgroundColor: '#8b5cf6' }}
                                                    railStyle={{ backgroundColor: '#334155' }}
                                                />
                                            </div>
                                            <input
                                                type="number"
                                                value={segment.max_splits}
                                                onChange={(e) => {
                                                    setIsEditing(true);
                                                    const newSegments = [...formData.price_segments];
                                                    newSegments[index] = { ...newSegments[index], max_splits: parseInt(e.target.value) || 1 };
                                                    setFormData(prev => ({ ...prev, price_segments: newSegments }));
                                                }}
                                                style={{ width: '100%', padding: '0.25rem', background: '#0f172a', border: '1px solid #475569', color: 'white', borderRadius: '0.25rem', fontSize: '0.8rem' }}
                                            />
                                        </div>
                                    </div>
                                </div>
                            ))}
                        </div>
                    </>
                ) : (
                    <div style={{ color: '#94a3b8', fontSize: '0.9rem', textAlign: 'center', padding: '2rem' }}>
                        No segments defined. Using global config.<br/>
                        <span style={{ fontSize: '0.8rem' }}>Use slider above to create segments</span>
                    </div>
                )}
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

            {/* Trailing Buy Settings */}
            <div style={{ marginTop: '1.5rem', marginBottom: '0.5rem', fontWeight: 'bold', color: '#fbbf24', borderTop: '1px solid #334155', paddingTop: '1rem' }}>
                Trailing Buy (Low-Risk Entry)
            </div>

            <div style={{ display: 'flex', alignItems: 'center', marginBottom: '1rem' }}>
                <input
                    type="checkbox"
                    id="use_trailing_buy"
                    name="use_trailing_buy"
                    checked={formData.use_trailing_buy || false}
                    onChange={handleChange}
                    style={{ width: '1.25rem', height: '1.25rem', marginRight: '0.75rem', accentColor: '#fbbf24' }}
                />
                <label htmlFor="use_trailing_buy" style={{ margin: 0, cursor: 'pointer', color: formData.use_trailing_buy ? '#fbbf24' : '#94a3b8' }}>
                    Enable Trailing Buy (RSI Filter)
                </label>
            </div>

            {formData.use_trailing_buy && (
                <div className="input-group" style={{ paddingLeft: '2rem', borderLeft: '2px solid #fbbf24' }}>
                    <div className="input-group">
                        <label>Watch Mode RSI Threshold (Max)</label>
                        <input
                            type="number"
                            name="rsi_buy_max"
                            value={formData.rsi_buy_max ?? 30}
                            onChange={handleChange}
                            placeholder="30"
                        />
                        <small style={{ color: '#94a3b8', fontSize: '0.75rem', display: 'block', marginTop: '0.25rem' }}>
                            If RSI(5m) is below this value (default 30), the bot enters <strong>Watch Mode</strong> instead of buying immediately.
                        </small>
                    </div>

                    <label>Rebound Threshold (% to trigger buy)</label>
                    <input
                        type="number"
                        step="0.1"
                        name="trailing_buy_rebound_percent"
                        value={formData.trailing_buy_rebound_percent ?? 0.2}
                        onChange={handleChange}
                        placeholder="0.2"
                    />
                    <small style={{ color: '#94a3b8', fontSize: '0.75rem', display: 'block', marginTop: '0.25rem' }}>
                        Buys after price rebounds by <strong>{formData.trailing_buy_rebound_percent ?? 0.2}%</strong> from the lowest point during a drop.
                    </small>

                    <div style={{ display: 'flex', alignItems: 'center', marginTop: '1rem' }}>
                        <input
                            type="checkbox"
                            id="trailing_buy_batch"
                            name="trailing_buy_batch"
                            checked={formData.trailing_buy_batch !== false}
                            onChange={handleChange}
                            style={{ width: '1.25rem', height: '1.25rem', marginRight: '0.75rem', accentColor: '#fbbf24' }}
                        />
                        <label htmlFor="trailing_buy_batch" style={{ margin: 0, cursor: 'pointer', color: formData.trailing_buy_batch !== false ? '#fbbf24' : '#94a3b8' }}>
                            Allow Batch Buy (Accumulate Splits)
                        </label>
                    </div>
                    <small style={{ color: '#94a3b8', fontSize: '0.75rem', display: 'block', marginTop: '0.25rem' }}>
                        If enabled, buys multiple splits at once if price dropped significantly. If disabled, buys only one split.
                    </small>
                </div>
            )}
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
            <div style={{ fontSize: '0.8rem', color: '#94a3b8', marginBottom: '0.75rem' }}>
                * Executed once daily at 9:00 AM KST based on confirmed daily close.
            </div>
            <div className="input-group">
                <label>Max Buy RSI (Underground)</label>
                <input type="number" name="rsi_buy_max" value={formData.rsi_buy_max ?? 30} onChange={handleChange} />
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem' }}>
                <div className="input-group">
                    <label>Rebound Threshold (+)</label>
                    <input type="number" name="rsi_buy_first_threshold" value={formData.rsi_buy_first_threshold ?? 5} onChange={handleChange} />
                </div>
                <div className="input-group">
                    <label>Buy Amount (Splits)</label>
                    <input type="number" name="rsi_buy_first_amount" value={formData.rsi_buy_first_amount ?? 1} onChange={handleChange} />
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
                    <label>Drop Threshold (-)</label>
                    <input type="number" name="rsi_sell_first_threshold" value={formData.rsi_sell_first_threshold ?? 5} onChange={handleChange} />
                </div>
                <div className="input-group">
                    <label>Sell Amount (%)</label>
                    <input
                        type="number"
                        name="rsi_sell_first_amount"
                        value={formData.rsi_sell_first_amount ?? 100}
                        onChange={handleChange}
                        min="0"
                        max="100"
                        placeholder="100"
                    />
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

    // Early return only if formData is completely invalid
    if (!formData) {
        return (
            <div className="card">
                <div className="card-header">
                    <span className="card-title">Strategy Configuration</span>
                </div>
                <div style={{ padding: '1rem', color: '#94a3b8' }}>Loading configuration...</div>
            </div>
        );
    }

    return (
        <div className="card" >
            <div className="card-header">
                <span className="card-title">Strategy Configuration</span>
            </div>
            <form onSubmit={handleSubmit}>
                {/* Strategy Mode Toggle */}
                <div style={{ marginBottom: '1.5rem', display: 'flex', flexDirection: 'column', gap: '0.5rem', padding: '0.75rem', background: '#1e293b', borderRadius: '0.5rem' }}>
                    <label style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', cursor: 'pointer', color: (formData.strategy_mode || 'PRICE') === 'PRICE' ? '#60a5fa' : '#94a3b8' }}>
                        <input
                            type="radio"
                            name="strategy_mode"
                            value="PRICE"
                            checked={(formData.strategy_mode || 'PRICE') !== 'RSI'}
                            onChange={handleChange}
                        />
                        Classic (Price Grid)
                    </label>
                    <label style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', cursor: 'pointer', color: (formData.strategy_mode || 'PRICE') === 'RSI' ? '#60a5fa' : '#94a3b8' }}>
                        <input
                            type="radio"
                            name="strategy_mode"
                            value="RSI"
                            checked={(formData.strategy_mode || 'PRICE') === 'RSI'}
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
                {(formData.strategy_mode || 'PRICE') === 'RSI' ? renderRSIConfig() : renderClassicConfig()}

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
        </div >
    );
};

export default Config;
