import React, { useState } from 'react';
import { errorMessage, setStoredPassword, settingsApi } from '../../lib/api';
import './password-gate.css';

export default function PasswordGate({ onUnlocked }) {
    const [password, setPassword] = useState('');
    const [busy, setBusy] = useState(false);
    const [message, setMessage] = useState('');

    const handleSubmit = async (event) => {
        event.preventDefault();
        if (!password.trim()) return;
        setBusy(true);
        setMessage('');
        try {
            await settingsApi.authCheck(password.trim());
            setStoredPassword(password.trim());
            onUnlocked?.();
        } catch (err) {
            setMessage(errorMessage(err, '비밀번호가 올바르지 않습니다.'));
        } finally {
            setBusy(false);
        }
    };

    return (
        <div className="gate-backdrop" role="dialog" aria-modal="true" aria-labelledby="gate-title">
            <form className="gate-card" onSubmit={handleSubmit}>
                <div className="gate-eyebrow">SevenSplit</div>
                <h1 id="gate-title" className="gate-title">대시보드 비밀번호</h1>
                <p className="gate-help">
                    이 서버는 <code>DASHBOARD_PASSWORD</code>로 보호되어 있습니다. 설정을 바꾸거나 봇을 조작하려면 비밀번호가 필요합니다.
                </p>
                <label className="gate-label" htmlFor="gate-password">비밀번호</label>
                <input
                    id="gate-password"
                    className="gate-input"
                    type="password"
                    autoFocus
                    autoComplete="current-password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="서버에 설정한 비밀번호"
                />
                {message && <div className="gate-error">{message}</div>}
                <button className="gate-submit" type="submit" disabled={busy || !password.trim()}>
                    {busy ? '확인 중…' : '잠금 해제'}
                </button>
            </form>
        </div>
    );
}
