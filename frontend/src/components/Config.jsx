import React, { useState } from 'react';
import axios from 'axios';

const Config = ({ config, onUpdate, selectedTicker }) => {
    const [formData, setFormData] = useState(config);
    const [isEditing, setIsEditing] = useState(false);

    // Update form data when config prop changes, BUT ONLY if not editing
    React.useEffect(() => {
        if (!isEditing) {
            setFormData(config);
        }
    }, [config, isEditing]);

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

        // For fee_rate, keep as standard number input (small decimal)
        if (name === 'fee_rate') {
            setFormData(prev => ({
                ...prev,
                [name]: parseFloat(value)
            }));
            return;
        }

        // For other fields, parse comma string
        const numValue = parseNumber(value);
        if (!isNaN(numValue)) {
            setFormData(prev => ({
                ...prev,
                [name]: numValue
            }));
        }
    };

    const handleSubmit = async (e) => {
        e.preventDefault();
        try {
            await axios.post('http://127.0.0.1:8000/config', {
                ticker: selectedTicker,
                config: formData
            });
            setIsEditing(false); // Done editing
            onUpdate();
            alert(`Configuration updated for ${selectedTicker}!`);
        } catch (error) {
            console.error('Error updating config:', error);
            alert('Failed to update config');
        }
    };

    return (
        <div className="card">
            <div className="card-header">
                <span className="card-title">Strategy Configuration</span>
            </div>
            <form onSubmit={handleSubmit}>
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
                    <label>Max Price (KRW - Reference Only)</label>
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
                        value={formData.buy_rate || 0.01}
                        onChange={(e) => {
                            setIsEditing(true);
                            setFormData(prev => ({
                                ...prev,
                                buy_rate: parseFloat(e.target.value)
                            }));
                        }}
                        placeholder="e.g. 0.01 = 1%"
                    />
                    <small style={{ color: '#94a3b8', fontSize: '0.75rem' }}>
                        {((formData.buy_rate || 0.01) * 100).toFixed(2)}% price drop triggers next buy
                    </small>
                </div>

                <div className="input-group">
                    <label>Sell Rate (% profit to sell)</label>
                    <input
                        type="number"
                        step="0.001"
                        name="sell_rate"
                        value={formData.sell_rate || 0.01}
                        onChange={(e) => {
                            setIsEditing(true);
                            setFormData(prev => ({
                                ...prev,
                                sell_rate: parseFloat(e.target.value)
                            }));
                        }}
                        placeholder="e.g. 0.01 = 1%"
                    />
                    <small style={{ color: '#94a3b8', fontSize: '0.75rem' }}>
                        {((formData.sell_rate || 0.01) * 100).toFixed(2)}% profit triggers sell
                    </small>
                </div>

                <div className="input-group">
                    <label>Exchange Fee Rate</label>
                    <input
                        type="number"
                        step="0.0001"
                        name="fee_rate"
                        value={formData.fee_rate || 0.0005}
                        onChange={handleChange}
                        placeholder="e.g. 0.0005 = 0.05%"
                    />
                    <small style={{ color: '#94a3b8', fontSize: '0.75rem' }}>
                        {((formData.fee_rate || 0.0005) * 100).toFixed(3)}% per trade
                    </small>
                </div>

                <button type="submit" className="btn btn-primary" style={{ width: '100%' }}>
                    Save Configuration
                </button>
            </form>
        </div>
    );
};

export default Config;
