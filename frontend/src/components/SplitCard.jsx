import React from 'react';

const SplitCard = ({ split, currentPrice }) => {
    const isBought = split.status === 'BOUGHT';
    const profitRate = isBought && currentPrice
        ? ((currentPrice - split.buy_price) / split.buy_price) * 100
        : 0;

    return (
        <div className={`card ${isBought ? 'active' : ''}`}>
            <div className="card-header">
                <span className="card-title">Split #{split.id}</span>
                <span className={`status-badge ${isBought ? 'status-running' : 'status-stopped'}`}>
                    {split.status}
                </span>
            </div>

            <div className="stat-row">
                <span className="stat-label">Buy Price</span>
                <span className="stat-value">
                    {isBought ? `₩${split.buy_price.toLocaleString()}` : '-'}
                </span>
            </div>

            <div className="stat-row">
                <span className="stat-label">Volume</span>
                <span className="stat-value">
                    {isBought ? split.buy_volume.toFixed(8) : '-'} BTC
                </span>
            </div>

            <div className="stat-row">
                <span className="stat-label">Profit/Loss</span>
                <span className={`stat-value ${profitRate > 0 ? 'split-status-bought' : profitRate < 0 ? 'split-status-empty' : ''}`}>
                    {isBought ? `${profitRate.toFixed(2)}%` : '-'}
                </span>
            </div>
        </div>
    );
};

export default SplitCard;
