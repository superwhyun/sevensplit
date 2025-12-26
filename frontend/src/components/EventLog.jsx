import React, { useEffect, useState, useRef } from 'react';
import axios from 'axios';

const EventLog = ({ strategyId, apiBaseUrl }) => {
    const [events, setEvents] = useState([]);
    const [page, setPage] = useState(1);
    const [totalPages, setTotalPages] = useState(1);
    const [loading, setLoading] = useState(false);

    // Auto-refresh interval
    useEffect(() => {
        if (!strategyId) return;

        fetchEvents();
        const interval = setInterval(fetchEvents, 5000); // Poll every 5 seconds

        return () => clearInterval(interval);
    }, [strategyId, page]);

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
                <h3 style={{ margin: 0, fontSize: '1rem', color: '#f8fafc' }}>System Events</h3>
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
                                <span style={{ opacity: 0.7, fontSize: '0.75rem' }}>{new Date(event.timestamp).toLocaleString()}</span>
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
