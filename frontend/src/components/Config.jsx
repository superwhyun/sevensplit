import React, { useState } from 'react';
import axios from 'axios';
import Slider from 'rc-slider';
import 'rc-slider/assets/index.css';
import { API_BASE_URL } from '../lib/api';
// field-note / config-grid-2 / config-subsection live here; import so this
// component never depends on another component having loaded the stylesheet.
import './strategy/strategy.css';

const defaultConfig = {
    strategy_mode: 'PRICE',
    use_adaptive_buy_control: false,
    adaptive_sell_pressure_step: 1.0,
    adaptive_buy_relief_step: 1.0,
    adaptive_pressure_cap: 4.0,
    adaptive_probe_multiplier: 0.5,
    use_fast_drop_brake: false,
    fast_drop_trigger_levels: 2,
    fast_drop_batch_cap: 1,
    fast_drop_next_gap_levels: 2,
    fast_drop_multiplier_cap: 0.75,
};
const DEFAULT_PRICE_SEGMENT_MAX_SPLITS = 20;

// Presets only touch the pressure-sizing fields. The fast-drop brake is a separate
// switch with its own section, so applying a preset here never changes it.
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
        },
    },
    {
        key: 'trend',
        label: '추세추종형',
        description: '눌림 추종을 더 우선하고 매수 축소는 약하게',
        values: {
            use_adaptive_buy_control: true,
            adaptive_sell_pressure_step: 0.6,
            adaptive_buy_relief_step: 1.0,
            adaptive_pressure_cap: 2.5,
            adaptive_probe_multiplier: 0.75,
        },
    },
    {
        key: 'defensive',
        label: '방어형',
        description: '고점 재진입 시 매수 금액을 더 강하게 축소',
        values: {
            use_adaptive_buy_control: true,
            adaptive_sell_pressure_step: 1.0,
            adaptive_buy_relief_step: 0.8,
            adaptive_pressure_cap: 4.0,
            adaptive_probe_multiplier: 0.5,
        },
    },
];

const adaptiveTooltips = {
    use_adaptive_buy_control: '매도가 쌓일수록 재진입 압력이 올라가 다음 매수 금액을 자동으로 줄입니다. 매수 개수는 건드리지 않습니다.',
    adaptive_sell_pressure_step: '매도가 체결될 때 스트레스가 얼마나 빨리 쌓일지 정합니다. 높을수록 몇 번 팔린 뒤 다음 매수를 더 작게 줄입니다.',
    adaptive_buy_relief_step: '매수가 체결될 때 스트레스가 얼마나 빨리 풀릴지 정합니다. 높을수록 다시 사면서 매수 크기가 더 빨리 정상으로 복구됩니다.',
    adaptive_pressure_cap: '스트레스 지수의 최대값입니다. 낮을수록 빨리 포화되고, 높을수록 더 천천히 누적됩니다.',
    adaptive_probe_multiplier: '스트레스가 최대일 때 적용되는 최소 매수 비율입니다. 0.65면 기본 split 금액의 65%만 매수합니다.',
    use_fast_drop_brake: '적응형 매수 조절과는 별개로 동작하는 독립 기능입니다. 여러 레벨을 한 번에 통과할 때 한 틱에 살 수 있는 분할 개수와 매수 크기를 제한합니다. 감시 모드 종료 후 몰아사기도 함께 제한되니 주의하세요.',
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
        // Group the integer part only. Grouping the whole string also put commas
        // inside the decimals (115,080,499.99,999,999 for an auto-filled price).
        const [intPart, decPart] = num.toString().split('.');
        const grouped = intPart.replace(/\B(?=(\d{3})+(?!\d))/g, ",");
        return decPart === undefined ? grouped : `${grouped}.${decPart}`;
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
        use_fast_drop_brake: !!data.use_fast_drop_brake,
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
        // A single (or absent) segment means the user is on the "classic" simple
        // min/max fields, not the multi-segment ladder editor. Always rebuild that
        // one segment from the current 매수 하한가/상한가 so editing those fields
        // actually changes what the bot checks -- otherwise the buy logic keeps
        // reading a stale segment bound from whenever it was first auto-generated,
        // and the top-level fields silently have no effect (backend:
        // logic_price.py::_effective_segments() only falls back to min_price/
        // max_price when price_segments is empty; once populated, those top-level
        // fields are ignored entirely).
        // Two or more segments means the user deliberately split the ladder in the
        // advanced editor, so that array is left untouched.
        if (segments.length > 1) {
            return segments;
        }
        // Only the price bounds are re-synced. Rebuilding the whole segment here
        // threw away 분할당 투자금 and 최대 분할 수 every time the form was saved,
        // because buildFallbackSegment() takes investment_per_split from the
        // top-level field and hardcodes max_splits.
        const existing = segments[0];
        if (existing) {
            const fallback = buildFallbackSegment(data);
            return [{
                ...existing,
                min_price: fallback.min_price,
                max_price: fallback.max_price,
            }];
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
                <small className="field-note">
                    현재가가 이 가격보다 낮으면 새로 사지 않습니다. 하락장에서 끝없이 물타는 것을 막는 바닥선입니다.
                    0으로 두면 저장 시점이 아니라 다음에 봇이 기동될 때 현재가의 -15%로 자동으로 채워집니다.
                </small>
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
                <small className="field-note">
                    현재가가 이 가격보다 높으면 새로 사지 않습니다. 너무 오른 가격에 새로 들어가는 것을 막는 천장선입니다.
                    0으로 두면 상한 없음으로 동작해 가격이 아무리 올라도 매수를 막지 않습니다.
                    (하한가도 0일 때만 다음 기동 시 현재가 +15%로 함께 채워집니다.)
                </small>
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
            <small className="field-note" style={{ marginBottom: '0.75rem' }}>
                매수 하한가~상한가 범위를 여러 구간으로 나눠, 구간마다 분할당 투자금을 다르게 줄 수 있습니다.
                예를 들어 낮은 가격대에서 더 크게 사고 싶을 때 씁니다. 구간을 나누지 않고 1개로 두면 위에서 입력한 상한가/하한가가 그대로 쓰입니다.
            </small>
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
                            <small className="field-note" style={{ marginTop: 0, marginBottom: '0.6rem' }}>
                                손잡이를 끌어 구간을 나누는 가격을 정합니다. 각 구간의 분할당 투자금은 아래에서 따로 입력합니다.
                            </small>
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

                                    <div className="config-grid-2">
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
                <small className="field-note">
                    보유 분할을 전부 팔아 현금만 남았을 때, 언제 다시 살지 정합니다.
                    <b>추세 추종</b>은 기다리지 않고 현재가에서 바로 새로 시작합니다. 상승장에서 유리하지만 고점에서 다시 시작할 위험이 있습니다.
                    <b>균형</b>은 마지막에 판 가격보다 매수 간격만큼 떨어져야 삽니다.
                    <b>보수</b>는 마지막에 산 가격 기준으로 떨어져야 사므로 가장 늦게 들어갑니다.
                </small>
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
            <small className="field-note" style={{ marginBottom: '1rem' }}>
                급락이 시작되면 정해진 가격에 바로 사지 않고, 5분봉 RSI로 과매도 구간에 들어섰는지 확인한 뒤 잠시 매수를 멈춥니다(감시 모드).
                이후 저점 대비 반등이 확인되면 그때 밀린 구간을 사들입니다. 떨어지는 도중에 계속 받아서 물리는 것을 줄이기 위한 기능입니다.
            </small>

            {formData.use_trailing_buy && (
                <div className="input-group config-subsection" style={{ borderLeftColor: '#fbbf24' }}>
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
                <div className="input-group config-subsection">
                    <div style={{ marginBottom: '1rem' }}>
                        <div style={{ marginBottom: '0.6rem', fontWeight: 'bold', color: '#e2e8f0' }}>프리셋</div>
                        <div className="config-preset-row">
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
                        <small className="field-note">분할 하나가 팔릴 때마다 경계 수위가 얼마나 오를지 정합니다. 1.0이면 한 번 팔릴 때 1만큼 오릅니다. 클수록 몇 번만 팔려도 다음 매수가 빨리 작아집니다.</small>
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
                        <small className="field-note">매수가 체결될 때마다 경계 수위가 얼마나 내려갈지 정합니다. 클수록 매수 금액이 정상 크기로 빨리 돌아옵니다. 작게 잡으면 한동안 계속 작게 삽니다.</small>
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
                        <small className="field-note">경계 수위의 최대값입니다. 4.0이고 증가폭이 1.0이면 분할 4개가 팔린 시점에 최대 경계에 도달합니다. 낮출수록 더 적게 팔려도 최대 경계에 도달합니다.</small>
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
                        <small className="field-note">
                            경계가 최대일 때 적용할 매수 금액 비율입니다. 0.5면 분할당 투자금의 50%만 삽니다.
                            경계가 0이면 100%(정상 크기)로 사고, 경계가 올라갈수록 이 값까지 점점 줄어듭니다.
                        </small>
                    </div>

                </div>
            )}

            <div style={{ marginTop: '1.5rem', marginBottom: '0.5rem', fontWeight: 'bold', color: '#38bdf8', borderTop: '1px solid #334155', paddingTop: '1rem' }}>
                급락 브레이크
            </div>

            <div style={{ display: 'flex', alignItems: 'center', marginBottom: '1rem' }}>
                <input
                    type="checkbox"
                    id="use_fast_drop_brake"
                    name="use_fast_drop_brake"
                    checked={!!formData.use_fast_drop_brake}
                    onChange={handleChange}
                    title={adaptiveTooltips.use_fast_drop_brake}
                    style={{ width: '1.25rem', height: '1.25rem', marginRight: '0.75rem', accentColor: '#38bdf8' }}
                />
                <label htmlFor="use_fast_drop_brake" title={adaptiveTooltips.use_fast_drop_brake} style={{ margin: 0, cursor: 'pointer', color: formData.use_fast_drop_brake ? '#38bdf8' : '#94a3b8' }}>
                    급락 브레이크 사용 (여러 레벨을 한 번에 지나면 매수 개수 제한)
                </label>
            </div>

            {formData.use_fast_drop_brake && (
                <div className="input-group config-subsection">
                    <small style={{ color: '#fbbf24', fontSize: '0.75rem', display: 'block', marginBottom: '1rem' }}>
                        주의: 이 기능을 켜면 감시 모드 종료 후 밀린 구간을 한 번에 몰아사는 동작이
                        "한 틱에 최대 N개"로 제한되어 여러 틱에 나눠 사게 됩니다.
                        몰아사기를 그대로 유지하려면 이 기능을 끄세요.
                    </small>

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
                        <small className="field-note">마지막 매수가 대비 매수 간격 몇 칸을 한꺼번에 지나쳤을 때 브레이크를 걸지 정합니다. 2면 매수 간격 1%일 때 2% 이상 한 번에 빠지면 발동합니다.</small>
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
                        <small className="field-note">브레이크가 걸렸을 때 한 번에 살 수 있는 최대 분할 개수입니다. 1이면 아무리 여러 칸이 밀려 있어도 한 번에 하나씩만 사고 나머지는 다음 확인 때로 넘깁니다.</small>
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
                        <small className="field-note">브레이크 상태로 산 뒤, 다음 매수 목표가를 몇 칸 더 아래로 벌릴지 정합니다. 2면 평소보다 두 배 더 떨어져야 다음 분할을 삽니다. 급락 중 촘촘히 받는 것을 막습니다.</small>
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
                        <small className="field-note">브레이크가 걸렸을 때 허용할 최대 매수 금액 비율입니다. 0.75면 분할당 투자금의 75%를 넘지 않습니다. 적응형 매수 조절이 이미 더 작게 줄였다면 그 값을 따릅니다.</small>
                    </div>
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
                <small className="field-note">RSI를 계산할 때 사용할 일봉 개수입니다. 숫자가 작을수록 신호가 자주, 민감하게 나옵니다. 보통 14를 씁니다.</small>
            </div>

            {/* Buying Conditions */}
            <div style={{ marginTop: '1rem', marginBottom: '0.5rem', fontWeight: 'bold', color: '#4ade80' }}>매수 조건</div>
            <div style={{ fontSize: '0.8rem', color: '#94a3b8', marginBottom: '0.75rem' }}>
                * 매일 오전 9시(KST) 확정된 일봉 종가 기준으로 하루 한 번 판단합니다.
            </div>
            <div className="input-group">
                <label>매수 RSI 기준 (아래에서 위로 돌파 시)</label>
                <input type="number" name="rsi_buy_max" value={formData.rsi_buy_max ?? 30} onChange={handleChange} />
                <small className="field-note">일봉 RSI가 이 값을 아래에서 위로 뚫고 올라올 때 매수합니다. 30이면 과매도 구간에서 벗어나는 순간을 노립니다. 값을 올리면 더 자주, 더 높은 가격에 사게 됩니다.</small>
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
                    <small className="field-note">매수 신호가 나왔을 때 한 번에 몇 개 분할을 살지 정합니다. 1이면 분할당 투자금 한 번치만 삽니다.</small>
                </div>
            </div>

            {/* Selling Conditions */}
            <div style={{ marginTop: '1rem', marginBottom: '0.5rem', fontWeight: 'bold', color: '#f87171' }}>매도 조건</div>
            <div className="input-group">
                <label>매도 RSI 기준 (위에서 아래로 돌파 시)</label>
                <input type="number" name="rsi_sell_min" value={formData.rsi_sell_min ?? 70} onChange={handleChange} />
                <small className="field-note">일봉 RSI가 이 값을 위에서 아래로 뚫고 내려갈 때 매도합니다. 70이면 과매수 구간이 꺾이는 순간에 팝니다. 값을 내리면 더 일찍 팔게 됩니다.</small>
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
                    <small className="field-note">매도 신호가 나왔을 때 보유 수량의 몇 퍼센트를 팔지 정합니다. 100이면 전량 매도, 50이면 절반만 팝니다. 퍼센트 단위이므로 1로 두면 1%만 팔린다는 점에 주의하세요.</small>
                </div>
            </div>

            {/* Risk Management */}
            <div style={{ marginTop: '1rem', marginBottom: '0.5rem', fontWeight: 'bold', color: '#fbbf24' }}>위험 관리</div>
            <div className="input-group">
                <label>최소 수익률 (%)</label>
                <input type="number" step="any" name="sell_rate" value={((formData.sell_rate ?? 0.005) * 100).toFixed(1)}
                    onChange={(e) => handleChange({ target: { name: 'sell_rate', value: parseFloat(e.target.value) / 100 } })}
                />
                <small className="field-note">매도 신호가 떠도 이 수익률에 못 미치면 팔지 않고 그대로 들고 갑니다. 손실 구간에서 신호만 보고 파는 것을 막는 안전장치입니다.</small>
            </div>
            <div className="input-group">
                <label>최대 보유 분할 수</label>
                <input type="number" name="max_holdings" value={formData.max_holdings ?? 20} onChange={handleChange} />
                <small className="field-note">동시에 들고 있을 수 있는 최대 분할 개수입니다. 이 개수를 채우면 매수 신호가 떠도 더 사지 않습니다.</small>
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
                    <small className="field-note">
                        가격 그리드는 정해둔 비율만큼 떨어질 때마다 나눠 사고, 각각 목표 수익률에 도달하면 파는 방식입니다.
                        RSI 반전은 하루 한 번 일봉 RSI가 기준선을 돌파할 때만 매매합니다. 대부분 가격 그리드를 사용합니다.
                    </small>
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
                    <small className="field-note">이 전략이 쓸 수 있는 전체 금액입니다. 보유 중인 분할 매수 금액의 합이 이 금액을 넘지 않습니다.</small>
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
                    <small className="field-note">한 번 매수할 때 넣을 금액입니다. 총 예산을 이 금액으로 나눈 횟수만큼 나눠 살 수 있습니다. 예산 100만원, 분할당 10만원이면 최대 10번 나눠 삽니다.</small>
                </div>
                )}

                {/* Conditional Settings */}
                {(formData.strategy_mode || 'PRICE') === 'RSI' ? renderRSIConfig() : renderClassicConfig()}

                {/* Common Footer Settings */}
                <details className="config-advanced">
                    <summary>실행 세부 설정 <span>확인 주기, 하루 거래 한도, 수수료</span></summary>
                    <div className="config-advanced-body config-grid-2">
                    <div className="input-group">
                        <label>확인 주기 (초)</label>
                        <input
                            type="number"
                            step="any"
                            name="tick_interval"
                            value={formData.tick_interval ?? 1.0}
                            onChange={handleChange}
                        />
                        <small className="field-note">현재가를 확인하고 매매 조건을 검사하는 주기(초)입니다. 1이면 1초마다 봅니다. 너무 짧게 잡으면 거래소 호출 제한에 걸릴 수 있습니다.</small>
                    </div>
                    <div className="input-group">
                        <label>하루 최대 거래 수</label>
                        <input
                            type="number"
                            name="max_trades_per_day"
                            value={formData.max_trades_per_day ?? 100}
                            onChange={handleChange}
                        />
                        <small className="field-note">최근 24시간 동안 허용할 매수 횟수입니다. 이 횟수를 채우면 시간이 지나 여유가 생길 때까지 새로 사지 않습니다. 변동성이 클 때 과도한 매매를 막는 안전장치입니다.</small>
                    </div>
                    <div className="input-group config-grid-span">
                        <label>수수료율</label>
                        <input
                            type="number"
                            step="any"
                            name="fee_rate"
                            value={formData.fee_rate || 0.0005}
                            onChange={handleChange}
                            placeholder="0.0005"
                        />
                        <small className="field-note">거래소 수수료율입니다. 업비트 원화 마켓은 0.0005(0.05%)입니다. 목표 수익률을 계산할 때 수수료를 빼고 남는 이익을 기준으로 삼습니다.</small>
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
