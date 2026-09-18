import React from 'react';
import { modeLabel } from '../../lib/format';
import './topbar.css';

export default function TopBar({ mode, view, onNavigate, passwordRequired, keyValid, hasKeys }) {
    const isReal = mode === 'REAL';
    return (
        <header className="topbar">
            <div className="topbar-inner">
                <button type="button" className="topbar-brand" onClick={() => onNavigate('dashboard')}>
                    <span className="topbar-mark" aria-hidden="true">7</span>
                    <span className="topbar-name">SevenSplit</span>
                </button>

                <nav className="topbar-nav" aria-label="주요 메뉴">
                    <button
                        type="button"
                        className={`topbar-link ${view === 'dashboard' ? 'active' : ''}`}
                        onClick={() => onNavigate('dashboard')}
                    >
                        대시보드
                    </button>
                    <button
                        type="button"
                        className={`topbar-link ${view === 'settings' ? 'active' : ''}`}
                        onClick={() => onNavigate('settings')}
                    >
                        설정
                    </button>
                </nav>

                <div className="topbar-status">
                    {hasKeys && keyValid === false && (
                        <span className="topbar-warn" title="저장된 업비트 키가 검증에 실패했습니다. 설정에서 확인하세요.">
                            키 확인 필요
                        </span>
                    )}
                    {passwordRequired && (
                        <span className="topbar-lock" title="비밀번호로 보호된 서버">🔒</span>
                    )}
                    <button
                        type="button"
                        className={`mode-pill ${isReal ? 'live' : 'paper'}`}
                        onClick={() => onNavigate('settings')}
                        title="클릭하면 설정에서 모드를 바꿀 수 있습니다"
                    >
                        <span className="mode-pill-dot" aria-hidden="true" />
                        {modeLabel(mode)}
                    </button>
                </div>
            </div>
            {isReal && (
                <div className="topbar-live-strip" role="status">
                    실거래 모드입니다. 봇이 실제 자산으로 주문을 냅니다.
                </div>
            )}
        </header>
    );
}
