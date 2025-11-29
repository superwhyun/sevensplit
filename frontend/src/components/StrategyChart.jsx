import { useEffect, useRef, useState } from 'react';
import { createChart, ColorType, CrosshairMode } from 'lightweight-charts';
import axios from 'axios';

const StrategyChart = ({ ticker, splits = [], tradeHistory = [] }) => {
    const chartContainerRef = useRef();
    const chartRef = useRef();
    const candlestickSeriesRef = useRef();
    const volumeSeriesRef = useRef();
    const [candleData, setCandleData] = useState([]);

    useEffect(() => {
        const fetchCandles = async () => {
            try {
                // console.log(`[Chart] Fetching candles for ${ticker}...`);

                const response = await axios.get(`https://api.upbit.com/v1/candles/minutes/5?market=${ticker}&count=200`);

                const data = response.data.map(item => {
                    // KST 시간을 UTC로 파싱 (끝에 'Z' 붙여서)
                    const timestamp = Date.parse(item.candle_date_time_kst + 'Z') / 1000;

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

    useEffect(() => {
        if (candlestickSeriesRef.current && candleData.length > 0) {
            try {
                candlestickSeriesRef.current.setData(candleData);

                if (volumeSeriesRef.current) {
                    const volumeData = candleData.map(d => ({
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

    // Update markers when splits or tradeHistory change
    useEffect(() => {
        if (!candlestickSeriesRef.current) return;

        const markers = [];

        // 1. Active Splits (Buy Markers)
        if (splits && splits.length > 0) {
            splits.forEach(split => {
                if (split.bought_at) {
                    const timeStr = split.bought_at.endsWith('Z') ? split.bought_at : split.bought_at + 'Z';
                    const time = Date.parse(timeStr) / 1000;

                    if (!isNaN(time)) {
                        markers.push({
                            time: time,
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
                    const timeStr = trade.timestamp.endsWith('Z') ? trade.timestamp : trade.timestamp + 'Z';
                    const time = Date.parse(timeStr) / 1000;

                    if (!isNaN(time)) {
                        markers.push({
                            time: time,
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
                    const timeStr = trade.bought_at.endsWith('Z') ? trade.bought_at : trade.bought_at + 'Z';
                    const time = Date.parse(timeStr) / 1000;

                    if (!isNaN(time)) {
                        markers.push({
                            time: time,
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

        // Sort markers by time (required by lightweight-charts)
        markers.sort((a, b) => a.time - b.time);

        try {
            candlestickSeriesRef.current.setMarkers(markers);
        } catch (e) {
            console.error("Error setting markers:", e);
        }

    }, [splits, tradeHistory, candleData]); // Re-run when data changes

    return (
        <div style={{
            marginBottom: '1rem',
            backgroundColor: '#1e293b',
            padding: '1rem',
            borderRadius: '0.5rem',
            border: '1px solid #334155'
        }}>
            <h3 style={{ margin: '0 0 1rem 0', color: '#f8fafc' }}>Price Chart</h3>
            <div ref={chartContainerRef} style={{ position: 'relative', height: '400px', width: '100%' }} />
        </div>
    );
};

export default StrategyChart;
