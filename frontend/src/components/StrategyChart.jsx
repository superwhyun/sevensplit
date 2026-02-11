import { useEffect, useRef, useState } from 'react';
import { createChart, ColorType, CrosshairMode } from 'lightweight-charts';
import axios from 'axios';

const StrategyChart = ({ ticker, splits = [], config = {}, tradeHistory = [], trailingBuyState, systemEvents = [], nextBuyTargetPrice = null }) => {
    const chartContainerRef = useRef();
    const chartRef = useRef();
    const candlestickSeriesRef = useRef();
    const volumeSeriesRef = useRef();
    const gateSeriesRef = useRef();
    const nextTargetSeriesRef = useRef();
    const rsiSeries14Ref = useRef();
    const rsiSeries4Ref = useRef();
    const rsiCursorLineRef = useRef();
    const tickerRef = useRef(ticker);

    const rsiBuyLineRef = useRef();
    const rsiSellLineRef = useRef();

    // Trailing Buy Indicator Refs
    const lowestPriceLineRef = useRef();
    const triggerPriceLineRef = useRef();

    // Keep tickerRef in sync with props
    useEffect(() => {
        tickerRef.current = ticker;
    }, [ticker]);

    // Data State
    const [candleData, setCandleData] = useState([]);
    const [volumeData, setVolumeData] = useState([]);

    // Pagination State
    const [isLoadingMore, setIsLoadingMore] = useState(false);
    const [lastCandleTime, setLastCandleTime] = useState(null);

    // Scaling State
    const [isAutoScaling, setIsAutoScaling] = useState(true);

    // Helper: Parse exact UTC ISO string to Unix Timestamp
    const parseUTC = (utcString) => {
        if (!utcString) return null;
        // Ensure 'Z' if missing (backend usually sends ISO-like strings which are effectively UTC)
        const timeStr = utcString.endsWith('Z') || utcString.includes('+') ? utcString : utcString + 'Z';
        return new Date(timeStr).getTime() / 1000;
    };

    // Reset state when ticker changes
    useEffect(() => {
        setCandleData([]);
        setVolumeData([]);
        setLastCandleTime(null);
    }, [ticker]);

    // Calculate RSI (Dual: 14 and 4)
    const calculateDualRSI = (data) => {
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

    const isRsiMode = (mode) => {
        const normalized = (mode || '').toString().toUpperCase();
        return normalized === 'RSI' || normalized === 'ALL';
    };

    const fetchCandles = async (to = null, isHistory = false) => {
        const interval = isRsiMode(config?.strategy_mode) ? 'days' : 'minutes/5';

        const API_BASE_URL = window.location.port === '5173'
            ? `http://${window.location.hostname}:8000`
            : '';

        try {
            const params = {
                market: ticker,
                count: 200,
                interval: interval
            };
            if (to) {
                params.to = to;
            }

            const response = await axios.get(`${API_BASE_URL}/candles`, { params });

            // Race condition check: discard if ticker changed
            if (ticker !== tickerRef.current) return;

            const data = response.data;

            if (!data || data.length === 0) return;

            // Sort by time ascending
            data.sort((a, b) => new Date(a.candle_date_time_utc) - new Date(b.candle_date_time_utc));

            const newCandles = data.map(d => ({
                time: parseUTC(d.candle_date_time_utc),
                open: d.opening_price,
                high: d.high_price,
                low: d.low_price,
                close: d.trade_price,
            })).filter(c => c.time !== null);

            const newVolumes = data.map(d => ({
                time: parseUTC(d.candle_date_time_utc),
                value: d.candle_acc_trade_volume,
                color: d.trade_price >= d.opening_price ? '#26a69a' : '#ef5350'
            })).filter(v => v.time !== null);

            if (isHistory) {
                // Prepend data
                setCandleData(prev => {
                    if (prev.length === 0) return newCandles;
                    const firstExistingTime = prev[0].time;
                    const uniqueNew = newCandles.filter(c => c.time < firstExistingTime);
                    return [...uniqueNew, ...prev];
                });
                setVolumeData(prev => {
                    if (prev.length === 0) return newVolumes;
                    const firstExistingTime = prev[0].time;
                    const uniqueNew = newVolumes.filter(v => v.time < firstExistingTime);
                    return [...uniqueNew, ...prev];
                });
            } else {
                // Initial load or normal refresh
                setCandleData(prev => {
                    if (prev.length === 0) return newCandles;
                    // Merge new candles at the end
                    const lastExistingTime = prev[prev.length - 1].time;
                    const uniqueNew = newCandles.filter(c => c.time > lastExistingTime);
                    return [...prev, ...uniqueNew];
                });
                setVolumeData(prev => {
                    if (prev.length === 0) return newVolumes;
                    const lastExistingTime = prev[prev.length - 1].time;
                    const uniqueNew = newVolumes.filter(v => v.time > lastExistingTime);
                    return [...prev, ...uniqueNew];
                });
            }

        } catch (error) {
            console.error("Error fetching candles:", error);
        } finally {
            setIsLoadingMore(false);
        }
    };

    // Initial Fetch & Polling
    useEffect(() => {
        if (ticker) {
            // Initial Fetch
            fetchCandles();
            // Polling
            const interval = setInterval(() => fetchCandles(), 60000);
            return () => clearInterval(interval);
        }
    }, [ticker, config?.strategy_mode, config?.use_trailing_buy]);

    // Infinite Scroll Logic
    useEffect(() => {
        if (!chartRef.current) return;

        const handleVisibleLogicalRangeChange = (newVisibleLogicalRange) => {
            if (newVisibleLogicalRange === null) return;

            // If scrolled close to the start (left side)
            if (newVisibleLogicalRange.from < 30 && !isLoadingMore) {
                if (candleData.length > 0) {
                    const firstTime = candleData[0].time;
                    // Convert unix timestamp back to ISO UTC string for API
                    const toTime = new Date(firstTime * 1000).toISOString();

                    if (lastCandleTime !== toTime) {
                        setIsLoadingMore(true);
                        setLastCandleTime(toTime);
                        fetchCandles(toTime, true);
                    }
                }
            }
        };

        chartRef.current.timeScale().subscribeVisibleLogicalRangeChange(handleVisibleLogicalRangeChange);

        return () => {
            if (chartRef.current) {
                chartRef.current.timeScale().unsubscribeVisibleLogicalRangeChange(handleVisibleLogicalRangeChange);
            }
        };
    }, [candleData, isLoadingMore, lastCandleTime]);

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
                // Show RSI if mode is RSI OR if Trailing Buy is enabled (which uses 5m RSI)
                const showRSI = isRsiMode(config?.strategy_mode) || config?.use_trailing_buy === true;

                if (showRSI && rsiSeries14Ref.current) {
                    const { rsi14, rsi4 } = calculateDualRSI(candleData);
                    rsiSeries14Ref.current.setData(rsi14);

                    // RSI(4) Removed as per user request
                    // rsiSeries4Ref.current.setData(rsi4);

                    chartRef.current.priceScale('rsi').applyOptions({
                        autoScale: false,
                        minValue: 0,
                        maxValue: 100,
                        scaleMargins: { top: 0.6, bottom: 0.15 },
                        visible: true,
                        borderColor: '#ef4444',
                    });
                } else {
                    if (rsiSeries14Ref.current) rsiSeries14Ref.current.setData([]);
                    if (rsiSeries4Ref.current) rsiSeries4Ref.current.setData([]);
                }

                // Only fit content on FIRST load (length <= 200) to avoid jumping when loading history
                if (candleData.length <= 200) {
                    chartRef.current.timeScale().fitContent();
                }

            } catch (error) {
                console.error("[Chart] Error setting data:", error);
            }
        }
    }, [candleData, volumeData, config?.strategy_mode, config?.use_trailing_buy]);

    // Handle AutoScaling Toggle
    useEffect(() => {
        if (!chartRef.current) return;
        chartRef.current.priceScale('right').applyOptions({
            autoScale: isAutoScaling,
        });
    }, [isAutoScaling]);

    const targetSellLineRef = useRef();

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
            localization: {
                locale: 'ko-KR',
                timeFormatter: (time) => {
                    return new Date(time * 1000).toLocaleString('ko-KR', {
                        timeZone: 'Asia/Seoul',
                        year: 'numeric',
                        month: '2-digit',
                        day: '2-digit',
                        hour: '2-digit',
                        minute: '2-digit',
                        second: '2-digit',
                        hour12: false
                    });
                }
            },
            timeScale: {
                borderColor: '#334155',
                timeVisible: true,
                secondsVisible: false,
                tickMarkFormatter: (time, tickMarkType) => {
                    const date = new Date(time * 1000);
                    const formatter = new Intl.DateTimeFormat('ko-KR', {
                        timeZone: 'Asia/Seoul',
                        month: '2-digit',
                        day: '2-digit',
                        hour: '2-digit',
                        minute: '2-digit',
                        hour12: false
                    });

                    const parts = formatter.formatToParts(date);
                    const getPart = (type) => parts.find(p => p.type === type)?.value;

                    if (tickMarkType === 2) { // Day
                        return `${getPart('month')}/${getPart('day')}`;
                    } else if (tickMarkType === 3) { // Time
                        return `${getPart('hour')}:${getPart('minute')}`;
                    } else {
                        const year = new Intl.DateTimeFormat('ko-KR', { timeZone: 'Asia/Seoul', year: 'numeric' }).format(date);
                        return `${year}-${getPart('month')}-${getPart('day')}`;
                    }
                },
            },
            width: chartContainerRef.current.clientWidth,
            height: 400,
        });

        // Initialize rsiCursorLineRef
        rsiCursorLineRef.current = null;

        chart.subscribeCrosshairMove(param => {
            // Update RSI Cursor Line
            if (rsiSeries14Ref.current && rsiCursorLineRef.current) {
                if (param.time && param.point) {
                    const data = param.seriesData.get(rsiSeries14Ref.current);
                    if (data && data.value !== undefined) {
                        rsiCursorLineRef.current.applyOptions({
                            price: data.value,
                            axisLabelVisible: true,
                        });
                    } else {
                        rsiCursorLineRef.current.applyOptions({ axisLabelVisible: false });
                    }
                } else {
                    rsiCursorLineRef.current.applyOptions({ axisLabelVisible: false });
                }
            }

            // Update Target Sell Price Line
            if (candlestickSeriesRef.current && targetSellLineRef.current && param.point) {

                // Get Price from Y coordinate
                const price = candlestickSeriesRef.current.coordinateToPrice(param.point.y);

                if (price && param.point.x >= 0 && param.point.y >= 0 &&
                    param.point.x <= chartContainerRef.current.clientWidth &&
                    param.point.y <= chartContainerRef.current.clientHeight) {

                    const sellRate = configRef.current?.sell_rate || 0.005; // Default 0.5%
                    const targetPrice = price * (1 + sellRate);

                    targetSellLineRef.current.applyOptions({
                        price: targetPrice,
                        title: `Target (+${(sellRate * 100).toFixed(1)}%)`,
                        axisLabelVisible: true,
                        lineVisible: true,
                    });
                } else {
                    // Hide if out of bounds
                    targetSellLineRef.current.applyOptions({
                        axisLabelVisible: false,
                        lineVisible: false
                    });
                }
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

        // Initialize Target Sell Line (Hidden initially)
        const targetSellLine = candlestickSeries.createPriceLine({
            price: 0,
            color: '#22d3ee', // Cyan
            lineWidth: 1,
            lineStyle: 1, // Dotted/ShortDash (1=Dotted in some versions, check LWC docs: 0=Solid, 1=Dotted, 2=Dashed, 3=LargeDashed)
            // LWC 3.8+: LineStyle.Dotted = 1
            axisLabelVisible: false,
            lineVisible: false,
            title: 'Target',
        });
        targetSellLineRef.current = targetSellLine;

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
                bottom: 0.35,
            },
        });

        // Buy-gate state strip (top band): colors blocked/watching intervals by time.
        const gateSeries = chart.addHistogramSeries({
            color: 'rgba(0,0,0,0)',
            priceFormat: { type: 'price', precision: 0, minMove: 1 },
            priceScaleId: 'gate',
            lastValueVisible: false,
            priceLineVisible: false,
            base: 0,
        });
        gateSeriesRef.current = gateSeries;
        chart.priceScale('gate').applyOptions({
            visible: false,
            autoScale: true,
            scaleMargins: {
                top: 0.0,
                bottom: 0.985, // ultra-thin ribbon at chart top
            },
        });

        const nextTargetSeries = chart.addLineSeries({
            color: '#22d3ee',
            lineWidth: 2,
            priceScaleId: 'right',
            lineStyle: 2, // dashed
            lastValueVisible: false,
            priceLineVisible: false,
        });
        nextTargetSeriesRef.current = nextTargetSeries;

        // Add RSI Series (Dual)
        const rsiSeries14 = chart.addLineSeries({
            color: '#8b5cf6', // Purple
            lineWidth: 2,
            priceScaleId: 'rsi',
            title: '', // Remove title to prevent axis label clutter
            priceFormat: { type: 'price', precision: 1, minMove: 0.1 },
            lastValueVisible: false, // Hide default static last value label
        });
        rsiSeries14Ref.current = rsiSeries14;

        // Create Dynamic Cursor Line for RSI
        // This line is invisible (transparent) but its axis label will show the cursor value
        const rsiCursorLine = rsiSeries14.createPriceLine({
            price: 50,
            color: 'transparent', // Hide the line
            lineWidth: 1,
            lineStyle: 2,
            axisLabelVisible: false, // Hidden by default, shown on hover
            axisLabelColor: '#8b5cf6', // Purple background
            axisLabelTextColor: '#ffffff',
        });
        rsiCursorLineRef.current = rsiCursorLine;

        const rsiSellLine = rsiSeries14.createPriceLine({
            price: configRef.current?.rsi_sell_min || 70.0,
            color: '#ef4444',
            lineWidth: 2,
            lineStyle: 2,
            axisLabelVisible: true,
            title: '80',
        });
        rsiSellLineRef.current = rsiSellLine;

        const rsiBuyLine = rsiSeries14.createPriceLine({
            price: configRef.current?.rsi_buy_max || 30.0,
            color: '#10b981',
            lineWidth: 2,
            lineStyle: 2,
            axisLabelVisible: true,
            title: '30',
        });
        rsiBuyLineRef.current = rsiBuyLine;

        const handleResize = () => {
            chart.applyOptions({ width: chartContainerRef.current.clientWidth });
        };

        window.addEventListener('resize', handleResize);

        return () => {
            window.removeEventListener('resize', handleResize);
            chart.remove();
        };
    }, []);

    // Keep config in ref for closure access in chart callbacks
    const configRef = useRef(config);
    useEffect(() => {
        configRef.current = config;
    }, [config]);

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

        if (splits && splits.length > 0) {
            splits.forEach(split => {
                if (split.bought_at) {
                    const time = ensureTimestamp(split.bought_at);
                    if (time) {
                        const isOpenPosition = split.status === 'BUY_FILLED' || split.status === 'PENDING_SELL';
                        markers.push({
                            time: time,
                            position: 'belowBar',
                            color: isOpenPosition ? '#f59e0b' : '#10b981',
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

        // Consolidate overlapping markers
        markers.sort((a, b) => a.time - b.time);

        const consolidatedMarkers = [];
        if (markers.length > 0) {
            let currentGroup = [markers[0]];

            for (let i = 1; i < markers.length; i++) {
                const prev = markers[i - 1];
                const curr = markers[i];

                // Check if same time AND same type (shape/color)
                // Note: We want to merge multiple BUYS at same time. 
                // We typically don't merge Buy + Sell (though unrelated in this strategy usually)
                if (curr.time === prev.time && curr.shape === prev.shape && curr.color === prev.color) {
                    currentGroup.push(curr);
                } else {
                    // Flush current group
                    const baseMarker = currentGroup[0];
                    if (currentGroup.length > 1) {
                        // Add text to indicate count, e.g. "x3"
                        const countText = `x${currentGroup.length}`;
                        // Append to existing text if any? Usually empty.
                        baseMarker.text = baseMarker.text ? `${baseMarker.text} (${countText})` : countText;
                        // Make slightly larger?
                        baseMarker.size = 2;
                    }
                    consolidatedMarkers.push(baseMarker);
                    currentGroup = [curr];
                }
            }
            // Flush last group
            const baseMarker = currentGroup[0];
            if (currentGroup.length > 1) {
                const countText = `x${currentGroup.length}`;
                baseMarker.text = baseMarker.text ? `${baseMarker.text} (${countText})` : countText;
                baseMarker.size = 2;
            }
            consolidatedMarkers.push(baseMarker);
        }

        try {
            candlestickSeriesRef.current.setMarkers(consolidatedMarkers);

        } catch (e) {
            console.error("Error setting markers:", e);
        }
    }, [splits, tradeHistory, candleData]);

    // Paint buy-gate intervals from system events (WATCH / BUY_GATE transitions)
    useEffect(() => {
        if (!gateSeriesRef.current || !candleData || candleData.length === 0) return;

        const eventToTs = (ev) => {
            const val = ev?.timestamp;
            if (!val) return null;
            if (typeof val === 'number') return val;
            return parseUTC(val);
        };

        const sortedEvents = [...(systemEvents || [])]
            .map((e) => ({ ...e, _ts: eventToTs(e) }))
            .filter((e) => e._ts !== null)
            .sort((a, b) => a._ts - b._ts);

        const colorByReason = (reason) => {
            if (!reason) return 'rgba(0,0,0,0)';
            if (reason === 'WATCH') return 'rgba(234, 179, 8, 0.75)'; // yellow
            if (reason === 'WAIT_TRADE_LIMIT') return 'rgba(239, 68, 68, 0.75)'; // red
            if (reason === 'WAIT_INSUFFICIENT_BUDGET') return 'rgba(249, 115, 22, 0.75)'; // orange
            if (reason === 'BUY_READY') return 'rgba(148, 163, 184, 0.42)'; // neutral-ready
            if (reason === 'WAIT_SEGMENT_MAX_SPLITS' || reason === 'WAIT_OUTSIDE_SEGMENT_RANGE' || reason === 'WAIT_SEGMENT_CONDITION') {
                return 'rgba(168, 85, 247, 0.78)'; // purple
            }
            if (reason === 'WAIT_PRICE_BELOW_TARGET') return 'rgba(14, 165, 233, 0.72)'; // blue
            return 'rgba(148, 163, 184, 0.7)'; // slate fallback
        };

        let watchActive = false;
        let gateCode = null;
        let eventIdx = 0;
        const stripData = [];

        for (const c of candleData) {
            while (eventIdx < sortedEvents.length && sortedEvents[eventIdx]._ts <= c.time) {
                const ev = sortedEvents[eventIdx];
                if (ev.event_type === 'WATCH_START') {
                    watchActive = true;
                } else if (ev.event_type === 'WATCH_END') {
                    watchActive = false;
                } else if (ev.event_type === 'BUY_GATE') {
                    const msg = String(ev.message || '');
                    const code = msg.split(':')[0]?.trim();
                    if (code === 'BUY_READY') {
                        gateCode = 'BUY_READY';
                    } else if (code && code.startsWith('WAIT_')) {
                        gateCode = code;
                    }
                }
                eventIdx += 1;
            }

            const reason = watchActive ? 'WATCH' : gateCode;
            stripData.push({
                time: c.time,
                value: reason ? 1 : 0,
                color: colorByReason(reason),
            });
        }

        gateSeriesRef.current.setData(stripData);
    }, [candleData, systemEvents]);

    // Draw next buy target as a time-series line using BUY_EXEC/TARGET_UPDATE event history.
    useEffect(() => {
        if (!nextTargetSeriesRef.current || !candleData || candleData.length === 0) return;

        const eventToTs = (ev) => {
            const val = ev?.timestamp;
            if (!val) return null;
            if (typeof val === 'number') return val;
            return parseUTC(val);
        };

        const parseTargetFromMessage = (msg) => {
            if (!msg) return null;
            const m = String(msg).match(/Next Buy Target:\s*([0-9]+(?:\.[0-9]+)?)/i);
            if (!m) return null;
            const parsed = Number(m[1]);
            return Number.isFinite(parsed) ? parsed : null;
        };

        const sortedEvents = [...(systemEvents || [])]
            .map((e) => ({ ...e, _ts: eventToTs(e) }))
            .filter((e) => e._ts !== null && (e.event_type === 'BUY_EXEC' || e.event_type === 'TARGET_UPDATE'))
            .sort((a, b) => a._ts - b._ts);

        let eventIdx = 0;
        let currentTarget = null;
        const targetLine = [];

        for (const c of candleData) {
            while (eventIdx < sortedEvents.length && sortedEvents[eventIdx]._ts <= c.time) {
                const t = parseTargetFromMessage(sortedEvents[eventIdx].message);
                if (String(sortedEvents[eventIdx].message || '').includes('Next Buy Target: NONE')) {
                    currentTarget = null;
                } else if (t !== null) {
                    currentTarget = t;
                }
                eventIdx += 1;
            }
            if (currentTarget !== null) {
                targetLine.push({ time: c.time, value: currentTarget });
            }
        }

        const latestTarget = Number(nextBuyTargetPrice);
        if (Number.isFinite(latestTarget) && latestTarget > 0 && targetLine.length > 0) {
            targetLine[targetLine.length - 1] = {
                time: targetLine[targetLine.length - 1].time,
                value: latestTarget,
            };
        } else if (Number.isFinite(latestTarget) && latestTarget > 0 && candleData.length > 0) {
            // Fallback when no BUY_EXEC event exists in the loaded window.
            targetLine.push({ time: candleData[candleData.length - 1].time, value: latestTarget });
        }

        nextTargetSeriesRef.current.setData(targetLine);
    }, [candleData, systemEvents, nextBuyTargetPrice]);

    // Draw Trailing Buy Lines
    useEffect(() => {
        if (!candlestickSeriesRef.current || !config) return;

        // Cleanup Helper
        const removeLines = () => {
            if (lowestPriceLineRef.current) {
                candlestickSeriesRef.current.removePriceLine(lowestPriceLineRef.current);
                lowestPriceLineRef.current = null;
            }
            if (triggerPriceLineRef.current) {
                candlestickSeriesRef.current.removePriceLine(triggerPriceLineRef.current);
                triggerPriceLineRef.current = null;
            }
        };

        if (trailingBuyState && trailingBuyState.isWatching && trailingBuyState.watchLowestPrice) {
            removeLines(); // Clear old to redraw (simple approach)

            const lowPrice = trailingBuyState.watchLowestPrice;
            const reboundPercent = config.trailing_buy_rebound_percent || 1.0;
            const triggerPrice = lowPrice * (1 + reboundPercent / 100);

            // 1. Lowest Price Line (Gray Dashed)
            lowestPriceLineRef.current = candlestickSeriesRef.current.createPriceLine({
                price: lowPrice,
                color: '#94a3b8',
                lineWidth: 1,
                lineStyle: 2, // Dashed
                axisLabelVisible: true,
                title: 'Lowest',
            });

            // 2. Trigger Price Line (Yellow Dashed)
            triggerPriceLineRef.current = candlestickSeriesRef.current.createPriceLine({
                price: triggerPrice,
                color: '#eab308',
                lineWidth: 2,
                lineStyle: 1, // Solid? or Dashed? Let's use ShortDash
                axisLabelVisible: true,
                title: `Buy Trigger (${reboundPercent}%)`,
            });
        } else {
            removeLines();
        }

    }, [trailingBuyState, config, candleData]); // Re-run when state/config changes

    // Update RSI Threshold Lines when config changes
    useEffect(() => {
        if (!config) return;

        const buyMax = config.rsi_buy_max ?? 30.0;
        const sellMin = config.rsi_sell_min ?? 70.0;

        if (rsiBuyLineRef.current) {
            rsiBuyLineRef.current.applyOptions({
                price: Number(buyMax),
            });
        }

        if (rsiSellLineRef.current) {
            rsiSellLineRef.current.applyOptions({
                price: Number(sellMin),
            });
        }
    }, [config]);

    return (
        <div style={{
            marginBottom: '1rem',
            backgroundColor: '#1e293b',
            padding: '1rem',
            borderRadius: '0.5rem',
            border: '1px solid #334155'
        }}>
            <h3 style={{ margin: '0 0 1rem 0', color: '#f8fafc' }}>Price Chart</h3>
            <div style={{ marginBottom: '0.5rem', display: 'flex', gap: '0.4rem', flexWrap: 'wrap', fontSize: '0.72rem' }}>
                <span style={{ color: '#94a3b8' }}>Buy Gate:</span>
                <span style={{ background: 'rgba(234, 179, 8, 0.55)', color: '#f8fafc', padding: '0.1rem 0.35rem', borderRadius: '0.25rem' }}>WATCH</span>
                <span style={{ background: 'rgba(14, 165, 233, 0.5)', color: '#f8fafc', padding: '0.1rem 0.35rem', borderRadius: '0.25rem' }}>Price Wait</span>
                <span style={{ background: 'rgba(168, 85, 247, 0.6)', color: '#f8fafc', padding: '0.1rem 0.35rem', borderRadius: '0.25rem' }}>Segment Wait</span>
                <span style={{ background: 'rgba(249, 115, 22, 0.6)', color: '#f8fafc', padding: '0.1rem 0.35rem', borderRadius: '0.25rem' }}>Budget Wait</span>
                <span style={{ background: 'rgba(239, 68, 68, 0.6)', color: '#f8fafc', padding: '0.1rem 0.35rem', borderRadius: '0.25rem' }}>Trade Limit</span>
                <span style={{ background: 'rgba(148, 163, 184, 0.42)', color: '#f8fafc', padding: '0.1rem 0.35rem', borderRadius: '0.25rem' }}>Buy Ready</span>
                <span style={{ background: 'rgba(34, 211, 238, 0.25)', color: '#67e8f9', border: '1px solid rgba(34, 211, 238, 0.65)', padding: '0.1rem 0.35rem', borderRadius: '0.25rem' }}>Next Target</span>
            </div>
            <div ref={chartContainerRef} style={{ position: 'relative', height: '400px', width: '100%', touchAction: 'none' }}>
                {/* Scale Lock Toggle Button */}
                <button
                    onClick={(e) => {
                        e.stopPropagation();
                        setIsAutoScaling(!isAutoScaling);
                    }}
                    title={isAutoScaling ? "Click to Lock Scale" : "Click to Auto Scale"}
                    style={{
                        position: 'absolute',
                        top: '8px',
                        right: '10px',
                        zIndex: 20,
                        backgroundColor: isAutoScaling ? 'rgba(30, 41, 59, 0.8)' : '#eab308',
                        color: isAutoScaling ? '#94a3b8' : 'white',
                        border: '1px solid #475569',
                        borderRadius: '4px',
                        padding: '2px 6px', // Smaller padding
                        cursor: 'pointer',
                        fontSize: '12px', // Smaller font
                        display: 'flex',
                        alignItems: 'center',
                        gap: '4px',
                        fontWeight: '600'
                    }}
                >
                    <span>{isAutoScaling ? '🔓' : '🔒'}</span>
                    <span style={{ fontSize: '11px' }}>{isAutoScaling ? 'Auto' : 'Locked'}</span>
                </button>
            </div>
        </div>
    );
};

export default StrategyChart;
