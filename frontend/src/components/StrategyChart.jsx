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

    // Helper to parse KST ISO string to UTC timestamp (seconds)
    const parseKSTISO = (isoString) => {
        if (!isoString) return null;
        // Append +09:00 if missing to treat it as KST
        const timeStr = isoString.endsWith('Z') || isoString.includes('+') ? isoString : isoString + '+09:00';
        return new Date(timeStr).getTime() / 1000;
    };

    // Helper to parse UTC ISO string to UTC timestamp (seconds)
    const parseUTCISO = (isoString) => {
        if (!isoString) return null;
        // Append Z if missing to treat it as UTC
        const timeStr = isoString.endsWith('Z') || isoString.includes('+') ? isoString : isoString + 'Z';
        return new Date(timeStr).getTime() / 1000;
    };

    useEffect(() => {
        const fetchCandles = async () => {
            // Determine interval based on strategy mode
            // Default to 'minutes/5' for PRICE mode, 'days' for RSI mode
            const interval = config?.strategy_mode?.toUpperCase() === 'RSI' ? 'days' : 'minutes/5';

            // console.log(`[Chart] Fetching candles for ${ticker} (Mode: ${config?.strategy_mode}, Interval: ${interval})...`);

            // If running on Vite dev server (port 5173), point to backend port 8000.
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

                // Sort by timestamp ascending
                data.sort((a, b) => new Date(a.candle_date_time_kst) - new Date(b.candle_date_time_kst));

                const candleData = data.map(d => ({
                    // Use KST time with explicit +09:00 offset to ensure correct UTC timestamp
                    time: parseKSTISO(d.candle_date_time_kst),
                    open: d.opening_price,
                    high: d.high_price,
                    low: d.low_price,
                    close: d.trade_price,
                }));

                const volumeData = data.map(d => ({
                    time: parseKSTISO(d.candle_date_time_kst),
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
        // Helper to calculate RSI for a specific period using SMA (to match Backend)
        const calcRSI = (period) => {
            const results = [];

            for (let i = 0; i < data.length; i++) {
                if (i < period) {
                    continue;
                }

                // Calculate average gain/loss for the window
                let sumGain = 0;
                let sumLoss = 0;
                for (let j = 0; j < period; j++) {
                    const change = data[i - j].close - data[i - j - 1].close;
                    if (change > 0) sumGain += change;
                    else sumLoss -= change;
                }

                const avgGain = sumGain / period;
                const avgLoss = sumLoss / period;

                const rs = avgLoss === 0 ? (avgGain === 0 ? 0 : 100) : avgGain / avgLoss;
                const rsi = 100 - (100 / (1 + rs));

                results.push({ time: data[i].time, value: rsi });
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
                        color: d.value > 0 ? d.color : 'rgba(0,0,0,0)' // Hide zero volume?
                    }));
                    volumeSeriesRef.current.setData(displayVolumeData);
                }

                // Update RSI (Dual) - Only if in RSI mode
                if (config?.strategy_mode?.toUpperCase() === 'RSI' && rsiSeries14Ref.current && rsiSeries4Ref.current) {
                    const { rsi14, rsi4 } = calculateDualRSI(candleData);

                    // No offset needed if candleData.time is already UTC
                    const rsi14DisplayData = rsi14.map(d => ({
                        time: d.time,
                        value: d.value
                    }));
                    const rsi4DisplayData = rsi4.map(d => ({
                        time: d.time,
                        value: d.value
                    }));

                    rsiSeries14Ref.current.setData(rsi14DisplayData);
                    rsiSeries4Ref.current.setData(rsi4DisplayData);

                    // Force re-apply RSI scale options to ensure visibility
                    chartRef.current.priceScale('rsi').applyOptions({
                        autoScale: false,
                        minValue: 0,
                        maxValue: 100,
                        scaleMargins: {
                            top: 0.7,
                            bottom: 0,
                        },
                        visible: true,
                        borderColor: '#ef4444', // Red border for debugging
                    });
                } else if (config?.strategy_mode?.toUpperCase() !== 'RSI') {
                    // Clear RSI data if not in RSI mode
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
                console.log("[StrategyChart] Calling onChartClick with time:", param.time);
                onChartClickRef.current(param.time);
            } else {
                console.log("[StrategyChart] Click ignored (no time or handler)");
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
                top: 0.5, // Start at 50% height
                bottom: 0.3, // End at 70% height (aligned with price chart bottom)
            },
        });

        // Add RSI Series (Dual)
        const rsiSeries14 = chart.addLineSeries({
            color: '#8b5cf6', // Purple
            lineWidth: 2,
            priceScaleId: 'rsi',
            title: 'RSI(14)',
            priceFormat: {
                type: 'price',
                precision: 1,
                minMove: 0.1,
            },
        });
        rsiSeries14Ref.current = rsiSeries14;

        const rsiSeries4 = chart.addLineSeries({
            color: '#f59e0b', // Yellow/Orange
            lineWidth: 1,
            priceScaleId: 'rsi',
            title: 'RSI(4)',
            priceFormat: {
                type: 'price',
                precision: 1,
                minMove: 0.1,
            },
        });
        rsiSeries4Ref.current = rsiSeries4;

        // Add Threshold Lines to RSI Series
        rsiSeries14.createPriceLine({
            price: 70.0,
            color: '#ef4444',
            lineWidth: 1,
            lineStyle: 2, // Dashed
            axisLabelVisible: false,
        });
        rsiSeries14.createPriceLine({
            price: 30.0,
            color: '#10b981',
            lineWidth: 1,
            lineStyle: 2, // Dashed
            axisLabelVisible: false,
        });

        const handleResize = () => {
            chart.applyOptions({ width: chartContainerRef.current.clientWidth });
        };

        window.addEventListener('resize', handleResize);

        return () => {
            window.removeEventListener('resize', handleResize);
            chart.remove();
        };
    }, []);

    // Combined Marker Effect
    useEffect(() => {
        if (!candlestickSeriesRef.current) return;

        const markers = [];

        if (isSimulating) {
            if (simResult && simResult.trades) {
                simResult.trades.forEach(t => {
                    // Buy Marker
                    if (t.bought_at) {
                        // Simulation returns UTC naive strings, so use parseUTCISO
                        const buyTime = parseUTCISO(t.bought_at);
                        if (buyTime) {
                            markers.push({
                                time: buyTime,
                                position: 'belowBar',
                                color: '#10b981', // Green
                                shape: 'arrowUp',
                                text: '',
                                size: 1
                            });
                        }
                    }

                    // Sell Marker
                    if (t.timestamp) {
                        let sellTime = t.timestamp;
                        if (typeof sellTime === 'string') {
                            // Simulation returns UTC naive strings
                            sellTime = parseUTCISO(sellTime);
                        } else if (typeof sellTime === 'number') {
                            // If it's a number, assume it's already UTC seconds.
                            // No parsing needed, just assign.
                        }

                        if (sellTime) {
                            markers.push({
                                time: sellTime,
                                position: 'aboveBar',
                                color: '#ef4444', // Red
                                shape: 'arrowDown',
                                text: '',
                                size: 1
                            });
                        }
                    }
                });
            }
        } else {
            if (splits && splits.length > 0) {
                splits.forEach(split => {
                    if (split.bought_at) {
                        const time = parseKSTISO(split.bought_at);
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
                        const time = parseKSTISO(trade.timestamp);
                        if (time) {
                            markers.push({
                                time: time,
                                position: 'aboveBar',
                                color: '#ef4444',
                                shape: 'arrowDown',
                                text: '',
                                size: 1,
                            });
                        }
                    }

                    if (trade.bought_at) {
                        const time = parseKSTISO(trade.bought_at);
                        if (time) {
                            markers.push({
                                time: time,
                                position: 'belowBar',
                                color: '#10b981',
                                shape: 'arrowUp',
                                text: '',
                                size: 1,
                            });
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
                            <span style={{ color: '#94a3b8' }}>Total Profit:</span>
                            <span style={{ fontWeight: 'bold', color: simResult.total_profit >= 0 ? '#10b981' : '#ef4444' }}>
                                ₩{Math.round(simResult.total_profit).toLocaleString()}
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
