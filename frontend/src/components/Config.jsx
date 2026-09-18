import React, { useState } from 'react';
import axios from 'axios';
import Slider from 'rc-slider';
import 'rc-slider/assets/index.css';
import { API_BASE_URL } from '../lib/api';

const defaultConfig = {
    strategy_mode: 'PRICE',
    use_adaptive_buy_control: false,
    adaptive_sell_pressure_step: 1.0,
    adaptive_buy_relief_step: 1.0,
    adaptive_pressure_cap: 4.0,
    adaptive_probe_multiplier: 0.5,
    use_fast_drop_brake: true,
    fast_drop_trigger_levels: 2,
    fast_drop_batch_cap: 1,
    fast_drop_next_gap_levels: 2,
    fast_drop_multiplier_cap: 0.75,
};
const DEFAULT_PRICE_SEGMENT_MAX_SPLITS = 20;

const adaptivePresets = [
    {
        key: 'balanced',
        label: '균형형',
        description: '추세를 크게 놓치지 않으면서 상단 재물림을 완화',
        values: {
            use_adaptive_buy_control: true,
            adaptive_sell_pressure_step: 0.8,
            adaptive_buy_relief_step: 1.0,
            adaptive_pressure_cap: 3.0,
            adaptive_probe_multiplier: 0.65,
            use_fast_drop_brake: true,
            fast_drop_trigger_levels: 3,
            fast_drop_batch_cap: 1,
            fast_drop_next_gap_levels: 2,
            fast_drop_multiplier_cap: 0.8,
        },
    },
    {
        key: 'trend',
        label: '추세추종형',
        description: '눌림 추종을 더 우선하고 제한은 약하게',
        values: {
            use_adaptive_buy_control: true,
            adaptive_sell_pressure_step: 0.6,
            adaptive_buy_relief_step: 1.0,
            adaptive_pressure_cap: 2.5,
            adaptive_probe_multiplier: 0.75,
            use_fast_drop_brake: true,
            fast_drop_trigger_levels: 3,
            fast_drop_batch_cap: 1,
            fast_drop_next_gap_levels: 2,
            fast_drop_multiplier_cap: 0.85,
        },
    },
    {
        key: 'defensive',
        label: '방어형',
        description: '고점 재진입과 급락 다단매수를 더 강하게 억제',
        values: {
            use_adaptive_buy_control: true,
            adaptive_sell_pressure_step: 1.0,
            adaptive_buy_relief_step: 0.8,
            adaptive_pressure_cap: 4.0,
            adaptive_probe_multiplier: 0.5,
            use_fast_drop_brake: true,
            fast_drop_trigger_levels: 2,
            fast_drop_batch_cap: 1,
            fast_drop_next_gap_levels: 2,
            fast_drop_multiplier_cap: 0.75,
        },
    },
];

const adaptiveTooltips = {
    use_adaptive_buy_control: '매도 후 재진입 압력과 급락 브레이크를 사용해 매수 금액과 배치 규모를 자동으로 완화합니다.',
    adaptive_sell_pressure_step: '매도가 체결될 때 스트레스가 얼마나 빨리 쌓일지 정합니다. 높을수록 몇 번 팔린 뒤 다음 매수를 더 작게 줄입니다.',
    adaptive_buy_relief_step: '매수가 체결될 때 스트레스가 얼마나 빨리 풀릴지 정합니다. 높을수록 다시 사면서 매수 크기가 더 빨리 정상으로 복구됩니다.',
    adaptive_pressure_cap: '스트레스 지수의 최대값입니다. 낮을수록 빨리 포화되고, 높을수록 더 천천히 누적됩니다.',
    adaptive_probe_multiplier: '스트레스가 최대일 때 적용되는 최소 매수 비율입니다. 0.65면 기본 split 금액의 65%만 매수합니다.',
    use_fast_drop_brake: '급락 중 과도한 연속 매수를 막는 보조 브레이크입니다. 여러 레벨을 한 번에 통과할 때 배치 수와 매수 크기를 추가로 제한합니다.',
    fast_drop_trigger_levels: '현재 가격이 한 번에 몇 개 buy level을 통과하면 급락 브레이크를 켤지 정합니다.',
    fast_drop_batch_cap: '급락 브레이크가 켜졌을 때 한 번에 최대 몇 개 split까지 살지 정합니다.',
    fast_drop_next_gap_levels: '급락 브레이크 매수 후 다음 매수 목표를 몇 레벨 아래로 넓힐지 정합니다.',
    fast_drop_multiplier_cap: '급락 브레이크가 켜졌을 때 허용되는 최대 매수 비율입니다. 현재 압력이 낮아도 이 값 이상으로는 사지 않습니다.',
};

const Config = ({ config, onUpdate, strategyId, currentPrice }) => {


    const [formData, setFormData] = useState({ ...defaultConfig, ...(config || {}) });
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
                setFormData({ ...defaultConfig, ...config });
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

    const clampNumber = (value, fallback, min = Number.NEGATIVE_INFINITY, max = Number.POSITIVE_INFINITY) => {
        const num = Number(value);
        if (!Number.isFinite(num)) return fallback;
        return Math.min(max, Math.max(min, num));
    };

    const sanitizeAdaptiveConfig = (data) => ({
        ...data,
        use_adaptive_buy_control: !!data.use_adaptive_buy_control,
        adaptive_sell_pressure_step: clampNumber(data.adaptive_sell_pressure_step, 1.0, 0.1),
        adaptive_buy_relief_step: clampNumber(data.adaptive_buy_relief_step, 1.0, 0.1),
        adaptive_pressure_cap: clampNumber(data.adaptive_pressure_cap, 4.0, 0.1),
        adaptive_probe_multiplier: clampNumber(data.adaptive_probe_multiplier, 0.5, 0.05, 1.0),
        use_fast_drop_brake: data.use_fast_drop_brake !== false,
        fast_drop_trigger_levels: Math.max(1, Math.round(clampNumber(data.fast_drop_trigger_levels, 2, 1))),
        fast_drop_batch_cap: Math.max(1, Math.round(clampNumber(data.fast_drop_batch_cap, 1, 1))),
        fast_drop_next_gap_levels: Math.max(1, Math.round(clampNumber(data.fast_drop_next_gap_levels, 2, 1))),
        fast_drop_multiplier_cap: clampNumber(data.fast_drop_multiplier_cap, 0.75, 0.05, 1.0),
    });

    const applyAdaptivePreset = (presetValues) => {
        setIsEditing(true);
        setFormData((prev) => ({
            ...prev,
            ...sanitizeAdaptiveConfig({
                ...prev,
                ...presetValues,
            }),
        }));
    };

    const isAdaptivePresetActive = (presetValues) => {
        const current = sanitizeAdaptiveConfig(formData || {});
        const target = sanitizeAdaptiveConfig({ ...(formData || {}), ...presetValues });
        return Object.keys(presetValues).every((key) => {
            const currentValue = current[key];
            const targetValue = target[key];
            if (typeof targetValue === 'number') {
                return Math.abs(Number(currentValue) - Number(targetValue)) < 1e-9;
            }
            return currentValue === targetValue;
        });
    };

    const buildFallbackSegment = (data) => {
        const minPrice = Number(data.min_price) || 0;
        const rawMaxPrice = Number(data.max_price) || 0;
        const maxPrice = rawMaxPrice > minPrice ? rawMaxPrice : 1000000000;
        return {
            min_price: minPrice,
            max_price: maxPrice,
            investment_per_split: Number(data.investment_per_split) || 100000,
            max_splits: DEFAULT_PRICE_SEGMENT_MAX_SPLITS,
        };
    };

    const ensureSegments = (data) => {
        const segments = Array.isArray(data.price_segments) ? data.price_segments : [];
        if (segments.length > 0) {
            return segments;
        }
        return [buildFallbackSegment(data)];
    };

    React.useEffect(() => {
        const mode = formData?.strategy_mode || 'PRICE';
        if (mode !== 'PRICE') {
            return;
        }
        if (!Array.isArray(formData?.price_segments) || formData.price_segments.length === 0) {
            setFormData(prev => ({
                ...prev,
                price_segments: ensureSegments(prev || {}),
            }));
        }
    }, [formData?.strategy_mode, formData?.price_segments?.length]);

    const handleChange = (e) => {
        setIsEditing(true);
        const { name, value, type, checked } = e.target;

        // Fields that should be treated as floats/ints directly
        const floatFields = [
            'fee_rate', 'buy_rate', 'sell_rate', 'tick_interval',
            'rsi_buy_max', 'rsi_buy_cross_threshold', 'rsi_sell_min', 'rsi_sell_cross_threshold',
            'watch_rsi_threshold',
            'trailing_buy_rebound_percent',
            'adaptive_sell_pressure_step', 'adaptive_buy_relief_step',
            'adaptive_pressure_cap', 'adaptive_probe_multiplier', 'fast_drop_multiplier_cap',
        ];

        const intFields = [
            'max_trades_per_day', 'rsi_period',
            'rsi_buy_first_amount',
            'rsi_sell_first_amount',
            'max_holdings',
            'fast_drop_trigger_levels', 'fast_drop_batch_cap', 'fast_drop_next_gap_levels',
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
        } else if (name === 'strategy_mode' || name === 'rebuy_strategy') {
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

            const { budget: newBudget, ...rawConfigData } = formData;
            const configData = {
                ...sanitizeAdaptiveConfig(rawConfigData),
                price_segments: ensureSegments(rawConfigData),
            };
            const response = await axios.post(`${API_BASE_URL}/strategies/config`, {
                strategy_id: strategyId,
                config: configData,
                budget: newBudget
            });
            setIsEditing(false);
            onUpdate();
            alert('설정을 저장했습니다.');
        } catch (error) {
            console.error('Failed to update config:', error);
            const errorMsg = error.response?.data?.detail || error.message || 'Unknown error';
            alert(`설정 저장 실패:\n${errorMsg}`);
        }
    };

    const renderClassicConfig = () => (
        <>
            <div className="input-group">
                <label>매수 하한가 (KRW)</label>
                <input
                    type="text"
                    name="min_price"
                    value={formatNumber(formData.min_price)}
                    onChange={handleChange}
                    placeholder="e.g. 50,000,000"
                />
                <small className="field-note">이 가격보다 낮으면 새로 사지 않습니다. 0이면 저장 시 현재가 -15%로 자동 설정됩니다.</small>
            </div>
            <div className="input-group">
                <label>매수 상한가 (KRW)</label>
                <input
                    type="text"
                    name="max_price"
                    value={formatNumber(formData.max_price)}
                    onChange={handleChange}
                    placeholder="e.g. 100,000,000"
                />
                <small className="field-note">이 가격보다 높으면 새로 사지 않습니다. 0이면 현재가 +15%로 자동 설정됩니다.</small>
            </div>
            <div className="input-group">
                <label>매수 간격 (비율)</label>
                <input
                    type="number"
                    step="any"
                    name="buy_rate"
                    value={formData.buy_rate ?? 0.005}
                    onChange={handleChange}
                />
                <small style={{ color: '#94a3b8', fontSize: '0.75rem' }}>
                    마지막 매수가보다 {((formData.buy_rate ?? 0.005) * 100).toFixed(2)}% 떨어지면 다음 분할을 삽니다
                </small>
            </div>
            <div className="input-group">
                <label>목표 수익률 (비율)</label>
                <input
                    type="number"
                    step="any"
                    name="sell_rate"
                    value={formData.sell_rate ?? 0.005}
                    onChange={handleChange}
                />
                <small style={{ color: '#94a3b8', fontSize: '0.75rem' }}>
                    각 분할은 매수가보다 {((formData.sell_rate ?? 0.005) * 100).toFixed(2)}% 오르면 팝니다
                </small>
            </div>

            <details className="config-advanced">
                <summary>고급 설정 <span>가격 구간별 투자금, 재진입, 추적 매수, 적응형 조절</span></summary>
                <div className="config-advanced-body">
            {/* Price Segments Editor - Visual Bar Split Mode */}
            <div style={{ marginTop: '1.5rem', marginBottom: '0.5rem', fontWeight: 'bold', color: '#60a5fa', borderTop: '1px solid #334155', paddingTop: '1rem' }}>
                가격 구간별 설정
            </div>
            <div style={{ marginBottom: '1rem', background: '#0f172a', padding: '1rem', borderRadius: '0.5rem', border: '1px solid #334155' }}>
                {/* Segment Count Selector */}
                <div style={{ marginBottom: '1.5rem' }}>
                    <label style={{ fontSize: '0.9rem', color: '#e2e8f0', marginBottom: '0.5rem', display: 'block' }}>
                        구간 수: {formData.price_segments?.length || 0}
                    </label>
                    <div style={{ padding: '0 10px', marginBottom: '0.5rem' }}>
                        <Slider
                            min={1}
                            max={10}
                            value={formData.price_segments?.length || 0}
                            onChange={(count) => {
                                setIsEditing(true);
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
                        드래그해서 구간 수를 정합니다. 구간마다 분할당 금액과 최대 분할 수를 다르게 둘 수 있습니다
                    </div>
                </div>

                {formData.price_segments && formData.price_segments.length > 0 ? (
                    <>
                        {/* Visual Range Divider */}
                        <div style={{ marginBottom: '1.5rem', padding: '1rem', background: '#1e293b', borderRadius: '0.5rem', border: '1px solid #475569' }}>
                            <label style={{ fontSize: '0.8rem', color: '#94a3b8', marginBottom: '0.75rem', display: 'block' }}>
                                구간 경계 (드래그로 조절)
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
                                구간별 설정
                            </div>
                            {formData.price_segments.map((segment, index) => (
                                <div key={index} style={{ marginBottom: '1rem', padding: '0.75rem', background: '#1e293b', borderRadius: '0.5rem', border: '1px solid #475569' }}>
                                    <div style={{ fontSize: '0.85rem', color: '#cbd5e1', marginBottom: '0.5rem', fontWeight: 'bold' }}>
                                        구간 {index + 1}: ₩{formatNumber(segment.min_price)} - ₩{formatNumber(segment.max_price)}
                                    </div>

                                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem' }}>
                                        <div>
                                            <label style={{ fontSize: '0.75rem', color: '#94a3b8', marginBottom: '0.25rem', display: 'block' }}>
                                                분할당 투자금
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
                                                최대 분할 수
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
                        구간이 없습니다.<br />
                        <span style={{ fontSize: '0.8rem' }}>위 슬라이더로 구간을 하나 이상 만드세요</span>
                    </div>
                )}
            </div>
            <div className="input-group">
                <label>전량 매도 후 재진입 방식</label>
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
                    <option value="reset_on_clear">현재가에서 바로 다시 시작 (추세 추종)</option>
                    <option value="last_sell_price">마지막 매도가에서 한 칸 떨어지면 매수 (균형)</option>
                    <option value="last_buy_price">마지막 매수가에서 한 칸 떨어지면 매수 (보수)</option>
                </select>
            </div>

            {/* Trailing Buy Settings */}
            <div style={{ marginTop: '1.5rem', marginBottom: '0.5rem', fontWeight: 'bold', color: '#fbbf24', borderTop: '1px solid #334155', paddingTop: '1rem' }}>
                추적 매수 (급락 시 반등 확인 후 진입)
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
                    추적 매수 사용 (RSI 필터)
                </label>
            </div>

            {formData.use_trailing_buy && (
                <div className="input-group" style={{ paddingLeft: '2rem', borderLeft: '2px solid #fbbf24' }}>
                    <div className="input-group">
                        <label>감시 모드 진입 RSI</label>
                        <input
                            type="number"
                            name="watch_rsi_threshold"
                            value={formData.watch_rsi_threshold ?? 30}
                            onChange={handleChange}
                            placeholder="30"
                        />
                        <small style={{ color: '#94a3b8', fontSize: '0.75rem', display: 'block', marginTop: '0.25rem' }}>
                            5분봉 RSI가 이 값(기본 30) 아래면 바로 사지 않고 <strong>감시 모드</strong>로 들어갑니다.
                        </small>
                    </div>

                    <label>반등 확인 폭 (%)</label>
                    <input
                        type="number"
                        step="any"
                        name="trailing_buy_rebound_percent"
                        value={formData.trailing_buy_rebound_percent ?? 0.2}
                        onChange={handleChange}
                        placeholder="0.2"
                    />
                    <small style={{ color: '#94a3b8', fontSize: '0.75rem', display: 'block', marginTop: '0.25rem' }}>
                        하락 중 최저가에서 <strong>{formData.trailing_buy_rebound_percent ?? 0.2}%</strong> 반등하면 매수합니다.
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
                            반등 시 건너뛴 분할을 한꺼번에 매수
                        </label>
                    </div>
                    <small style={{ color: '#94a3b8', fontSize: '0.75rem', display: 'block', marginTop: '0.25rem' }}>
                        감시 모드가 반등으로 끝날 때만 적용됩니다. 켜면 건너뛴 레벨만큼 여러 분할을 한 번에 사고, 끄면 한 분할만 삽니다.
                    </small>
                </div>
            )}

            <div style={{ marginTop: '1.5rem', marginBottom: '0.5rem', fontWeight: 'bold', color: '#38bdf8', borderTop: '1px solid #334155', paddingTop: '1rem' }}>
                적응형 매수 조절
            </div>

            <div style={{ display: 'flex', alignItems: 'center', marginBottom: '1rem' }}>
                <input
                    type="checkbox"
                    id="use_adaptive_buy_control"
                    name="use_adaptive_buy_control"
                    checked={formData.use_adaptive_buy_control || false}
                    onChange={handleChange}
                    title={adaptiveTooltips.use_adaptive_buy_control}
                    style={{ width: '1.25rem', height: '1.25rem', marginRight: '0.75rem', accentColor: '#38bdf8' }}
                />
                <label htmlFor="use_adaptive_buy_control" title={adaptiveTooltips.use_adaptive_buy_control} style={{ margin: 0, cursor: 'pointer', color: formData.use_adaptive_buy_control ? '#38bdf8' : '#94a3b8' }}>
                    적응형 매수 조절 사용
                </label>
            </div>

            {formData.use_adaptive_buy_control && (
                <div className="input-group" style={{ paddingLeft: '2rem', borderLeft: '2px solid #38bdf8' }}>
                    <div style={{ marginBottom: '1rem' }}>
                        <div style={{ marginBottom: '0.6rem', fontWeight: 'bold', color: '#e2e8f0' }}>프리셋</div>
                        <div style={{ display: 'flex', gap: '0.6rem', flexWrap: 'nowrap' }}>
                            {adaptivePresets.map((preset) => {
                                const active = isAdaptivePresetActive(preset.values);
                                return (
                                    <button
                                        key={preset.key}
                                        type="button"
                                        onClick={() => applyAdaptivePreset(preset.values)}
                                        title={preset.description}
                                        style={{
                                            textAlign: 'center',
                                            padding: '0.65rem 0.75rem',
                                            borderRadius: '0.5rem',
                                            border: active ? '1px solid #38bdf8' : '1px solid #334155',
                                            backgroundColor: active ? 'rgba(56, 189, 248, 0.14)' : '#0f172a',
                                            color: '#e2e8f0',
                                            cursor: 'pointer',
                                            flex: '1 1 0',
                                            minWidth: 0,
                                        }}
                                    >
                                        <div style={{ fontWeight: 700, color: active ? '#7dd3fc' : '#f8fafc' }}>{preset.label}</div>
                                    </button>
                                );
                            })}
                        </div>
                    </div>

                    <div style={{ marginBottom: '1rem', fontWeight: 'bold', color: '#e2e8f0' }}>재진입 압력</div>

                    <div className="input-group">
                        <label title={adaptiveTooltips.adaptive_sell_pressure_step}>매도 시 압력 증가</label>
                        <input
                            type="number"
                            step="any"
                            min="0.1"
                            max="10"
                            name="adaptive_sell_pressure_step"
                            value={formData.adaptive_sell_pressure_step ?? 1.0}
                            onChange={handleChange}
                            title={adaptiveTooltips.adaptive_sell_pressure_step}
                        />
                    </div>

                    <div className="input-group">
                        <label title={adaptiveTooltips.adaptive_buy_relief_step}>매수 시 압력 완화</label>
                        <input
                            type="number"
                            step="any"
                            min="0.1"
                            max="10"
                            name="adaptive_buy_relief_step"
                            value={formData.adaptive_buy_relief_step ?? 1.0}
                            onChange={handleChange}
                            title={adaptiveTooltips.adaptive_buy_relief_step}
                        />
                    </div>

                    <div className="input-group">
                        <label title={adaptiveTooltips.adaptive_pressure_cap}>압력 상한</label>
                        <input
                            type="number"
                            step="any"
                            min="0.1"
                            max="20"
                            name="adaptive_pressure_cap"
                            value={formData.adaptive_pressure_cap ?? 4.0}
                            onChange={handleChange}
                            title={adaptiveTooltips.adaptive_pressure_cap}
                        />
                    </div>

                    <div className="input-group">
                        <label title={adaptiveTooltips.adaptive_probe_multiplier}>최소 매수 비율</label>
                        <input
                            type="number"
                            step="any"
                            min="0.05"
                            max="1"
                            name="adaptive_probe_multiplier"
                            value={formData.adaptive_probe_multiplier ?? 0.5}
                            onChange={handleChange}
                            title={adaptiveTooltips.adaptive_probe_multiplier}
                        />
                        <small style={{ color: '#94a3b8', fontSize: '0.75rem' }}>
                            Pressure 0 uses 1.0x. Pressure cap uses this minimum size.
                        </small>
                    </div>

                    <div style={{ marginTop: '1.25rem', marginBottom: '1rem', fontWeight: 'bold', color: '#e2e8f0' }}>급락 브레이크</div>

                    <div style={{ display: 'flex', alignItems: 'center', marginBottom: '1rem' }}>
                        <input
                            type="checkbox"
                            id="use_fast_drop_brake"
                            name="use_fast_drop_brake"
                            checked={formData.use_fast_drop_brake !== false}
                            onChange={handleChange}
                            title={adaptiveTooltips.use_fast_drop_brake}
                            style={{ width: '1.25rem', height: '1.25rem', marginRight: '0.75rem', accentColor: '#38bdf8' }}
                        />
                        <label htmlFor="use_fast_drop_brake" title={adaptiveTooltips.use_fast_drop_brake} style={{ margin: 0, cursor: 'pointer', color: formData.use_fast_drop_brake !== false ? '#38bdf8' : '#94a3b8' }}>
                            급락 브레이크 사용 (여러 레벨을 한 번에 지나면 매수 억제)
                        </label>
                    </div>

                    {formData.use_fast_drop_brake !== false && (
                        <>
                            <div className="input-group">
                                <label title={adaptiveTooltips.fast_drop_trigger_levels}>발동 레벨 수</label>
                                <input
                                    type="number"
                                    min="1"
                                    max="10"
                                    name="fast_drop_trigger_levels"
                                    value={formData.fast_drop_trigger_levels ?? 2}
                                    onChange={handleChange}
                                    title={adaptiveTooltips.fast_drop_trigger_levels}
                                />
                            </div>

                            <div className="input-group">
                                <label title={adaptiveTooltips.fast_drop_batch_cap}>한 번에 최대 분할</label>
                                <input
                                    type="number"
                                    min="1"
                                    max="10"
                                    name="fast_drop_batch_cap"
                                    value={formData.fast_drop_batch_cap ?? 1}
                                    onChange={handleChange}
                                    title={adaptiveTooltips.fast_drop_batch_cap}
                                />
                            </div>

                            <div className="input-group">
                                <label title={adaptiveTooltips.fast_drop_next_gap_levels}>다음 매수 간격 (레벨)</label>
                                <input
                                    type="number"
                                    min="1"
                                    max="10"
                                    name="fast_drop_next_gap_levels"
                                    value={formData.fast_drop_next_gap_levels ?? 2}
                                    onChange={handleChange}
                                    title={adaptiveTooltips.fast_drop_next_gap_levels}
                                />
                            </div>

                            <div className="input-group">
                                <label title={adaptiveTooltips.fast_drop_multiplier_cap}>브레이크 시 최대 매수 비율</label>
                                <input
                                    type="number"
                                    step="any"
                                    min="0.05"
                                    max="1"
                                    name="fast_drop_multiplier_cap"
                                    value={formData.fast_drop_multiplier_cap ?? 0.75}
                                    onChange={handleChange}
                                    title={adaptiveTooltips.fast_drop_multiplier_cap}
                                />
                            </div>
                        </>
                    )}
                </div>
            )}
                </div>
            </details>
        </>
    );

    const renderRSIConfig = () => (
        <>
            {/* Indicator Settings */}
            <div style={{ marginTop: '1rem', marginBottom: '0.5rem', fontWeight: 'bold', color: '#60a5fa' }}>지표 설정</div>
            <div className="input-group">
                <label>RSI 기간</label>
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
            <div style={{ marginTop: '1rem', marginBottom: '0.5rem', fontWeight: 'bold', color: '#4ade80' }}>매수 조건</div>
            <div style={{ fontSize: '0.8rem', color: '#94a3b8', marginBottom: '0.75rem' }}>
                * 매일 오전 9시(KST) 확정된 일봉 종가 기준으로 하루 한 번 판단합니다.
            </div>
            <div className="input-group">
                <label>매수 RSI 기준 (아래에서 위로 돌파 시)</label>
                <input type="number" name="rsi_buy_max" value={formData.rsi_buy_max ?? 30} onChange={handleChange} />
            </div>
            <div className="input-group">
                <label>매수 확인 폭 (RSI 변화량)</label>
                <input type="number" step="any" name="rsi_buy_cross_threshold" value={formData.rsi_buy_cross_threshold ?? 0} onChange={handleChange} />
                <small style={{ color: '#94a3b8', fontSize: '0.75rem' }}>
                    (전날 RSI − 전전날 RSI)가 이 값 이상일 때만 매수합니다.
                </small>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr', gap: '0.75rem' }}>
                <div className="input-group">
                    <label>매수 분할 수</label>
                    <input type="number" name="rsi_buy_first_amount" value={formData.rsi_buy_first_amount ?? 1} onChange={handleChange} />
                </div>
            </div>

            {/* Selling Conditions */}
            <div style={{ marginTop: '1rem', marginBottom: '0.5rem', fontWeight: 'bold', color: '#f87171' }}>매도 조건</div>
            <div className="input-group">
                <label>매도 RSI 기준 (위에서 아래로 돌파 시)</label>
                <input type="number" name="rsi_sell_min" value={formData.rsi_sell_min ?? 70} onChange={handleChange} />
            </div>
            <div className="input-group">
                <label>매도 확인 폭 (RSI 변화량)</label>
                <input type="number" step="any" name="rsi_sell_cross_threshold" value={formData.rsi_sell_cross_threshold ?? 0} onChange={handleChange} />
                <small style={{ color: '#94a3b8', fontSize: '0.75rem' }}>
                    (전전날 RSI − 전날 RSI)가 이 값 이상일 때만 매도합니다.
                </small>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr', gap: '0.75rem' }}>
                <div className="input-group">
                    <label>매도 비율 (%)</label>
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
            <div style={{ marginTop: '1rem', marginBottom: '0.5rem', fontWeight: 'bold', color: '#fbbf24' }}>위험 관리</div>
            <div className="input-group">
                <label>최소 수익률 (%)</label>
                <input type="number" step="any" name="sell_rate" value={((formData.sell_rate ?? 0.005) * 100).toFixed(1)}
                    onChange={(e) => handleChange({ target: { name: 'sell_rate', value: parseFloat(e.target.value) / 100 } })}
                />
            </div>
            <div className="input-group">
                <label>최대 보유 분할 수</label>
                <input type="number" name="max_holdings" value={formData.max_holdings ?? 20} onChange={handleChange} />
            </div>
        </>
    );

    // Early return only if formData is completely invalid
    if (!formData) {
        return (
            <div className="card">
                <div className="card-header">
                    <span className="card-title">전략 설정</span>
                </div>
                <div style={{ padding: '1rem', color: '#94a3b8' }}>설정 불러오는 중…</div>
            </div>
        );
    }

    return (
        <div className="card" >
            <div className="card-header">
                <span className="card-title">전략 설정</span>
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
                        가격 그리드 (기본) — 떨어지면 사고 오르면 판다
                    </label>
                    <label style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', cursor: 'pointer', color: (formData.strategy_mode || 'PRICE') === 'RSI' ? '#60a5fa' : '#94a3b8' }}>
                        <input
                            type="radio"
                            name="strategy_mode"
                            value="RSI"
                            checked={(formData.strategy_mode || 'PRICE') === 'RSI'}
                            onChange={handleChange}
                        />
                        RSI 반전 — 일봉 RSI 돌파 신호로 매매
                    </label>
                </div>

                {/* Common Settings */}
                <div className="input-group">
                    <label>총 예산 (KRW)</label>
                    <input
                        type="text"
                        name="budget"
                        value={formatNumber(formData.budget)}
                        onChange={handleChange}
                        placeholder="e.g. 1,000,000"
                    />
                </div>
                {!(formData.strategy_mode !== 'RSI' && formData.price_segments && formData.price_segments.length > 0) && (
                <div className="input-group">
                    <label>분할당 투자금 (KRW)</label>
                    <input
                        type="text"
                        name="investment_per_split"
                        value={formatNumber(formData.investment_per_split)}
                        onChange={handleChange}
                        placeholder="e.g. 100,000"
                    />
                </div>
                )}

                {/* Conditional Settings */}
                {(formData.strategy_mode || 'PRICE') === 'RSI' ? renderRSIConfig() : renderClassicConfig()}

                {/* Common Footer Settings */}
                <details className="config-advanced">
                    <summary>실행 세부 설정 <span>확인 주기, 하루 거래 한도, 수수료</span></summary>
                    <div className="config-advanced-body" style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem' }}>
                    <div className="input-group">
                        <label>확인 주기 (초)</label>
                        <input
                            type="number"
                            step="any"
                            name="tick_interval"
                            value={formData.tick_interval ?? 1.0}
                            onChange={handleChange}
                        />
                    </div>
                    <div className="input-group">
                        <label>하루 최대 거래 수</label>
                        <input
                            type="number"
                            name="max_trades_per_day"
                            value={formData.max_trades_per_day ?? 100}
                            onChange={handleChange}
                        />
                    </div>
                    <div className="input-group" style={{ gridColumn: 'span 2' }}>
                        <label>수수료율</label>
                        <input
                            type="number"
                            step="any"
                            name="fee_rate"
                            value={formData.fee_rate || 0.0005}
                            onChange={handleChange}
                            placeholder="0.0005"
                        />
                    </div>
                    </div>
                </details>

                <button type="submit" className="btn btn-primary" style={{ width: '100%', marginTop: '1rem' }}>
                    설정 저장
                </button>
            </form>
        </div >
    );
};

export default Config;
