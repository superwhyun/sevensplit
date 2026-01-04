import React, { useEffect, useState, useRef } from 'react';
import axios from 'axios';

const EventLog = ({ strategyId, apiBaseUrl, status, simulationEvents }) => {
    const [events, setEvents] = useState([]);
    const [page, setPage] = useState(1);
    const [totalPages, setTotalPages] = useState(1);
    const [loading, setLoading] = useState(false);

    // Filter and Paginate local events if in simulation mode
    useEffect(() => {
        if (simulationEvents) {
            const limit = 10;
            const start = (page - 1) * limit;
            const end = start + limit;

            // Sort by time descending (latest first)
            const sortedEvents = [...simulationEvents].sort((a, b) =>
                new Date(b.created_at || b.timestamp) - new Date(a.created_at || a.timestamp)
            );

            // Add ID for map key if missing
            const mappedEvents = sortedEvents.map((ev, idx) => ({
                ...ev,
                id: ev.id || `sim-${idx}`,
                timestamp: ev.created_at || ev.timestamp // Ensure consistent key
            }));

            setEvents(mappedEvents.slice(start, end));
            setTotalPages(Math.ceil(mappedEvents.length / limit));
        }
    }, [simulationEvents, page]);

    // Auto-refresh interval (Only if NOT in simulation mode)
    useEffect(() => {
        if (!strategyId || simulationEvents) return;

        fetchEvents();
        const interval = setInterval(fetchEvents, 5000); // Poll every 5 seconds

        return () => clearInterval(interval);
    }, [strategyId, page, simulationEvents]);

    const fetchEvents = async () => {
        try {
            // Don't set loading on poll to avoid flickering
            // setLoading(true); 
            const response = await axios.get(`${apiBaseUrl}/strategies/${strategyId}/events?page=${page}&limit=10`);
            setEvents(response.data.events);
            setTotalPages(response.data.total_pages);
            // setLoading(false);
        } catch (error) {
            console.error("Failed to fetch events:", error);
        }
    };

    const handlePrev = () => {
        if (page > 1) setPage(page - 1);
    };

    const handleNext = () => {
        if (page < totalPages) setPage(page + 1);
    };

    if (!strategyId) return null;

    // Helper to get color by level/type
    const getRowStyle = (event) => {
        // ... (unchanged)
        const style = {
            borderBottom: '1px solid #334155',
            padding: '0.5rem',
            fontSize: '0.85rem'
        };

        if (event.event_type.includes('WATCH')) {
            style.backgroundColor = 'rgba(234, 179, 8, 0.1)'; // Yellow tint
            style.color = '#eab308';
        } else if (event.level === 'WARNING' || event.level === 'ERROR') {
            style.backgroundColor = 'rgba(239, 68, 68, 0.1)'; // Red tint
            style.color = '#ef4444';
        } else {
            style.color = '#94a3b8';
        }
        return style;
    };

    const getStatusBadgeStyle = (status) => {
        const baseStyle = {
            padding: '0.1rem 0.4rem',
            borderRadius: '0.25rem',
            fontSize: '0.65rem',
            fontWeight: 'bold',
            textTransform: 'uppercase',
            marginLeft: '0.5rem'
        };

        switch (status) {
            case 'Watching':
                return { ...baseStyle, backgroundColor: 'rgba(234, 179, 8, 0.2)', color: '#facc15', border: '1px solid rgba(234, 179, 8, 0.4)' };
            case 'Max Limit':
                return { ...baseStyle, backgroundColor: 'rgba(239, 68, 68, 0.2)', color: '#f87171', border: '1px solid rgba(239, 68, 68, 0.4)' };
            case 'Stopped':
                return { ...baseStyle, backgroundColor: 'rgba(148, 163, 184, 0.2)', color: '#cbd5e1', border: '1px solid rgba(148, 163, 184, 0.4)' };
            default: // Normal
                return { ...baseStyle, backgroundColor: 'rgba(34, 197, 94, 0.2)', color: '#4ade80', border: '1px solid rgba(34, 197, 94, 0.4)' };
        }
    };

    const handleClearEvents = async () => {
        if (!window.confirm("Are you sure you want to clear all events for this strategy?")) return;

        try {
            await axios.delete(`${apiBaseUrl}/strategies/${strategyId}/events`);
            setEvents([]);
            setPage(1);
            fetchEvents();
        } catch (error) {
            alert("Failed to clear events: " + error.message);
        }
    };

    return (
        <div style={{
            backgroundColor: 'rgba(15, 23, 42, 0.5)',
            borderRadius: '0.5rem',
            border: '1px solid #334155',
            marginTop: '1rem',
            marginBottom: '1rem',
            padding: '1rem'
        }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                    <h3 style={{ margin: 0, fontSize: '1rem', color: '#f8fafc' }}>System Events</h3>
                    {status && (
                        <span style={getStatusBadgeStyle(status)}>{status}</span>
                    )}
                    <button
                        onClick={handleClearEvents}
                        title="Clear All Events"
                        style={{
                            background: 'none', border: 'none', color: '#64748b', cursor: 'pointer',
                            fontSize: '1rem', display: 'flex', alignItems: 'center', padding: '4px',
                            transition: 'color 0.2s',
                        }}
                        onMouseOver={(e) => e.currentTarget.style.color = '#ef4444'}
                        onMouseOut={(e) => e.currentTarget.style.color = '#64748b'}
                    >
                        🗑️
                    </button>
                </div>
                <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center', fontSize: '0.8rem' }}>
                    <button
                        onClick={handlePrev}
                        disabled={page === 1}
                        style={{ background: 'none', border: '1px solid #475569', color: 'white', borderRadius: '0.25rem', padding: '0.2rem 0.5rem', cursor: page === 1 ? 'not-allowed' : 'pointer', opacity: page === 1 ? 0.5 : 1 }}
                    >
                        &lt; Prev
                    </button>
                    <span style={{ color: '#94a3b8' }}>{page} / {totalPages || 1}</span>
                    <button
                        onClick={handleNext}
                        disabled={page >= totalPages}
                        style={{ background: 'none', border: '1px solid #475569', color: 'white', borderRadius: '0.25rem', padding: '0.2rem 0.5rem', cursor: page >= totalPages ? 'not-allowed' : 'pointer', opacity: page >= totalPages ? 0.5 : 1 }}
                    >
                        Next &gt;
                    </button>
                </div>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column' }}>
                {events.length === 0 ? (
                    <div style={{ padding: '1rem', textAlign: 'center', color: '#64748b' }}>No recent events</div>
                ) : (
                    events.map(event => (
                        <div key={event.id} style={getRowStyle(event)}>
                            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.2rem' }}>
                                <span style={{ fontWeight: 'bold' }}>[{event.event_type}]</span>
                                <span style={{ opacity: 0.7, fontSize: '0.75rem' }}>
                                    {new Date(event.timestamp).toLocaleString('ko-KR', { timeZone: 'Asia/Seoul', hour12: false })}
                                </span>
                            </div>
                            <div>{event.message}</div>
                        </div>
                    ))
                )}
            </div>
        </div>
    );
};

export default EventLog;
