import { useEffect, useRef, useState } from 'react';
import { createChart, ColorType, CrosshairMode } from 'lightweight-charts';
import axios from 'axios';

const StrategyChart = ({ ticker, splits = [], config = {}, tradeHistory = [], isSimulating = false, simResult, onSimulationComplete }) => {
    const chartContainerRef = useRef();
    const chartRef = useRef();
    const candlestickSeriesRef = useRef();
    const volumeSeriesRef = useRef();
    const [candleData, setCandleData] = useState([]);
    const [showResultPopup, setShowResultPopup] = useState(true);

    // Reset popup visibility when simResult changes
    useEffect(() => {
        if (simResult) setShowResultPopup(true);
    }, [simResult]);

    useEffect(() => {
        const fetchCandles = async () => {
            try {
                // console.log(`[Chart] Fetching candles for ${ticker}...`);

                const response = await axios.get(`https://api.upbit.com/v1/candles/minutes/5?market=${ticker}&count=200`);

                const data = response.data.map(item => {
                    // UTC 시간을 파싱 (끝에 'Z' 붙여서)
                    const timestamp = Date.parse(item.candle_date_time_utc + 'Z') / 1000;

                    return {
                        time: timestamp,
                        open: item.opening_price,
                        high: item.high_price,
                        low: item.low_price,
                        close: item.trade_price,
                        volume: item.candle_acc_trade_volume,
                    };
                }).sort((a, b) => a.time - b.time);

                setCandleData(data);
            } catch (error) {
                console.error("[Chart] Error:", error);
            }
        };

        if (ticker) {
            fetchCandles();
            const interval = setInterval(fetchCandles, 60000);
            return () => clearInterval(interval);
        }
    }, [ticker]);

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
                    top: 0.1,
                    bottom: 0.15,
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
                top: 0.9,
                bottom: 0,
            },
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

    // Ref to access latest isSimulating in event handler
    const isSimulatingRef = useRef(isSimulating);
    useEffect(() => { isSimulatingRef.current = isSimulating; }, [isSimulating]);

    const candleDataRef = useRef(candleData);
    useEffect(() => { candleDataRef.current = candleData; }, [candleData]);

    const configRef = useRef(config);
    useEffect(() => { configRef.current = config; }, [config]);

    // Attach click handler separately to access refs
    useEffect(() => {
        if (!chartRef.current) return;

        const clickHandler = async (param) => {
            if (!isSimulatingRef.current || !param.time || !candleDataRef.current.length) return;

            const clickTime = param.time;
            // clickTime is KST (shifted), find original UTC candle
            const KST_OFFSET = 9 * 60 * 60;
            const startIndex = candleDataRef.current.findIndex(c => (c.time + KST_OFFSET) === clickTime);

            if (startIndex === -1) return;

            // Convert clickTime back to UTC for logging
            const utcTime = clickTime - KST_OFFSET;
            console.log(`Starting simulation from index ${startIndex} (UTC: ${new Date(utcTime * 1000).toUTCString()}, KST: ${new Date(clickTime * 1000).toLocaleString()})`);

            try {
                const payload = {
                    strategy_config: configRef.current,
                    candles: candleDataRef.current,
                    start_index: startIndex,
                    ticker: ticker,
                    budget: 1000000 // Default or from props
                };

                // If running on Vite dev server (port 5173), point to backend port 8000.
                const API_BASE_URL = window.location.port === '5173'
                    ? `http://${window.location.hostname}:8000`
                    : '';

                const response = await axios.post(`${API_BASE_URL}/simulate`, payload);
                const result = response.data;

                if (onSimulationComplete) onSimulationComplete(result);

            } catch (error) {
                console.error("Simulation error:", error);
                alert("Simulation failed");
            }
        };

        chartRef.current.subscribeClick(clickHandler);

        return () => {
            if (chartRef.current) {
                try {
                    chartRef.current.unsubscribeClick(clickHandler);
                } catch (e) { /* ignore */ }
            }
        };
    }, [ticker]); // Re-bind if ticker changes, but refs handle updates

    // Clear sim state when exiting sim mode
    // No local state to clear anymore
    /*
    useEffect(() => {
        if (!isSimulating) {
            setSimResult(null);
            setSimMarkers([]);
        }
    }, [isSimulating]);
    */

    useEffect(() => {
        if (candlestickSeriesRef.current && candleData.length > 0) {
            try {
                // Shift to KST for display
                const KST_OFFSET = 9 * 60 * 60;
                const displayData = candleData.map(d => ({
                    ...d,
                    time: d.time + KST_OFFSET
                }));

                candlestickSeriesRef.current.setData(displayData);

                if (volumeSeriesRef.current) {
                    const volumeData = displayData.map(d => ({
                        time: d.time,
                        value: d.volume,
                        color: d.close >= d.open ? 'rgba(16, 185, 129, 0.5)' : 'rgba(239, 68, 68, 0.5)',
                    }));
                    volumeSeriesRef.current.setData(volumeData);
                }

                chartRef.current.timeScale().fitContent();
            } catch (error) {
                console.error("[Chart] Error setting data:", error);
            }
        }
    }, [candleData]);



    // Combined Marker Effect
    useEffect(() => {
        if (!candlestickSeriesRef.current) return;

        const markers = [];

        const KST_OFFSET = 9 * 60 * 60;

        if (isSimulating && simResult && simResult.trades) {
            simResult.trades.forEach(t => {
                // For simplicity, let's just mark the Sells (Red Arrows).
                // In simulation.py, 'timestamp' is the SELL time.
                let time = t.timestamp;
                // Handle string timestamp if necessary
                if (typeof time === 'string') {
                    time = Date.parse(time.endsWith('Z') ? time : time + 'Z') / 1000;
                }

                markers.push({
                    time: time + KST_OFFSET,
                    position: 'aboveBar',
                    color: '#ef4444',
                    shape: 'arrowDown',
                    text: `₩${Math.round(t.net_profit)}`,
                    size: 2
                });
            });
        } else {
            // 1. Active Splits (Buy Markers)
            if (splits && splits.length > 0) {
                splits.forEach(split => {
                    if (split.bought_at) {
                        let time;
                        if (typeof split.bought_at === 'number') {
                            time = split.bought_at;
                        } else {
                            const timeStr = split.bought_at.endsWith('Z') ? split.bought_at : split.bought_at + 'Z';
                            time = Date.parse(timeStr) / 1000;
                        }

                        if (!isNaN(time)) {
                            markers.push({
                                time: time + KST_OFFSET,
                                position: 'belowBar',
                                color: split.status === 'PENDING_SELL' ? '#eab308' : '#10b981', // Yellow if Pending Sell, else Green
                                shape: 'arrowUp',
                                text: '', // No text
                                size: 1,
                            });
                        }
                    }
                });
            }

            // 2. Trade History
            if (tradeHistory && tradeHistory.length > 0) {
                tradeHistory.forEach(trade => {
                    // Sell Marker
                    if (trade.timestamp) {
                        let time;
                        if (typeof trade.timestamp === 'number') {
                            time = trade.timestamp;
                        } else {
                            const timeStr = trade.timestamp.endsWith('Z') ? trade.timestamp : trade.timestamp + 'Z';
                            time = Date.parse(timeStr) / 1000;
                        }

                        if (!isNaN(time)) {
                            markers.push({
                                time: time + KST_OFFSET,
                                position: 'aboveBar',
                                color: '#ef4444', // Red
                                shape: 'arrowDown',
                                text: '', // No text
                                size: 1,
                            });
                        }
                    }

                    // Buy Marker (if available)
                    if (trade.bought_at) {
                        let time;
                        if (typeof trade.bought_at === 'number') {
                            time = trade.bought_at;
                        } else {
                            const timeStr = trade.bought_at.endsWith('Z') ? trade.bought_at : trade.bought_at + 'Z';
                            time = Date.parse(timeStr) / 1000;
                        }

                        if (!isNaN(time)) {
                            markers.push({
                                time: time + KST_OFFSET,
                                position: 'belowBar',
                                color: '#10b981', // Green (Completed trade buy was just a normal buy)
                                shape: 'arrowUp',
                                text: '', // No text
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
    }, [splits, tradeHistory, candleData, isSimulating, simResult]); // Re-run when data changes

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
