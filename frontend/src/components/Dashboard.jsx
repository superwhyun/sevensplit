import React, { useEffect, useState, useRef } from 'react';
import axios from 'axios';
import StrategyChart from './StrategyChart';
import Config from './Config';
import EventLog from './EventLog';
import StrategyStatusPanel from './StrategyStatusPanel';
import BotStatusStrip from './strategy/BotStatusStrip';
import './Dashboard.css';
import './strategy/strategy.css';

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
                <h2 style={{ marginTop: 0, color: '#f8fafc' }}>새 전략 만들기</h2>
                <form onSubmit={handleSubmit}>
                    <div style={{ marginBottom: '1rem' }}>
                        <label style={{ display: 'block', color: '#94a3b8', marginBottom: '0.5rem' }}>전략 이름</label>
                        <input
                            type="text"
                            value={name}
                            onChange={(e) => setName(e.target.value)}
                            placeholder="예: BTC 공격형"
                            required
                            style={{ width: '100%', padding: '0.5rem', borderRadius: '0.25rem', border: '1px solid #475569', backgroundColor: '#0f172a', color: 'white' }}
                        />
                    </div>
                    <div style={{ marginBottom: '1rem' }}>
                        <label style={{ display: 'block', color: '#94a3b8', marginBottom: '0.5rem' }}>코인</label>
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
                        <label style={{ display: 'block', color: '#94a3b8', marginBottom: '0.5rem' }}>예산 (KRW)</label>
                        <input
                            type="text"
                            value={budget}
                            onChange={(e) => setBudget(e.target.value.replace(/\D/g, '').replace(/\B(?=(\d{3})+(?!\d))/g, ","))}
                            required
                            style={{ width: '100%', padding: '0.5rem', borderRadius: '0.25rem', border: '1px solid #475569', backgroundColor: '#0f172a', color: 'white' }}
                        />
                    </div>
                    <div style={{ display: 'flex', gap: '1rem', justifyContent: 'flex-end' }}>
                        <button type="button" onClick={onClose} style={{ padding: '0.5rem 1rem', borderRadius: '0.25rem', border: 'none', backgroundColor: '#475569', color: 'white', cursor: 'pointer' }}>취소</button>
                        <button type="submit" style={{ padding: '0.5rem 1rem', borderRadius: '0.25rem', border: 'none', backgroundColor: '#3b82f6', color: 'white', cursor: 'pointer' }}>만들기</button>
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
                <h2 style={{ marginTop: 0, color: '#f8fafc' }}>다음 매수 목표가 직접 지정</h2>
                <p style={{ color: '#94a3b8', fontSize: '0.9rem', marginBottom: '1.5rem' }}>
                    봇이 그리드 계산 대신 이 가격에서 다음 분할을 삽니다.
                    (비워두면 다시 자동 계산으로 돌아갑니다)
                </p>
                <form onSubmit={handleSubmit}>
                    <div style={{ marginBottom: '1.5rem' }}>
                        <label style={{ display: 'block', color: '#94a3b8', marginBottom: '0.5rem' }}>다음 매수 목표가 (KRW)</label>
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
                        <button type="button" onClick={onClose} style={{ padding: '0.5rem 1rem', borderRadius: '0.25rem', border: 'none', backgroundColor: '#475569', color: 'white', cursor: 'pointer' }}>취소</button>
                        <button type="submit" style={{ padding: '0.5rem 1rem', borderRadius: '0.25rem', border: 'none', backgroundColor: '#3b82f6', color: 'white', cursor: 'pointer' }}>저장</button>
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
                <h2 style={{ marginTop: 0, color: '#f8fafc' }}>전략 이름 바꾸기</h2>
                <form onSubmit={handleSubmit}>
                    <div style={{ marginBottom: '1rem' }}>
                        <label style={{ display: 'block', color: '#94a3b8', marginBottom: '0.5rem' }}>새 이름</label>
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
                        <button type="button" onClick={onClose} style={{ padding: '0.5rem 1rem', borderRadius: '0.25rem', border: 'none', backgroundColor: '#475569', color: 'white', cursor: 'pointer' }}>취소</button>
                        <button type="submit" style={{ padding: '0.5rem 1rem', borderRadius: '0.25rem', border: 'none', backgroundColor: '#3b82f6', color: 'white', cursor: 'pointer' }}>저장</button>
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
                    <h3 style={{ margin: 0, color: '#f8fafc' }}>{ticker} 봇 상태 메모</h3>
                    <button onClick={onClose} style={{ background: 'none', border: 'none', color: '#94a3b8', fontSize: '1.5rem', cursor: 'pointer' }}>×</button>
                </div>
                <div style={{
                    backgroundColor: '#0f172a', padding: '1rem', borderRadius: '0.375rem',
                    border: '1px solid #334155', color: '#e2e8f0', minHeight: '80px',
                    fontFamily: 'monospace', fontSize: '0.9rem', whiteSpace: 'pre-wrap'
                }}>
                    {statusMsg || "아직 상태 정보가 없습니다."}
                </div>
                <div style={{ marginTop: '1.5rem', display: 'flex', justifyContent: 'flex-end' }}>
                    <button onClick={onClose} style={{ padding: '0.5rem 1.5rem', borderRadius: '0.25rem', border: 'none', backgroundColor: '#3b82f6', color: 'white', cursor: 'pointer' }}>닫기</button>
                </div>
            </div>
        </div>
    );
};

const DEV_REPLAY_OPTIONS_PRICE = [
    { key: '1d', label: '1일', desc: '1일 전 캔들부터 재생' },
    { key: '3d', label: '3일', desc: '3일 전 캔들부터 재생' },
    { key: '7d', label: '7일', desc: '7일 전 캔들부터 재생' },
];
const DEV_REPLAY_OPTIONS_RSI = [1, 3, 6, 9, 12, 15, 18, 21].map((m) => ({
    key: `${m}m`, label: `${m}개월`, desc: `약 ${m * 30}개 일봉 재생`,
}));

const devReplayOptionsFor = (isRSI) => (isRSI ? DEV_REPLAY_OPTIONS_RSI : DEV_REPLAY_OPTIONS_PRICE);

const describeDevStartOption = (opt) => {
    if (!opt || opt === 'live') return '지금부터 실시간';
    if (opt.endsWith('m')) return `${parseInt(opt, 10)}개월 리플레이 후 실시간`;
    return `${parseInt(opt, 10)}일 리플레이 후 실시간`;
};

const isValidDevStartOption = (opt, isRSI) =>
    opt === 'live' || devReplayOptionsFor(isRSI).some((o) => o.key === opt);

const StartBotModal = ({ isOpen, onClose, onStart, loading, strategyMode, lastOption }) => {
    if (!isOpen) return null;

    const isRSI = strategyMode === 'RSI';
    const replayOptions = devReplayOptionsFor(isRSI);
    const last = isValidDevStartOption(lastOption, isRSI) ? lastOption : null;

    return (
        <div className="modal-backdrop" role="dialog" aria-modal="true" aria-labelledby="start-modal-title">
            <div className="modal-card start-modal">
                <h2 id="start-modal-title" className="modal-title">모의 투자 어떻게 시작할까요?</h2>
                <p className="modal-lead">
                    {isRSI
                        ? 'RSI 전략은 일봉 기준이라 신호가 드뭅니다. 과거 구간을 먼저 돌려보면 신호 이력을 빨리 볼 수 있습니다.'
                        : '실시간으로 바로 돌리거나, 과거 구간을 먼저 재생해 결과를 본 뒤 실시간으로 이어갈 수 있습니다.'}
                </p>

                <button
                    type="button"
                    className={`start-option-card ${last === 'live' || !last ? 'recommended' : ''}`}
                    onClick={() => onStart('live')}
                    disabled={loading}
                >
                    <span className="start-option-head">
                        <span className="start-option-title">▶ 지금부터 실시간</span>
                        {(!last || last === 'live') && <span className="badge badge-accent">기본</span>}
                    </span>
                    <span className="start-option-desc">현재 시세부터 실시간으로 돌립니다. 결과는 시간이 지나야 쌓입니다.</span>
                </button>

                <div className="start-option-group">
                    <div className="start-option-group-title">과거 구간을 먼저 재생한 뒤 실시간으로 이어가기</div>
                    <div className="start-option-chips">
                        {replayOptions.map((opt) => (
                            <button
                                key={opt.key}
                                type="button"
                                className={`start-option-chip ${last === opt.key ? 'active' : ''}`}
                                onClick={() => onStart(opt.key)}
                                disabled={loading}
                                title={opt.desc}
                            >
                                {opt.label}
                                {last === opt.key && <small>최근</small>}
                            </button>
                        ))}
                    </div>
                    <div className="start-option-note">
                        재생이 끝날 때까지 몇 초에서 수십 초가 걸리고, 끝나면 자동으로 실시간 모드로 넘어갑니다.
                    </div>
                </div>

                <div className="modal-actions">
                    <button type="button" className="btn-ghost" onClick={onClose} disabled={loading}>닫기</button>
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

const toTimestampMs = (value) => {
    if (value === null || value === undefined) return null;
    if (typeof value === 'number') {
        return value > 1e12 ? value : value * 1000;
    }
    const normalized = String(value).includes('T') && !String(value).endsWith('Z') && !String(value).includes('+')
        ? `${value}Z`
        : String(value);
    const parsed = Date.parse(normalized);
    return Number.isNaN(parsed) ? null : parsed;
};

const calculateStrategyProfit = (strategyState) => {
    if (!strategyState || typeof strategyState !== 'object') {
        return { realized_profit: 0, realized_profit_24h: 0, unrealized_profit: 0, total_profit: 0 };
    }
    const kstOffsetMs = 9 * 60 * 60 * 1000;
    const kstNow = new Date(Date.now() + kstOffsetMs);
    const todayMidnightKST = Date.UTC(kstNow.getUTCFullYear(), kstNow.getUTCMonth(), kstNow.getUTCDate()) - kstOffsetMs;
    const realizedFromHistory = (strategyState.trade_history || []).reduce((sum, trade) => {
        return sum + Number(trade?.net_profit || 0);
    }, 0);
    const realized24hFromHistory = (strategyState.trade_history || []).reduce((sum, trade) => {
        const ts = toTimestampMs(trade?.timestamp);
        if (ts !== null && ts >= todayMidnightKST) {
            return sum + Number(trade?.net_profit || 0);
        }
        return sum;
    }, 0);
    const realized = Number(strategyState.realized_profit_total ?? realizedFromHistory);
    const realized24h = Number(strategyState.realized_profit_24h ?? realized24hFromHistory);
    const unrealized = Number(strategyState.total_profit_amount || 0);
    return {
        realized_profit: realized,
        realized_profit_24h: realized24h,
        unrealized_profit: unrealized,
        total_profit: realized,
    };
};

const DailyProfitChart = ({ data }) => {
    const [tooltip, setTooltip] = React.useState(null);
    if (!data || data.length === 0) return <div className="daily-profit-chart" />;

    const values = data.map(d => d.profit);
    const maxAbs = Math.max(...values.map(Math.abs), 1);
    const W = 400, H = 72, barGap = 2;
    const barW = Math.max(2, Math.floor((W - barGap * (data.length - 1)) / data.length));
    const midY = H / 2;

    return (
        <div className="daily-profit-chart" style={{ position: 'relative' }}>
            <svg width="100%" viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" style={{ display: 'block' }}>
                <line x1={0} y1={midY} x2={W} y2={midY} stroke="rgba(255,255,255,0.08)" strokeWidth="1" />
                {data.map((d, i) => {
                    const x = i * (barW + barGap);
                    const ratio = d.profit / maxAbs;
                    const barH = Math.max(1, Math.abs(ratio) * (midY - 4));
                    const y = d.profit >= 0 ? midY - barH : midY;
                    const color = d.profit >= 0 ? '#10b981' : '#ef4444';
                    const opacity = i === data.length - 1 ? 1 : 0.65;
                    return (
                        <rect
                            key={d.date}
                            x={x} y={y} width={barW} height={barH}
                            fill={color} opacity={opacity} rx="1"
                            onMouseEnter={(e) => setTooltip({ d, x: e.clientX, y: e.clientY })}
                            onMouseLeave={() => setTooltip(null)}
                            style={{ cursor: 'default' }}
                        />
                    );
                })}
            </svg>
            {tooltip && (
                <div style={{
                    position: 'fixed', left: tooltip.x + 10, top: tooltip.y - 36,
                    background: '#1e293b', border: '1px solid #334155',
                    borderRadius: '0.4rem', padding: '0.3rem 0.6rem',
                    fontSize: '0.72rem', color: '#f1f5f9', pointerEvents: 'none', zIndex: 9999,
                    whiteSpace: 'nowrap',
                }}>
                    <span style={{ color: '#94a3b8' }}>{tooltip.d.date} </span>
                    <span style={{ color: tooltip.d.profit >= 0 ? '#10b981' : '#ef4444', fontWeight: 600 }}>
                        {tooltip.d.profit >= 0 ? '+' : ''}₩{Math.round(tooltip.d.profit).toLocaleString()}
                    </span>
                </div>
            )}
        </div>
    );
};

const Dashboard = ({ onOpenSettings, onStartSetup, heldOnBootIds = [] }) => {
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
    const [activeSection, setActiveSection] = useState(() => {
        try { return localStorage.getItem('sevensplit.section') || 'overview'; } catch { return 'overview'; }
    });
    const [isMoreMenuOpen, setIsMoreMenuOpen] = useState(false);
    const selectSection = (key) => {
        setActiveSection(key);
        setIsMoreMenuOpen(false);
        try { localStorage.setItem('sevensplit.section', key); } catch { /* ignore */ }
    };
    const [simActionLoading, setSimActionLoading] = useState(false);
    const [lastDevStartOption, setLastDevStartOption] = useState(null);
    const devStartOptionKey = (strategyId) => `sevensplit.devStartOption:${strategyId}`;
    const [liveSessionId, setLiveSessionId] = useState(null);
    const [liveSessionState, setLiveSessionState] = useState(null);
    const [liveError, setLiveError] = useState('');
    const [simOverlayState, setSimOverlayState] = useState(null);
    const [simMeta, setSimMeta] = useState(null);
    const [simSystemEvents, setSimSystemEvents] = useState([]);
    const [strategyEvents, setStrategyEvents] = useState([]);
    const [strategyProfitById, setStrategyProfitById] = useState({});
    const [dailyProfits, setDailyProfits] = useState([]);
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
            setStrategyProfitById((prev) => ({
                ...prev,
                [currentId]: calculateStrategyProfit(response.data),
            }));
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

    const fetchDailyProfits = async () => {
        try {
            const response = await axios.get(`${API_BASE_URL}/daily-profits?days=30`);
            setDailyProfits(response.data || []);
        } catch (error) {
            console.error('Error fetching daily profits:', error);
        }
    };

    const wsRef = useRef(null);

    useEffect(() => {
        // Initial fetch
        fetchStrategies();
        fetchPortfolio();
        fetchDailyProfits();

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
                            const profitMap = {};
                            data.strategies.forEach((s) => {
                                profitMap[s.id] = calculateStrategyProfit(s);
                            });
                            setStrategyProfitById(profitMap);
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
                alert(`정지 실패: ${error.response?.data?.detail || error.message}`);
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
            alert(`정지 실패: ${error.response?.data?.detail || error.message}`);
        }
    };

    const handlePauseBuying = async () => {
        if (!liveSessionId) return;
        setSimActionLoading(true);
        try {
            await axios.post(`${API_BASE_URL}/simulations/live/${liveSessionId}/pause-buying`);
            await fetchLiveSessionStatus(liveSessionId);
        } catch (error) {
            alert(`매수 일시정지 실패: ${error.response?.data?.detail || error.message}`);
        } finally {
            setSimActionLoading(false);
        }
    };

    const handleResumeBuying = async () => {
        if (!liveSessionId) return;
        setSimActionLoading(true);
        try {
            await axios.post(`${API_BASE_URL}/simulations/live/${liveSessionId}/resume-buying`);
            await fetchLiveSessionStatus(liveSessionId);
        } catch (error) {
            alert(`매수 재개 실패: ${error.response?.data?.detail || error.message}`);
        } finally {
            setSimActionLoading(false);
        }
    };

    const handleHardStop = async () => {
        if (!window.confirm('전량 정지는 걸어둔 매수·매도 주문을 모두 취소합니다. 코인은 지갑에 남습니다. 계속할까요?')) {
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
                alert(`전량 정지 실패: ${error.response?.data?.detail || error.message}`);
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
            alert(`전량 정지 실패: ${error.response?.data?.detail || error.message}`);
        }
    };

    const handleReset = async () => {
        if (!window.confirm(`이 전략을 초기화할까요?\n\n- 이 전략의 모든 주문을 취소합니다\n- 포지션(분할)을 비웁니다\n- 거래 기록을 전부 삭제합니다\n\n(지갑 잔고는 그대로입니다)`)) {
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
            alert(`초기화 실패: ${error.response?.data?.detail || error.message}`);
        }
    };

    const handleAddStrategy = async (strategyData) => {
        try {
            const response = await axios.post(`${API_BASE_URL}/strategies`, strategyData);
            await fetchStrategies();
            setSelectedStrategyId(response.data.strategy_id);
        } catch (error) {
            console.error('Error creating strategy:', error);
            alert('전략을 만들지 못했습니다');
        }
    };

    const handleDeleteStrategy = async () => {
        if (!window.confirm(`이 전략을 삭제할까요? 되돌릴 수 없습니다.`)) {
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
            alert('전략을 삭제하지 못했습니다');
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
            alert('내보낼 거래가 없습니다.');
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
                alert("이름을 바꾸지 못했습니다");
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
            alert('목표가를 설정하지 못했습니다');
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
            const running = response.data?.status === 'running';
            setLiveSessionState(response.data);
            if (response.data?.final_state) {
                // A stopped session keeps its results on screen, but must never look "running":
                // that is what left the Stop button stuck and the Start button hidden.
                const paused = running && !!response.data?.buying_paused;
                setSimOverlayState({
                    ...response.data.final_state,
                    is_running: running,
                    status: !running ? 'Simulation (Stopped)' : paused ? 'Simulation (Paused)' : 'Simulation (Live)',
                });
                setSimMeta({
                    mode: response.data?.replay_days ? `replay+live-${response.data.replay_days}d` : 'live',
                    replay_days: response.data?.replay_days || 0,
                    status: response.data?.status,
                    trades: response.data?.trades ?? 0,
                    realized_profit: response.data?.realized_profit ?? 0,
                    cumulative_buy_amount: response.data?.cumulative_buy_amount ?? 0,
                    cumulative_sell_amount: response.data?.cumulative_sell_amount ?? 0,
                    max_invested_amount: response.data?.max_invested_amount ?? 0,
                    source: 'live'
                });
                setSimSystemEvents(response.data?.sim_events || []);
            }
            if (!running) {
                // Stop polling a finished session; the overlay above stays for viewing.
                setLiveSessionId(null);
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
            setLastDevStartOption(startOption);
            try { localStorage.setItem(devStartOptionKey(selectedStrategyId), startOption); } catch { /* ignore */ }
            setSimMeta({
                mode: replayDays > 0 ? `replay+live-${replayDays}d` : 'live',
                replay_days: replayDays,
                status: 'running',
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
    const selectedStrategyProfit = calculateStrategyProfit(displayedStatus);
    const aggregateProfit = Object.values(strategyProfitById).reduce((acc, profit) => {
        acc.realized_profit += Number(profit?.realized_profit || 0);
        acc.realized_profit_24h += Number(profit?.realized_profit_24h || 0);
        return acc;
    }, { realized_profit: 0, realized_profit_24h: 0 });
    const totalRealizedProfit = Number(portfolio?.total_realized_profit ?? aggregateProfit.realized_profit);
    const resolvedConfig = strategyConfig ?? displayedStatus?.config ?? {};
    const isDevMode = portfolio?.mode === 'DEV';
    const isDevSimulationActive = isDevMode && (liveSessionState?.status === 'running');
    // The engine-run paper bot is reported by the real strategy status; the simulation
    // overlay must not be able to keep this true after its session has stopped.
    const isDevBotRunning = isDevMode && !!status?.is_running;
    const canStartInDev = isDevMode && !isDevSimulationActive && !isDevBotRunning;
    const hasSimResults = isDevMode && !!simOverlayState && !isDevSimulationActive;
    const isRSIStrategy = (resolvedConfig?.strategy_mode || 'PRICE') === 'RSI';
    const quickDevStartOption = isValidDevStartOption(lastDevStartOption, isRSIStrategy) ? lastDevStartOption : null;
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
        if (!selectedStrategyId) { setLastDevStartOption(null); return; }
        try {
            setLastDevStartOption(localStorage.getItem(devStartOptionKey(selectedStrategyId)));
        } catch {
            setLastDevStartOption(null);
        }
    }, [selectedStrategyId]);

    useEffect(() => {
        if (!selectedStrategyId) return;
        const timer = setInterval(() => {
            if (!simOverlayState) {
                fetchStrategyEvents(selectedStrategyId);
            }
        }, 10000);
        return () => clearInterval(timer);
    }, [selectedStrategyId, simOverlayState]);

    if (!displayedStatus && strategies.length > 0) return <div style={{ padding: '2rem', color: 'white' }}>전략 불러오는 중…</div>;
    if (!portfolio) return <div style={{ padding: '2rem', color: 'white' }}>포트폴리오 불러오는 중…</div>;

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
                lastOption={lastDevStartOption}
            />

            {/* Global Portfolio Header */}
            <header className="header" style={{
                display: 'block',
                padding: '1.5rem',
                backgroundColor: 'rgba(15, 23, 42, 0.9)',
                borderBottom: '2px solid #334155'
            }}>
                {/* Overall Portfolio Stats - Compact Card */}
                <div className="portfolio-summary-card">
                    <div className="portfolio-main-stats">
                        <div className="total-value-section">
                            <span className="label">총 자산</span>
                            <span className="value">₩{Math.round(portfolio.total_value)?.toLocaleString()}</span>
                        </div>
                        <DailyProfitChart data={dailyProfits} />
                        <div className="profit-section">
                            <span className="label">실현 수익</span>
                            <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'baseline', justifyContent: 'flex-end' }}>
                                <span style={{ fontSize: '0.7rem', color: '#94a3b8', letterSpacing: '0.04em' }}>누적</span>
                                <span className="value" style={{ color: totalRealizedProfit >= 0 ? '#10b981' : '#ef4444' }}>
                                    {new Intl.NumberFormat('ko-KR', { style: 'currency', currency: 'KRW' }).format(totalRealizedProfit)}
                                </span>
                            </div>
                            <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'baseline', justifyContent: 'flex-end', marginTop: '0.2rem' }}>
                                <span style={{ fontSize: '0.7rem', color: '#94a3b8', letterSpacing: '0.04em' }}>오늘</span>
                                <span style={{ fontSize: '0.95rem', color: aggregateProfit.realized_profit_24h >= 0 ? '#10b981' : '#ef4444' }}>
                                    {(aggregateProfit.realized_profit_24h >= 0 ? '+' : '')}
                                    {new Intl.NumberFormat('ko-KR', { style: 'currency', currency: 'KRW' }).format(aggregateProfit.realized_profit_24h)}
                                </span>
                            </div>
                        </div>
                    </div>

                    <div className="assets-scroll-container">
                        {/* KRW Chip */}
                        <div className="asset-chip krw">
                            <span className="asset-name">🇰🇷 KRW</span>
                            <span className="asset-value">₩{Math.round(portfolio.balance_krw || 0).toLocaleString()}</span>
                            <span className="asset-amount">현금</span>
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
                {strategies.map(s => {
                    const tabProfit = strategyProfitById[s.id]?.realized_profit ?? 0;
                    return (
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
                                    title="전략 이름 바꾸기"
                                >
                                    ✎
                                </span>
                            )}
                        </div>
                        <span style={{ fontSize: '0.7rem', opacity: 0.8 }}>{s.ticker}</span>
                        <span style={{
                            fontSize: '0.7rem',
                            fontWeight: 600,
                            color: tabProfit >= 0 ? '#10b981' : '#ef4444',
                            opacity: selectedStrategyId === s.id ? 1 : 0.9
                        }}>
                            {(tabProfit >= 0 ? '+' : '')}₩{Math.round(tabProfit).toLocaleString()}
                        </span>
                    </button>
                    );
                })}
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
                    + 새 전략
                </button>
            </div>

            {heldOnBootIds.length > 0 && (
                <div className="held-banner" role="status">
                    <strong>재기동 후 정지 상태로 시작한 전략이 {heldOnBootIds.length}개 있습니다.</strong>
                    {' '}매도 체결은 계속 동기화되고 있습니다. 각 전략의 상태를 확인한 뒤 시작을 누르세요.
                    <span className="held-banner-ids">
                        {strategies.filter((s) => heldOnBootIds.includes(s.id)).map((s) => s.name).join(' · ')}
                    </span>
                </div>
            )}
            {strategies.length === 0 && (
                <section className="empty-state" aria-label="전략 없음">
                    <div className="empty-state-icon" aria-hidden="true">7</div>
                    <h2 className="empty-state-title">아직 전략이 없습니다</h2>
                    <p className="empty-state-text">
                        코인과 예산, 투자 성향만 고르면 3분 안에 첫 전략이 돌아갑니다.
                        {portfolio?.mode === 'REAL' ? ' 지금은 실거래 모드이니 소액으로 시작해 보세요.' : ' 모의 투자 모드라 실제 돈은 나가지 않습니다.'}
                    </p>
                    <div className="empty-state-actions">
                        <button type="button" className="btn-primary-lg" onClick={() => onStartSetup?.()}>
                            첫 전략 만들기
                        </button>
                        <button type="button" className="btn-ghost" onClick={() => setIsModalOpen(true)}>
                            직접 설정해서 만들기
                        </button>
                        <button type="button" className="btn-ghost" onClick={() => onOpenSettings?.()}>
                            설정 열기
                        </button>
                    </div>
                </section>
            )}

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
                                    <span>현재가</span>
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
                                <div style={{ fontSize: '0.75rem', color: '#94a3b8', marginBottom: '0.5rem' }}>보유 수량</div>
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
                                <div style={{ fontSize: '0.75rem', color: '#94a3b8', marginBottom: '0.5rem' }}>평가 금액</div>
                                <div style={{ fontSize: '1.25rem', fontWeight: 'bold', color: '#10b981' }}>
                                    ₩{Math.round(displayedStatus.total_valuation || 0).toLocaleString()}
                                </div>
                                <div style={{ fontSize: '0.7rem', color: '#94a3b8', marginTop: '0.25rem' }}>
                                    {`투자 금액: ₩${Math.round(displayedStatus.total_invested || 0).toLocaleString()}`}
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
                                <div style={{ fontSize: '0.75rem', color: '#94a3b8', marginBottom: '0.5rem' }}>평가 손익</div>
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
                            <div style={{
                                padding: '1rem',
                                backgroundColor: selectedStrategyProfit.realized_profit >= 0
                                    ? 'rgba(16, 185, 129, 0.1)'
                                    : 'rgba(239, 68, 68, 0.1)',
                                borderRadius: '0.5rem',
                                border: selectedStrategyProfit.realized_profit >= 0
                                    ? '1px solid rgba(16, 185, 129, 0.3)'
                                    : '1px solid rgba(239, 68, 68, 0.3)'
                            }}>
                                <div style={{ fontSize: '0.75rem', color: '#94a3b8', marginBottom: '0.5rem' }}>실현 수익</div>
                                <div style={{
                                    fontSize: '1.25rem',
                                    fontWeight: 'bold',
                                    color: selectedStrategyProfit.realized_profit >= 0 ? '#10b981' : '#ef4444'
                                }}>
                                    {selectedStrategyProfit.realized_profit >= 0 ? '+' : ''}
                                    ₩{Math.round(selectedStrategyProfit.realized_profit).toLocaleString()}
                                </div>
                                <div style={{
                                    fontSize: '0.75rem',
                                    color: selectedStrategyProfit.realized_profit_24h >= 0 ? '#10b981' : '#ef4444',
                                    marginTop: '0.25rem'
                                }}>
                                    오늘: {(selectedStrategyProfit.realized_profit_24h >= 0 ? '+' : '')}
                                    ₩{Math.round(selectedStrategyProfit.realized_profit_24h).toLocaleString()}
                                </div>
                            </div>
                        </div>
                    </div>
                    <div className="dashboard-layout">
                        <main className="dashboard-main">
                            <nav className="section-tabs" aria-label="전략 화면">
                                {[
                                    { key: 'overview', label: '현황' },
                                    { key: 'settings', label: '전략 설정' },
                                    { key: 'trades', label: '거래 내역', count: (displayedStatus?.trade_history || []).length },
                                    { key: 'events', label: '이벤트' },
                                ].map((tab) => (
                                    <button
                                        key={tab.key}
                                        type="button"
                                        className={`section-tab ${activeSection === tab.key ? 'active' : ''}`}
                                        onClick={() => selectSection(tab.key)}
                                    >
                                        {tab.label}
                                        {tab.count > 0 && <span className="count">{tab.count}</span>}
                                    </button>
                                ))}
                            </nav>

                            {activeSection === 'overview' && (
                                <>
                                    <BotStatusStrip
                                        status={displayedStatus}
                                        config={resolvedConfig}
                                        mode={portfolio?.mode}
                                        nextBuyTarget={getNextBuyTarget(displayedStatus)}
                                        runLabel={isDevMode && simMeta ? describeDevStartOption(simMeta.replay_days ? `${simMeta.replay_days}d` : 'live') : null}
                                    />
                            {(() => {
                                // Open orders come from the real strategy status. A stopped simulation's
                                // overlay still lists its in-memory orders, which no longer exist anywhere.
                                const counts = (isDevMode ? status?.status_counts : displayedStatus?.status_counts) || {};
                                const hasOpenOrders = (counts.pending_sell || 0) + (counts.pending_buy || 0) > 0;
                                const realRunning = !isDevMode && !!displayedStatus?.is_running;
                                const canStart = isDevMode ? canStartInDev : !realRunning;
                                const isRunningAny = isDevSimulationActive || isDevBotRunning || realRunning;
                                const busy = simActionLoading;
                                const showHardStop = !isDevSimulationActive && (realRunning || isDevBotRunning || hasOpenOrders);
                                const runLabel = describeDevStartOption(simMeta?.replay_days ? `${simMeta.replay_days}d` : 'live');
                                const onRealStart = () => {
                                    if (!window.confirm(`실거래를 시작합니다.\n${displayedStatus?.ticker}을(를) 현재가에 첫 분할만큼 즉시 시장가 매수합니다. 계속할까요?`)) return;
                                    handleStart();
                                };
                                const onDevQuickStart = () => {
                                    if (quickDevStartOption) handleStartDevBot(quickDevStartOption);
                                    else setIsStartBotModalOpen(true);
                                };
                                let hint;
                                if (isDevMode && isDevSimulationActive && liveSessionState?.buying_paused) hint = '매수 일시정지 중. 매도 주문은 계속 감시하고, 재개하면 다시 삽니다.';
                                else if (isDevMode && isDevSimulationActive) hint = `${runLabel} 진행 중. 매수만 잠시 멈추거나 완전히 정지할 수 있습니다.`;
                                else if (isDevMode && isDevBotRunning) hint = '모의 투자 봇이 실행 중입니다.';
                                else if (isDevMode && quickDevStartOption) hint = `최근 방식: ${describeDevStartOption(quickDevStartOption)}. 버튼을 누르면 이 방식으로 바로 시작하고, ▾에서 바꿀 수 있습니다.`;
                                else if (isDevMode) hint = '시작 방식(실시간 / 과거 리플레이)을 고르는 창이 뜹니다.';
                                else if (realRunning) hint = '매수 중단은 새 매수만 멈추고, 걸어둔 매도 주문은 그대로 둡니다.';
                                else hint = '시작하면 현재가에 첫 분할을 바로 삽니다.';
                                if (hasSimResults && canStart) hint = `마지막 시뮬레이션 결과를 표시 중입니다. ${hint}`;
                                return (
                                    <div className="action-bar">
                                        <div className="action-bar-primary">
                                            {canStart ? (
                                                isDevMode ? (
                                                    <div className="btn-split">
                                                        <button type="button" className="btn-primary-lg" onClick={onDevQuickStart} disabled={busy}>
                                                            {busy ? '시작하는 중…' : '▶ 모의 투자 시작'}
                                                        </button>
                                                        <button type="button" className="btn-primary-lg btn-split-caret" onClick={() => setIsStartBotModalOpen(true)} disabled={busy} aria-label="시작 방식 선택" title="시작 방식 선택">
                                                            ▾
                                                        </button>
                                                    </div>
                                                ) : (
                                                    <button type="button" className="btn-primary-lg danger" onClick={onRealStart}>
                                                        ▶ 실거래 시작
                                                    </button>
                                                )
                                            ) : isDevMode ? (
                                                <>
                                                    {isDevSimulationActive && (
                                                        liveSessionState?.buying_paused ? (
                                                            <button type="button" className="btn-primary-lg" onClick={handleResumeBuying} disabled={busy} title="새 매수를 다시 시작합니다.">
                                                                ▶ 매수 재개
                                                            </button>
                                                        ) : (
                                                            <button type="button" className="btn-pause" onClick={handlePauseBuying} disabled={busy} title="새 매수만 멈춥니다. 걸어둔 매도 주문은 계속 체결을 기다립니다.">
                                                                ⏸ 매수 일시정지
                                                            </button>
                                                        )
                                                    )}
                                                    <button type="button" className="btn-stop" onClick={handleStop} disabled={busy} title="시뮬레이션을 완전히 끝냅니다.">
                                                        {busy ? '처리 중…' : '■ 시뮬레이션 정지'}
                                                    </button>
                                                </>
                                            ) : (
                                                <button type="button" className="btn-stop" onClick={handleStop} title="새 매수만 멈춥니다. 걸어둔 매도 주문은 그대로 체결을 기다립니다.">
                                                    ⏸ 매수 중단
                                                </button>
                                            )}
                                            {showHardStop && (
                                                <button type="button" className="btn-hardstop" onClick={handleHardStop} disabled={busy} title="매수·매도 주문을 모두 취소하고 멈춥니다. 코인은 지갑에 남습니다.">
                                                    ⛔ 전량 정지
                                                </button>
                                            )}
                                            <span className="action-bar-hint">{hint}</span>
                                        </div>
                                        <div className="action-bar-more">
                                            <button type="button" className="btn-ghost" onClick={() => setIsMoreMenuOpen((v) => !v)} aria-haspopup="menu" aria-expanded={isMoreMenuOpen}>
                                                관리 ▾
                                            </button>
                                            {isMoreMenuOpen && (
                                                <div className="more-menu" role="menu" onMouseLeave={() => setIsMoreMenuOpen(false)}>
                                                    <button type="button" role="menuitem" onClick={() => { setIsMoreMenuOpen(false); handleExport(); }}>
                                                        ⬇ 거래 내역 CSV 내보내기
                                                    </button>
                                                    <button type="button" role="menuitem" disabled={isRunningAny} onClick={() => { setIsMoreMenuOpen(false); handleReset(); }}>
                                                        🔄 상태 초기화
                                                        <small>{isRunningAny ? '먼저 정지한 뒤 할 수 있습니다.' : '주문 취소, 포지션과 거래 기록 삭제. 지갑 잔고는 유지됩니다.'}</small>
                                                    </button>
                                                    <div className="more-menu-divider" role="separator" />
                                                    <button type="button" role="menuitem" className="danger" disabled={isRunningAny} onClick={() => { setIsMoreMenuOpen(false); handleDeleteStrategy(); }}>
                                                        🗑 전략 삭제
                                                        <small>{isRunningAny ? '먼저 정지한 뒤 할 수 있습니다.' : '되돌릴 수 없습니다.'}</small>
                                                    </button>
                                                </div>
                                            )}
                                        </div>
                                    </div>
                                );
                            })()}
                            {(isDevMode && (simMeta || liveError)) && (
                                <div className={`sim-info ${simMeta?.status === 'running' ? 'running' : 'stopped'}`}>
                                    {simMeta && (
                                        <div className="sim-info-row">
                                            <span className={`sim-info-state ${simMeta.status === 'running' ? 'running' : ''}`}>
                                                {simMeta.status !== 'running' ? '■ 정지됨' : liveSessionState?.buying_paused ? '⏸ 매수 일시정지' : '● 진행 중'}
                                            </span>
                                            <span>{describeDevStartOption(simMeta.replay_days ? `${simMeta.replay_days}d` : 'live')}</span>
                                            <span>거래 {simMeta.trades}건</span>
                                            <span style={{ color: (simMeta.realized_profit || 0) >= 0 ? '#10b981' : '#ef4444' }}>
                                                손익 {(simMeta.realized_profit || 0) >= 0 ? '+' : ''}₩{Math.round(simMeta.realized_profit || 0).toLocaleString()}
                                            </span>
                                            <span>누적 매수 ₩{Math.round(simMeta.cumulative_buy_amount || 0).toLocaleString()}</span>
                                            <span>누적 매도 ₩{Math.round(simMeta.cumulative_sell_amount || 0).toLocaleString()}</span>
                                            <span>최대 투자 ₩{Math.round(simMeta.max_invested_amount || 0).toLocaleString()}</span>
                                        </div>
                                    )}
                                    {liveError && <div className="sim-info-error">{liveError}</div>}
                                </div>
                            )}

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
                                    adaptiveState={{
                                        enabled: !!resolvedConfig?.use_adaptive_buy_control,
                                        pressure: displayedStatus?.adaptive_reentry_pressure,
                                        multiplier: displayedStatus?.adaptive_effective_buy_multiplier,
                                        fastDropActive: displayedStatus?.adaptive_fast_drop_active,
                                    }}
                                />
                            </div>

                            
                            {/* Segment Summary (PRICE mode only) */}
                            {(resolvedConfig?.strategy_mode || 'PRICE') !== 'RSI' && strategyConfig?.price_segments?.length > 0 && (
                                <div className="card segment-status-card" style={{ marginBottom: '1rem' }}>
                                    <div className="card-header">
                                        <span className="card-title">구간 현황</span>
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
                                                        구간 {index + 1}
                                                    </div>
                                                    <div style={{ fontSize: '0.85rem', color: '#e2e8f0', marginBottom: '0.5rem', fontWeight: 'bold' }}>
                                                        ₩{segment.min_price.toLocaleString()} - ₩{segment.max_price.toLocaleString()}
                                                    </div>
                                                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.5rem', fontSize: '0.75rem' }}>
                                                        <div>
                                                            <div style={{ color: '#94a3b8' }}>사용 분할</div>
                                                            <div style={{ fontWeight: 'bold' }}>
                                                                <span style={{ color: segmentSplits.length > segment.max_splits ? '#ef4444' : '#e2e8f0' }}>
                                                                    {segmentSplits.length}
                                                                </span>
                                                                <span style={{ color: '#e2e8f0' }}> / {segment.max_splits}</span>
                                                            </div>
                                                        </div>
                                                        <div>
                                                            <div style={{ color: '#94a3b8' }}>투자금</div>
                                                            <div style={{ color: '#10b981', fontWeight: 'bold' }}>
                                                                ₩{Math.round(totalInvested).toLocaleString()}
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
                                                        범위 밖
                                                    </div>
                                                    <div style={{ fontSize: '0.85rem', color: '#ef4444', marginBottom: '0.5rem', fontWeight: 'bold' }}>
                                                        설정한 구간 밖의 포지션
                                                    </div>
                                                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.5rem', fontSize: '0.75rem' }}>
                                                        <div>
                                                            <div style={{ color: '#94a3b8' }}>개수</div>
                                                            <div style={{ fontWeight: 'bold', color: '#e2e8f0' }}>
                                                                {outOfRangeSplits.length}
                                                            </div>
                                                        </div>
                                                        <div>
                                                            <div style={{ color: '#94a3b8' }}>투자금</div>
                                                            <div style={{ color: '#ef4444', fontWeight: 'bold' }}>
                                                                ₩{Math.round(outOfRangeInvested).toLocaleString()}
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

                            
                                </>
                            )}

                            {activeSection === 'settings' && (
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
                            
                            )}

                            {activeSection === 'trades' && (
                                <>
                            {/* Recent Trades Section */}
                            {displayedStatus?.trade_history && displayedStatus?.trade_history.length > 0 && (
                                <div className="trades-container">
                                    <div className="card">
                                        <div className="card-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                                            <span className="card-title">
                                                {`거래 내역 (${displayedStatus?.name})`}
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
                                                    {tradesPage} / {Math.ceil((displayedStatus?.trade_history || []).length / TRADES_PER_PAGE) || 1}
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
                                                        <th style={{ padding: '1rem' }}>매수 시각</th>
                                                        <th style={{ padding: '1rem' }}>매도 시각</th>
                                                        <th style={{ padding: '1rem' }}>분할</th>
                                                        <th style={{ padding: '1rem' }}>정보</th>
                                                        <th style={{ padding: '1rem', textAlign: 'right' }}>매수 금액</th>
                                                        <th style={{ padding: '1rem', textAlign: 'right' }}>매도 금액</th>
                                                        <th style={{ padding: '1rem', textAlign: 'right' }}>총 수익</th>
                                                        <th style={{ padding: '1rem', textAlign: 'right' }}>수수료</th>
                                                        <th style={{ padding: '1rem', textAlign: 'right' }}>순수익</th>
                                                        <th style={{ padding: '1rem', textAlign: 'right' }}>수익률</th>
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

                            
                                    {!(displayedStatus?.trade_history?.length > 0) && (
                                        <div className="card section-empty">아직 완료된 거래가 없습니다. 매수 후 목표가에 팔리면 여기에 쌓입니다.</div>
                                    )}
                                </>
                            )}

                            {activeSection === 'events' && (
                                <>
                            {/* System Event Log */}
                            <div className="event-log-container">
                                <EventLog
                                    strategyId={selectedStrategyId}
                                    apiBaseUrl={API_BASE_URL}
                                    status={displayedStatus?.status}
                                    simulationEvents={simOverlayState ? simEventsForLog : null}
                                />
                            </div>
                        
                                </>
                            )}
                        </main>
                    </div>
                </>
            )}

        </div>
    );
};

export default Dashboard;
