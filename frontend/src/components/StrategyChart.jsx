import { useEffect, useRef, useState } from 'react';
import { createChart, ColorType, CrosshairMode } from 'lightweight-charts';
import axios from 'axios';

const StrategyChart = ({ ticker, splits = [], config = {}, tradeHistory = [], isSimulating = false, simResult, onSimulationComplete, onChartClick }) => {
    const chartContainerRef = useRef();
    const chartRef = useRef();
    const onChartClickRef = useRef(onChartClick);

    // Update ref when prop changes
    useEffect(() => {
        onChartClickRef.current = onChartClick;
    }, [onChartClick]);
    const candlestickSeriesRef = useRef();
    const volumeSeriesRef = useRef();
    const rsiSeries14Ref = useRef();
    const rsiSeries4Ref = useRef();
    const [candleData, setCandleData] = useState([]);
    const [volumeData, setVolumeData] = useState([]);
    const [showResultPopup, setShowResultPopup] = useState(true);

    // Reset popup visibility when simResult changes
    useEffect(() => {
        if (simResult) setShowResultPopup(true);
    }, [simResult]);

    // Helper: Parse exact UTC ISO string to Unix Timestamp
    const parseUTC = (utcString) => {
        if (!utcString) return null;
        // Ensure 'Z' if missing (backend usually sends ISO-like strings which are effectively UTC)
        const timeStr = utcString.endsWith('Z') || utcString.includes('+') ? utcString : utcString + 'Z';
        return new Date(timeStr).getTime() / 1000;
    };

    useEffect(() => {
        const fetchCandles = async () => {
            const interval = config?.strategy_mode?.toUpperCase() === 'RSI' ? 'days' : 'minutes/5';

            const API_BASE_URL = window.location.port === '5173'
                ? `http://${window.location.hostname}:8000`
                : '';

            try {
                const response = await axios.get(`${API_BASE_URL}/candles`, {
                    params: {
                        market: ticker,
                        count: 200,
                        interval: interval
                    }
                });
                const data = response.data;

                // Sort by candle_date_time_utc (always standard)
                data.sort((a, b) => new Date(a.candle_date_time_utc) - new Date(b.candle_date_time_utc));

                const candleData = data.map(d => ({
                    // Use Real UTC Timestamp
                    time: parseUTC(d.candle_date_time_utc),
                    open: d.opening_price,
                    high: d.high_price,
                    low: d.low_price,
                    close: d.trade_price,
                }));

                const volumeData = data.map(d => ({
                    time: parseUTC(d.candle_date_time_utc),
                    value: d.candle_acc_trade_volume,
                    color: d.trade_price >= d.opening_price ? 'rgba(38, 166, 154, 0.5)' : 'rgba(239, 83, 80, 0.5)',
                }));

                setCandleData(candleData);
                setVolumeData(volumeData);
            } catch (error) {
                console.error("Error fetching candles:", error);
            }
        };

        if (ticker) {
            fetchCandles();
            const interval = setInterval(fetchCandles, 60000);
            return () => clearInterval(interval);
        }
    }, [ticker, config.strategy_mode]); // Re-fetch when ticker or strategy mode changes

    // Calculate RSI (Dual: 14 and 4)
    const calculateDualRSI = (data) => {
        // Helper to calculate RSI for a specific period (Wilder's Smoothing)
        const calcRSI = (period) => {
            if (data.length < period + 1) return [];

            const results = [];
            let gains = [];
            let losses = [];

            // 1. Calculate Deltas
            for (let i = 1; i < data.length; i++) {
                const change = data[i].close - data[i - 1].close;
                gains.push(change > 0 ? change : 0);
                losses.push(change < 0 ? Math.abs(change) : 0);
            }

            // 2. Initial Average
            let avgGain = gains.slice(0, period).reduce((a, b) => a + b, 0) / period;
            let avgLoss = losses.slice(0, period).reduce((a, b) => a + b, 0) / period;

            // First RSI point
            let rs = avgLoss === 0 ? 100 : avgGain / avgLoss;
            let rsi = 100 - (100 / (1 + rs));

            results.push({ time: data[period].time, value: rsi });

            // 3. Wilder's Smoothing
            for (let i = period; i < gains.length; i++) {
                avgGain = (avgGain * (period - 1) + gains[i]) / period;
                avgLoss = (avgLoss * (period - 1) + losses[i]) / period;

                rs = avgLoss === 0 ? 100 : avgGain / avgLoss;
                rsi = 100 - (100 / (1 + rs));

                results.push({ time: data[i + 1].time, value: rsi });
            }

            return results;
        };

        return {
            rsi14: calcRSI(14),
            rsi4: calcRSI(4)
        };
    };


    // Update chart data when candleData changes
    useEffect(() => {
        if (!chartRef.current || !candlestickSeriesRef.current) return;

        if (candleData.length > 0) {
            try {
                candlestickSeriesRef.current.setData(candleData);

                if (volumeSeriesRef.current && volumeData.length > 0) {
                    const displayVolumeData = volumeData.map(d => ({
                        ...d,
                        color: d.value > 0 ? d.color : 'rgba(0,0,0,0)'
                    }));
                    volumeSeriesRef.current.setData(displayVolumeData);
                }

                // Update RSI (Dual)
                if (config?.strategy_mode?.toUpperCase() === 'RSI' && rsiSeries14Ref.current && rsiSeries4Ref.current) {
                    const { rsi14, rsi4 } = calculateDualRSI(candleData);
                    rsiSeries14Ref.current.setData(rsi14);
                    rsiSeries4Ref.current.setData(rsi4);

                    chartRef.current.priceScale('rsi').applyOptions({
                        autoScale: false,
                        minValue: 0,
                        maxValue: 100,
                        scaleMargins: { top: 0.7, bottom: 0 },
                        visible: true,
                        borderColor: '#ef4444',
                    });
                } else if (config?.strategy_mode?.toUpperCase() !== 'RSI') {
                    if (rsiSeries14Ref.current) rsiSeries14Ref.current.setData([]);
                    if (rsiSeries4Ref.current) rsiSeries4Ref.current.setData([]);
                }

                chartRef.current.timeScale().fitContent();
            } catch (error) {
                console.error("[Chart] Error setting data:", error);
            }
        }
    }, [candleData, volumeData, config.strategy_mode]);

    // Initialize Chart
    useEffect(() => {
        if (!chartContainerRef.current) return;

        const chart = createChart(chartContainerRef.current, {
            layout: {
                background: { type: ColorType.Solid, color: '#1e293b' },
                textColor: '#cbd5e1',
            },
            grid: {
                vertLines: { color: '#334155' },
                horzLines: { color: '#334155' },
            },
            crosshair: {
                mode: CrosshairMode.Normal,
            },
            rightPriceScale: {
                borderColor: '#334155',
                autoScale: true,
                scaleMargins: {
                    top: 0.05,
                    bottom: 0.3, // Leave space for RSI
                },
            },
            timeScale: {
                borderColor: '#334155',
                timeVisible: true,
                secondsVisible: false,
                // CUSTOM FORMATTER: Display KST (+9h) on X-Axis from UTC Data
                tickMarkFormatter: (time, tickMarkType, locale) => {
                    // 'time' is UTC timestamp from data.
                    // We want to display it as KST.
                    const date = new Date(time * 1000);
                    // Add 9 hours
                    const kstDate = new Date(date.getTime() + (9 * 60 * 60 * 1000));

                    // Simple formatting to HH:mm or DD
                    // tickMarkType: 0=Year, 1=Month, 2=DayOfMonth, 3=Time
                    // We can check tickMarkType or just standard format

                    const pad = (n) => n.toString().padStart(2, '0');
                    const month = kstDate.getUTCMonth() + 1;
                    const day = kstDate.getUTCDate();
                    const hours = kstDate.getUTCHours();
                    const minutes = kstDate.getUTCMinutes();

                    if (tickMarkType === 2) { // Day
                        return `${month}/${day}`;
                    } else if (tickMarkType === 3) { // Time
                        return `${pad(hours)}:${pad(minutes)}`;
                    } else {
                        // Fallback or Month/Year
                        return `${kstDate.getUTCFullYear()}-${pad(month)}-${pad(day)}`;
                    }
                },
            },
            localization: {
                locale: 'ko-KR',
            },
            width: chartContainerRef.current.clientWidth,
            height: 400,
        });

        // Create Legend
        const legend = document.createElement('div');
        legend.style.position = 'absolute';
        legend.style.left = '12px';
        legend.style.top = '12px';
        legend.style.zIndex = '1';
        legend.style.fontSize = '14px';
        legend.style.fontFamily = 'sans-serif';
        legend.style.lineHeight = '18px';
        legend.style.fontWeight = '300';
        legend.style.color = '#cbd5e1';
        chartContainerRef.current.appendChild(legend);

        chart.subscribeCrosshairMove(param => {
            if (
                param.point === undefined ||
                !param.time ||
                param.point.x < 0 ||
                param.point.x > chartContainerRef.current.clientWidth ||
                param.point.y < 0 ||
                param.point.y > chartContainerRef.current.clientHeight
            ) {
                return;
            }

            let rsi14Val = '';
            let rsi4Val = '';

            if (rsiSeries14Ref.current) {
                const data = param.seriesData.get(rsiSeries14Ref.current);
                if (data && data.value !== undefined) rsi14Val = data.value.toFixed(2);
            }
            if (rsiSeries4Ref.current) {
                const data = param.seriesData.get(rsiSeries4Ref.current);
                if (data && data.value !== undefined) rsi4Val = data.value.toFixed(2);
            }

            if (rsi14Val || rsi4Val) {
                legend.innerHTML = `
                    <div style="display: flex; gap: 12px;">
                        ${rsi14Val ? `<div style="color: #8b5cf6">RSI(14): <strong>${rsi14Val}</strong></div>` : ''}
                        ${rsi4Val ? `<div style="color: #f59e0b">RSI(4): <strong>${rsi4Val}</strong></div>` : ''}
                    </div>
                `;
            } else {
                legend.innerHTML = '';
            }
        });

        // Click Handler for Simulation
        chart.subscribeClick(param => {
            console.log("[StrategyChart] Click param:", param);
            if (onChartClickRef.current && param.time) {
                // The chart now uses Real UTC timestamps internally. 
                // param.time is Real UTC. No offset needed.
                console.log("[StrategyChart] Calling onChartClick with UTC time:", param.time);
                onChartClickRef.current(param.time);
            }
        });

        chartRef.current = chart;

        const candlestickSeries = chart.addCandlestickSeries({
            upColor: '#10b981',
            downColor: '#ef4444',
            borderVisible: false,
            wickUpColor: '#10b981',
            wickDownColor: '#ef4444',
            priceFormat: {
                type: 'price',
                precision: 0,
                minMove: 1,
            },
            priceScaleId: 'right',
        });
        candlestickSeriesRef.current = candlestickSeries;

        const volumeSeries = chart.addHistogramSeries({
            color: '#26a69a',
            priceFormat: {
                type: 'volume',
            },
            priceScaleId: 'volume',
        });
        volumeSeriesRef.current = volumeSeries;

        chart.priceScale('volume').applyOptions({
            scaleMargins: {
                top: 0.5,
                bottom: 0.3,
            },
        });

        // Add RSI Series (Dual)
        const rsiSeries14 = chart.addLineSeries({
            color: '#8b5cf6', // Purple
            lineWidth: 2,
            priceScaleId: 'rsi',
            title: 'RSI(14)',
            priceFormat: { type: 'price', precision: 1, minMove: 0.1 },
        });
        rsiSeries14Ref.current = rsiSeries14;

        const rsiSeries4 = chart.addLineSeries({
            color: '#f59e0b', // Yellow/Orange
            lineWidth: 1,
            priceScaleId: 'rsi',
            title: 'RSI(4)',
            priceFormat: { type: 'price', precision: 1, minMove: 0.1 },
        });
        rsiSeries4Ref.current = rsiSeries4;

        rsiSeries14.createPriceLine({ price: 70.0, color: '#ef4444', lineWidth: 1, lineStyle: 2, axisLabelVisible: false });
        rsiSeries14.createPriceLine({ price: 30.0, color: '#10b981', lineWidth: 1, lineStyle: 2, axisLabelVisible: false });

        const handleResize = () => {
            chart.applyOptions({ width: chartContainerRef.current.clientWidth });
        };

        window.addEventListener('resize', handleResize);

        return () => {
            window.removeEventListener('resize', handleResize);
            chart.remove();
        };
    }, []);

    // Markers System (Using True UTC)
    useEffect(() => {
        if (!candlestickSeriesRef.current) return;

        const markers = [];

        // Helper: No more timezone shifting needed. 
        // Just explicit parsing if input is string to ensure safe Unix timestamp.
        const ensureTimestamp = (val) => {
            if (!val) return null;
            if (typeof val === 'number') return val;
            return parseUTC(val);
        };

        if (isSimulating || simResult) {
            if (simResult && simResult.trades) {
                simResult.trades.forEach(t => {
                    // Buy Marker
                    if (t.bought_at) {
                        const buyTime = ensureTimestamp(t.bought_at);
                        if (buyTime) {
                            markers.push({ time: buyTime, position: 'belowBar', color: '#10b981', shape: 'arrowUp', text: '', size: 1 });
                        }
                    }
                    // Sell Marker
                    if (t.timestamp) {
                        const sellTime = ensureTimestamp(t.timestamp);
                        if (sellTime) {
                            markers.push({ time: sellTime, position: 'aboveBar', color: '#ef4444', shape: 'arrowDown', text: '', size: 1 });
                        }
                    }
                });
            }
            if (simResult && simResult.splits) {
                simResult.splits.forEach(s => {
                    if (s.bought_at) {
                        const buyTime = ensureTimestamp(s.bought_at);
                        if (buyTime) {
                            markers.push({ time: buyTime, position: 'belowBar', color: '#eab308', shape: 'arrowUp', text: '', size: 1 });
                        }
                    }
                });
            }
        } else {
            if (splits && splits.length > 0) {
                splits.forEach(split => {
                    if (split.bought_at) {
                        const time = ensureTimestamp(split.bought_at);
                        if (time) {
                            markers.push({
                                time: time,
                                position: 'belowBar',
                                color: split.status === 'PENDING_SELL' ? '#eab308' : '#10b981',
                                shape: 'arrowUp',
                                text: '',
                                size: 1,
                            });
                        }
                    }
                });
            }
            if (tradeHistory && tradeHistory.length > 0) {
                tradeHistory.forEach(trade => {
                    if (trade.timestamp) {
                        const time = ensureTimestamp(trade.timestamp);
                        if (time) {
                            markers.push({ time: time, position: 'aboveBar', color: '#ef4444', shape: 'arrowDown', text: '', size: 1 });
                        }
                    }
                    if (trade.bought_at) {
                        const time = ensureTimestamp(trade.bought_at);
                        if (time) {
                            markers.push({ time: time, position: 'belowBar', color: '#10b981', shape: 'arrowUp', text: '', size: 1 });
                        }
                    }
                });
            }
        }

        markers.sort((a, b) => a.time - b.time);
        try {
            candlestickSeriesRef.current.setMarkers(markers);
        } catch (e) {
            console.error("Error setting markers:", e);
        }
    }, [splits, tradeHistory, candleData, isSimulating, simResult]);

    return (
        <div style={{
            marginBottom: '1rem',
            backgroundColor: '#1e293b',
            padding: '1rem',
            borderRadius: '0.5rem',
            border: '1px solid #334155'
        }}>
            <h3 style={{ margin: '0 0 1rem 0', color: '#f8fafc' }}>Price Chart {isSimulating ? '(SIMULATION MODE)' : ''}</h3>
            <div ref={chartContainerRef} style={{ position: 'relative', height: '400px', width: '100%' }}>
                {simResult && showResultPopup && (
                    <div style={{
                        position: 'absolute',
                        top: '10px',
                        left: '10px',
                        zIndex: 20,
                        backgroundColor: 'rgba(0, 0, 0, 0.8)',
                        padding: '1rem',
                        borderRadius: '0.5rem',
                        border: '1px solid #eab308',
                        color: 'white',
                        boxShadow: '0 4px 6px rgba(0,0,0,0.3)'
                    }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
                            <h4 style={{ margin: 0, color: '#eab308' }}>Simulation Result</h4>
                            <button
                                onClick={(e) => {
                                    e.stopPropagation(); // Prevent chart click
                                    // We can't clear simResult here because it's a prop.
                                    // But we can hide this specific popup if we had local state, 
                                    // or we can ask parent to clear.
                                    // The user asked for a button to "remove" it.
                                    // Since simResult drives the whole view, maybe just a local "visible" state for this popup?
                                    // Or call onSimulationComplete(null)? No, that exits the mode.
                                    // Let's use a local state to toggle visibility of this box.
                                    setShowResultPopup(false);
                                }}
                                style={{
                                    background: 'transparent',
                                    border: 'none',
                                    color: '#94a3b8',
                                    cursor: 'pointer',
                                    fontSize: '1.2rem',
                                    padding: '0 0.5rem'
                                }}
                            >
                                ×
                            </button>
                        </div>
                        <div style={{ display: 'grid', gridTemplateColumns: 'auto auto', gap: '0.5rem 1rem', fontSize: '0.9rem' }}>
                            <span style={{ color: '#94a3b8' }}>Realized Profit:</span>
                            <span style={{ fontWeight: 'bold', color: simResult.total_profit >= 0 ? '#10b981' : '#ef4444' }}>
                                ₩{Math.round(simResult.total_profit).toLocaleString()}
                            </span>

                            <span style={{ color: '#94a3b8' }}>Unrealized Profit:</span>
                            <span style={{ fontWeight: 'bold', color: (simResult.unrealized_profit || 0) >= 0 ? '#10b981' : '#ef4444' }}>
                                ₩{Math.round(simResult.unrealized_profit || 0).toLocaleString()}
                            </span>

                            <span style={{ color: '#94a3b8' }}>Trades:</span>
                            <span>{simResult.trade_count}</span>

                            <span style={{ color: '#94a3b8' }}>Final Balance:</span>
                            <span>₩{Math.round(simResult.final_balance).toLocaleString()}</span>
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
};

export default StrategyChart;
