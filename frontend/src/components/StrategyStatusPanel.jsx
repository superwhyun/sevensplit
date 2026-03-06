import React from 'react';

const SEGMENT_COLORS = [
    '#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6',
    '#ec4899', '#14b8a6', '#f97316', '#6366f1', '#84cc16',
];

function formatTime(t) {
    if (!t) return '-';
    const options = {
        year: 'numeric', month: '2-digit', day: '2-digit',
        hour: '2-digit', minute: '2-digit', second: '2-digit',
        hour12: false,
        timeZone: 'Asia/Seoul',
    };
    if (typeof t === 'number') return new Date(t * 1000).toLocaleString('ko-KR', options);
    let timeStr = t;
    if (!timeStr.endsWith('Z') && !timeStr.includes('+')) timeStr += 'Z';
    return new Date(timeStr).toLocaleString('ko-KR', options);
}

function getNextBuyTarget(status, strategyConfig) {
    if (!status) return null;
    const effectiveNext = Number(status.next_buy_target_price);
    if (Number.isFinite(effectiveNext) && effectiveNext > 0) return Math.floor(effectiveNext);
    const lastBuy = Number(status.last_buy_price);
    if (!Number.isFinite(lastBuy) || lastBuy <= 0) return null;
    const buyRate = Number(status.config?.buy_rate ?? strategyConfig?.buy_rate ?? 0.005);
    return Number.isFinite(buyRate) ? Math.floor(lastBuy * (1 - buyRate)) : null;
}

// ── Info cell: segment badge / accumulated / RSI ──────────────────────────────
function InfoCell({ split, priceSegments }) {
    const segments = priceSegments || [];
    const segmentIndex = segments.findIndex(
        seg => split.buy_price >= seg.min_price && split.buy_price <= seg.max_price
    );
    const hasSegmentBadge = segmentIndex !== -1;

    return (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
            {hasSegmentBadge && (
                <span style={{
                    fontSize: '0.7rem',
                    backgroundColor: SEGMENT_COLORS[segmentIndex % SEGMENT_COLORS.length],
                    color: 'white',
                    padding: '0.1rem 0.4rem',
                    borderRadius: '0.2rem',
                    width: 'fit-content',
                }}>
                    Seg {segmentIndex + 1}
                </span>
            )}
            {split.is_accumulated && (
                <span style={{
                    fontSize: '0.7rem',
                    backgroundColor: '#8b5cf6',
                    color: 'white',
                    padding: '0.1rem 0.4rem',
                    borderRadius: '0.2rem',
                    width: 'fit-content',
                }}>
                    Accumulated
                </span>
            )}
            {split.buy_rsi != null && (
                <span style={{ fontSize: '0.75rem', color: '#cbd5e1' }}>
                    RSI: {split.buy_rsi.toFixed(1)}
                </span>
            )}
            {!split.is_accumulated && split.buy_rsi == null && !hasSegmentBadge && (
                <span style={{ fontSize: '0.75rem', color: '#64748b' }}>-</span>
            )}
        </div>
    );
}

// ── PRICE strategy row ────────────────────────────────────────────────────────
function PriceRow({ split, currentPrice, sellRate, priceSegments }) {
    const isBought = split.status === 'BUY_FILLED' || split.status === 'PENDING_SELL';
    const profitRate = isBought ? ((currentPrice - split.buy_price) / split.buy_price * 100) : 0;
    const buyPriceRate = ((split.buy_price - currentPrice) / currentPrice * 100);
    const sellTargetPrice = split.target_sell_price > 0
        ? split.target_sell_price
        : split.buy_price * (1 + (sellRate || 0.005));
    const sellTargetRate = ((sellTargetPrice - currentPrice) / currentPrice * 100);

    return (
        <tr style={{ borderBottom: '1px solid #1e293b', backgroundColor: isBought ? 'rgba(16, 185, 129, 0.1)' : 'transparent' }}>
            <td style={{ padding: '1rem' }}>#{split.id}</td>
            <td style={{ padding: '1rem' }}>
                <span style={{
                    padding: '0.25rem 0.5rem', borderRadius: '0.25rem',
                    fontSize: '0.75rem', fontWeight: 'bold',
                    backgroundColor: isBought ? '#10b981' : '#64748b', color: 'white',
                }}>
                    {split.status}
                </span>
            </td>
            <td style={{ padding: '1rem', fontSize: '0.85rem', color: '#cbd5e1' }}>
                {formatTime(split.bought_at)}
            </td>
            <td style={{ padding: '1rem' }}>
                <InfoCell split={split} priceSegments={priceSegments} />
            </td>
            <td style={{ padding: '1rem' }}>
                <div>₩{split.buy_price.toLocaleString()}</div>
                <div style={{ fontSize: '0.75rem', color: buyPriceRate < 0 ? '#10b981' : buyPriceRate > 0 ? '#ef4444' : '#94a3b8' }}>
                    {buyPriceRate > 0 ? '+' : ''}{buyPriceRate.toFixed(2)}%
                </div>
            </td>
            <td style={{ padding: '1rem' }}>₩{Math.round(split.buy_amount || 0).toLocaleString()}</td>
            <td style={{ padding: '1rem' }}>
                <div>₩{sellTargetPrice.toLocaleString()}</div>
                <div style={{ fontSize: '0.75rem', color: sellTargetRate < 0 ? '#ef4444' : sellTargetRate > 0 ? '#10b981' : '#94a3b8' }}>
                    {sellTargetRate > 0 ? '+' : ''}{sellTargetRate.toFixed(2)}%
                </div>
            </td>
            <td style={{ padding: '1rem', color: profitRate > 0 ? '#10b981' : profitRate < 0 ? '#ef4444' : '#94a3b8' }}>
                {isBought ? `${profitRate.toFixed(2)}%` : '-'}
            </td>
        </tr>
    );
}

// ── RSI strategy row ──────────────────────────────────────────────────────────
function RSIRow({ split, currentPrice }) {
    const isBought = split.status === 'BUY_FILLED' || split.status === 'PENDING_SELL';
    const profitRate = isBought ? ((currentPrice - split.buy_price) / split.buy_price * 100) : 0;
    const buyPriceRate = ((split.buy_price - currentPrice) / currentPrice * 100);

    return (
        <tr style={{ borderBottom: '1px solid #1e293b', backgroundColor: isBought ? 'rgba(16, 185, 129, 0.1)' : 'transparent' }}>
            <td style={{ padding: '1rem' }}>#{split.id}</td>
            <td style={{ padding: '1rem' }}>
                <span style={{
                    padding: '0.25rem 0.5rem', borderRadius: '0.25rem',
                    fontSize: '0.75rem', fontWeight: 'bold',
                    backgroundColor: isBought ? '#10b981' : '#64748b', color: 'white',
                }}>
                    {split.status}
                </span>
            </td>
            <td style={{ padding: '1rem', fontSize: '0.85rem', color: '#cbd5e1' }}>
                {formatTime(split.bought_at)}
            </td>
            <td style={{ padding: '1rem' }}>
                <InfoCell split={split} priceSegments={[]} />
            </td>
            <td style={{ padding: '1rem' }}>
                <div>₩{split.buy_price.toLocaleString()}</div>
                <div style={{ fontSize: '0.75rem', color: buyPriceRate < 0 ? '#10b981' : buyPriceRate > 0 ? '#ef4444' : '#94a3b8' }}>
                    {buyPriceRate > 0 ? '+' : ''}{buyPriceRate.toFixed(2)}%
                </div>
            </td>
            <td style={{ padding: '1rem' }}>₩{Math.round(split.buy_amount || 0).toLocaleString()}</td>
            <td style={{ padding: '1rem', color: profitRate > 0 ? '#10b981' : profitRate < 0 ? '#ef4444' : '#94a3b8' }}>
                {isBought ? `${profitRate.toFixed(2)}%` : '-'}
            </td>
        </tr>
    );
}

// ── Main export ───────────────────────────────────────────────────────────────
export default function StrategyStatusPanel({
    strategyMode,
    status,
    strategyConfig,
    onManualTargetClick,
    onPeekClick,
}) {
    const isRSI = strategyMode === 'RSI';
    const splits = status?.splits || [];
    const currentPrice = status?.current_price;
    const nextBuyTarget = isRSI ? null : getNextBuyTarget(status, strategyConfig);
    const showNextBuyBadge = !isRSI && (status?.next_buy_target_price || status?.last_buy_price);
    const adaptiveEnabled = !isRSI && (status?.config?.use_adaptive_buy_control || strategyConfig?.use_adaptive_buy_control);
    const adaptivePressure = Number(status?.adaptive_reentry_pressure ?? 0);
    const adaptiveMultiplier = Number(status?.adaptive_effective_buy_multiplier ?? 1);
    const fastDropActive = !!status?.adaptive_fast_drop_active;

    return (
        <div className="grid-status-container">
            <div className="card" style={{ maxHeight: '600px', overflowY: 'auto', overflowX: 'auto' }}>
                <div className="card-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <span className="card-title">
                        {isRSI ? 'Position Status' : 'Grid Status'} ({splits.length} Lines)
                    </span>

                    {showNextBuyBadge && (
                        <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.5rem' }}>
                            <span
                                onClick={onManualTargetClick}
                                className="hover-bright"
                                style={{
                                    fontSize: '0.9rem', color: '#94a3b8', cursor: 'pointer',
                                    padding: '0.25rem 0.5rem', borderRadius: '0.25rem',
                                    backgroundColor: 'rgba(59, 130, 246, 0.1)',
                                    border: '1px dashed rgba(59, 130, 246, 0.3)',
                                    transition: 'all 0.2s',
                                }}
                            >
                                Next Buy Target:
                                <span style={{ color: '#3b82f6', fontWeight: 'bold' }}>
                                    {nextBuyTarget !== null ? ` ₩${nextBuyTarget.toLocaleString()}` : ' -'}
                                </span>
                                <span style={{ marginLeft: '0.5rem', fontSize: '0.8rem' }}>✏️</span>
                            </span>
                            <span
                                onClick={e => { e.stopPropagation(); onPeekClick(); }}
                                className="hover-bright"
                                style={{
                                    backgroundColor: '#3b82f6', color: 'white',
                                    padding: '0.2rem 0.5rem', borderRadius: '0.25rem',
                                    fontSize: '0.75rem', fontWeight: 'bold', cursor: 'pointer',
                                    display: 'flex', alignItems: 'center', gap: '0.25rem',
                                }}
                            >
                                🔍 PEEK
                            </span>
                        </span>
                    )}
                </div>

                {adaptiveEnabled && (
                    <div style={{
                        padding: '0 1rem 1rem',
                        display: 'flex',
                        gap: '0.75rem',
                        flexWrap: 'wrap',
                        fontSize: '0.8rem',
                    }}>
                        <span style={{
                            padding: '0.3rem 0.55rem',
                            borderRadius: '999px',
                            border: '1px solid #334155',
                            backgroundColor: '#0f172a',
                            color: '#cbd5e1',
                        }}>
                            Pressure: {adaptivePressure.toFixed(2)}
                        </span>
                        <span style={{
                            padding: '0.3rem 0.55rem',
                            borderRadius: '999px',
                            border: '1px solid #334155',
                            backgroundColor: 'rgba(56, 189, 248, 0.12)',
                            color: '#7dd3fc',
                        }}>
                            Buy Size: {adaptiveMultiplier.toFixed(2)}x
                        </span>
                        <span style={{
                            padding: '0.3rem 0.55rem',
                            borderRadius: '999px',
                            border: `1px solid ${fastDropActive ? '#f59e0b' : '#334155'}`,
                            backgroundColor: fastDropActive ? 'rgba(245, 158, 11, 0.12)' : '#0f172a',
                            color: fastDropActive ? '#fbbf24' : '#94a3b8',
                        }}>
                            Fast Drop Brake: {fastDropActive ? 'ON' : 'OFF'}
                        </span>
                    </div>
                )}

                <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left' }}>
                    <thead style={{ position: 'sticky', top: 0, backgroundColor: '#1e293b', zIndex: 10 }}>
                        <tr style={{ borderBottom: '1px solid #334155', color: '#94a3b8' }}>
                            <th style={{ padding: '1rem' }}>ID</th>
                            <th style={{ padding: '1rem' }}>Status</th>
                            <th style={{ padding: '1rem' }}>Buy Time</th>
                            <th style={{ padding: '1rem' }}>Info</th>
                            <th style={{ padding: '1rem' }}>Buy Price (vs Current)</th>
                            <th style={{ padding: '1rem' }}>Invested</th>
                            {!isRSI && <th style={{ padding: '1rem' }}>Sell Target (vs Current)</th>}
                            <th style={{ padding: '1rem' }}>Current P/L</th>
                        </tr>
                    </thead>
                    <tbody>
                        {splits.map(split =>
                            isRSI ? (
                                <RSIRow
                                    key={split.id}
                                    split={split}
                                    currentPrice={currentPrice}
                                />
                            ) : (
                                <PriceRow
                                    key={split.id}
                                    split={split}
                                    currentPrice={currentPrice}
                                    sellRate={status?.config?.sell_rate}
                                    priceSegments={strategyConfig?.price_segments}
                                />
                            )
                        )}
                    </tbody>
                </table>
            </div>
        </div>
    );
}
