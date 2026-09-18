import React, { useState } from 'react';
import { errorMessage, getStoredPassword, setStoredPassword, settingsApi } from '../../lib/api';
import { formatKRW, formatWithCommas, modeLabel, parseCommaNumber } from '../../lib/format';
import './settings.css';

export default function SettingsPage({ settings, passwordRequired, onChanged, onNavigate }) {
    if (!settings) {
        return <div className="settings-page"><p className="settings-loading">설정을 불러오는 중…</p></div>;
    }
    return (
        <div className="settings-page">
            <header className="settings-head">
                <h1>설정</h1>
                <p>실행 방식, 업비트 연결, 모의 투자 잔고를 여기서 관리합니다. 바꾼 내용은 바로 서버에 저장됩니다.</p>
            </header>

            <ModeSection settings={settings} onChanged={onChanged} />
            <KeysSection settings={settings} onChanged={onChanged} />
            <PaperSection settings={settings} onChanged={onChanged} />
            <BootSection settings={settings} onChanged={onChanged} />
            <SecuritySection passwordRequired={passwordRequired} />

            <footer className="settings-foot">
                <button type="button" className="btn-ghost" onClick={() => onNavigate('dashboard')}>← 대시보드로</button>
            </footer>
        </div>
    );
}

function Section({ id, title, lead, children, tone }) {
    return (
        <section className={`settings-section ${tone || ''}`} aria-labelledby={`${id}-title`}>
            <div className="settings-section-head">
                <h2 id={`${id}-title`}>{title}</h2>
                {lead && <p>{lead}</p>}
            </div>
            <div className="settings-section-body">{children}</div>
        </section>
    );
}

// ─────────────────────────────────────────────────────────────── mode
function ModeSection({ settings, onChanged }) {
    const [busy, setBusy] = useState(false);
    const [error, setError] = useState('');
    const running = settings.running_strategies || 0;
    const realAllowed = settings.has_keys && settings.key_valid !== false;

    const switchTo = async (target) => {
        if (target === settings.mode) return;
        if (target === 'REAL') {
            const ok = window.confirm('실거래 모드로 바꿉니다. 이후 시작하는 전략은 실제 업비트 계좌로 주문을 냅니다. 계속할까요?');
            if (!ok) return;
        }
        setBusy(true);
        setError('');
        try {
            await settingsApi.switchMode(target);
            await onChanged?.();
        } catch (err) {
            setError(errorMessage(err));
        } finally {
            setBusy(false);
        }
    };

    return (
        <Section
            id="mode"
            title="실행 방식"
            lead="모의 투자와 실거래는 전략 목록과 거래 기록이 서로 분리됩니다. 전환하면 해당 모드의 전략만 보입니다."
        >
            <div className="mode-switch">
                <button
                    type="button"
                    className={`mode-option paper ${settings.mode === 'DEV' ? 'active' : ''}`}
                    onClick={() => switchTo('DEV')}
                    disabled={busy || running > 0}
                >
                    <span className="mode-option-title">🧪 모의 투자</span>
                    <span className="mode-option-desc">실제 시세, 가상 잔고. 돈이 나가지 않습니다.</span>
                </button>
                <button
                    type="button"
                    className={`mode-option live ${settings.mode === 'REAL' ? 'active' : ''}`}
                    onClick={() => switchTo('REAL')}
                    disabled={busy || running > 0 || !realAllowed}
                >
                    <span className="mode-option-title">⚡ 실거래</span>
                    <span className="mode-option-desc">
                        {realAllowed ? '업비트 계좌로 실제 주문을 냅니다.' : '검증된 API 키를 먼저 저장하세요.'}
                    </span>
                </button>
            </div>
            <div className="settings-status-line">
                현재 <strong>{modeLabel(settings.mode)}</strong> 모드
                {running > 0 && (
                    <span className="text-warning"> · 실행 중인 전략이 {running}개 있어 전환할 수 없습니다. 먼저 정지하세요.</span>
                )}
            </div>
            {error && <div className="form-error">{error}</div>}
        </Section>
    );
}

// ─────────────────────────────────────────────────────────────── keys
function KeysSection({ settings, onChanged }) {
    const [editing, setEditing] = useState(!settings.has_keys);
    const [accessKey, setAccessKey] = useState('');
    const [secretKey, setSecretKey] = useState('');
    const [showSecret, setShowSecret] = useState(false);
    const [busy, setBusy] = useState('');
    const [error, setError] = useState('');
    const [notice, setNotice] = useState('');
    const [checkResult, setCheckResult] = useState(null);

    const reset = () => {
        setAccessKey('');
        setSecretKey('');
        setCheckResult(null);
        setError('');
    };

    const recheckStored = async () => {
        setBusy('recheck');
        setError('');
        setNotice('');
        try {
            const data = await settingsApi.validateKeys();
            if (data.valid) {
                setNotice(`연결 정상 · KRW 잔고 ${formatKRW(data.krw_balance)}${data.expire_at ? ` · 만료 ${data.expire_at.slice(0, 10)}` : ''}`);
            } else {
                setError(data.error || '키 검증에 실패했습니다.');
            }
            await onChanged?.();
        } catch (err) {
            setError(errorMessage(err));
        } finally {
            setBusy('');
        }
    };

    const checkNew = async () => {
        setBusy('check');
        setError('');
        setCheckResult(null);
        try {
            const data = await settingsApi.validateKeys(accessKey.trim(), secretKey.trim());
            if (data.valid) setCheckResult(data);
            else setError(data.error || '키 검증에 실패했습니다.');
        } catch (err) {
            setError(errorMessage(err));
        } finally {
            setBusy('');
        }
    };

    const saveNew = async () => {
        setBusy('save');
        setError('');
        try {
            await settingsApi.saveKeys(accessKey.trim(), secretKey.trim());
            await onChanged?.();
            setNotice('새 키를 저장했습니다.');
            setEditing(false);
            reset();
        } catch (err) {
            setError(errorMessage(err));
        } finally {
            setBusy('');
        }
    };

    const removeKeys = async () => {
        if (!window.confirm('저장된 업비트 키를 삭제할까요? 실거래 모드에서는 삭제할 수 없습니다.')) return;
        setBusy('delete');
        setError('');
        try {
            await settingsApi.deleteKeys();
            await onChanged?.();
            setNotice('키를 삭제했습니다.');
            setEditing(true);
        } catch (err) {
            setError(errorMessage(err));
        } finally {
            setBusy('');
        }
    };

    const validityBadge = settings.key_valid === true
        ? <span className="badge badge-success">검증됨</span>
        : settings.key_valid === false
            ? <span className="badge badge-danger">검증 실패</span>
            : <span className="badge badge-muted">미검증</span>;

    return (
        <Section
            id="keys"
            title="업비트 API 키"
            lead="키는 이 서버의 데이터베이스에만 저장됩니다. 화면과 API 응답에는 마지막 네 자리만 나옵니다."
        >
            {settings.has_keys && !editing && (
                <div className="keys-current">
                    <div className="keys-row">
                        <span className="keys-label">Access Key</span>
                        <code className="mono">{settings.access_key_masked}</code>
                        {validityBadge}
                        <span className="badge badge-muted">{settings.key_source === 'env' ? '환경변수에서 읽음' : '웹에서 저장'}</span>
                    </div>
                    <div className="keys-meta">
                        {settings.key_expire_at && <span>만료 {settings.key_expire_at.slice(0, 10)}</span>}
                        {settings.key_last_validated_at && <span>마지막 검증 {new Date(settings.key_last_validated_at).toLocaleString('ko-KR')}</span>}
                    </div>
                    <div className="keys-actions">
                        <button type="button" className="btn-ghost" onClick={recheckStored} disabled={!!busy}>
                            {busy === 'recheck' ? '확인 중…' : '연결 다시 확인'}
                        </button>
                        <button type="button" className="btn-ghost" onClick={() => { setEditing(true); setNotice(''); }} disabled={!!busy}>
                            키 교체
                        </button>
                        <button type="button" className="btn-ghost danger" onClick={removeKeys} disabled={!!busy || settings.mode === 'REAL'}>
                            {busy === 'delete' ? '삭제 중…' : '삭제'}
                        </button>
                    </div>
                </div>
            )}

            {editing && (
                <div className="keys-form">
                    <div className="field">
                        <label htmlFor="set-access">Access Key</label>
                        <input id="set-access" className="mono" value={accessKey} onChange={(e) => { setAccessKey(e.target.value); setCheckResult(null); }} autoComplete="off" spellCheck={false} />
                    </div>
                    <div className="field">
                        <label htmlFor="set-secret">Secret Key</label>
                        <div className="field-inline">
                            <input id="set-secret" className="mono" type={showSecret ? 'text' : 'password'} value={secretKey} onChange={(e) => { setSecretKey(e.target.value); setCheckResult(null); }} autoComplete="off" spellCheck={false} />
                            <button type="button" className="btn-ghost small" onClick={() => setShowSecret((v) => !v)}>{showSecret ? '숨기기' : '보기'}</button>
                        </div>
                    </div>
                    {checkResult && (
                        <div className="check-result">
                            <div className="check-result-title">✓ 연결 확인</div>
                            <dl>
                                <div><dt>KRW 잔고</dt><dd>{formatKRW(checkResult.krw_balance)}</dd></div>
                                <div><dt>보유 코인</dt><dd>{checkResult.held_currencies?.length ? checkResult.held_currencies.join(', ') : '없음'}</dd></div>
                                <div><dt>키 만료</dt><dd>{checkResult.expire_at ? checkResult.expire_at.slice(0, 10) : '정보 없음'}</dd></div>
                            </dl>
                        </div>
                    )}
                    <div className="keys-actions">
                        {!checkResult ? (
                            <button type="button" className="btn-primary-lg" onClick={checkNew} disabled={!!busy || accessKey.trim().length < 10 || secretKey.trim().length < 10}>
                                {busy === 'check' ? '업비트에 확인 중…' : '연결 확인'}
                            </button>
                        ) : (
                            <button type="button" className="btn-primary-lg" onClick={saveNew} disabled={!!busy}>
                                {busy === 'save' ? '저장 중…' : '저장'}
                            </button>
                        )}
                        {settings.has_keys && (
                            <button type="button" className="btn-ghost" onClick={() => { setEditing(false); reset(); }} disabled={!!busy}>취소</button>
                        )}
                    </div>
                </div>
            )}

            {notice && <div className="form-notice">{notice}</div>}
            {error && <div className="form-error">{error}</div>}
        </Section>
    );
}

// ─────────────────────────────────────────────────────────────── paper balance
function PaperSection({ settings, onChanged }) {
    const [text, setText] = useState(formatWithCommas(Math.round(settings.paper_initial_krw || 0)));
    const [busy, setBusy] = useState(false);
    const [error, setError] = useState('');
    const [notice, setNotice] = useState('');
    const value = parseCommaNumber(text);
    const dirty = value !== Math.round(settings.paper_initial_krw || 0);

    const save = async () => {
        setBusy(true);
        setError('');
        setNotice('');
        try {
            await settingsApi.setPaperInitialKrw(value);
            await onChanged?.();
            setNotice('저장했습니다. 다음에 모의 투자 모드로 들어가거나 서버를 재시작할 때 이 금액으로 시작합니다.');
        } catch (err) {
            setError(errorMessage(err));
        } finally {
            setBusy(false);
        }
    };

    return (
        <Section id="paper" title="모의 투자 잔고" lead="모의 투자 모드에서 봇이 쓰는 가상 KRW의 시작 금액입니다.">
            <div className="paper-row">
                <div className="field">
                    <label htmlFor="paper-krw">시작 금액 (KRW)</label>
                    <input id="paper-krw" className="mono" inputMode="numeric" value={text} onChange={(e) => setText(formatWithCommas(e.target.value))} />
                </div>
                <button type="button" className="btn-primary-lg" onClick={save} disabled={busy || !dirty || value < 5000}>
                    {busy ? '저장 중…' : '저장'}
                </button>
            </div>
            {notice && <div className="form-notice">{notice}</div>}
            {error && <div className="form-error">{error}</div>}
        </Section>
    );
}

// ─────────────────────────────────────────────────────────────── boot behaviour
function BootSection({ settings, onChanged }) {
    const [busy, setBusy] = useState(false);
    const [error, setError] = useState('');
    const enabled = settings.resume_strategies_on_boot !== false;

    const toggle = async () => {
        setBusy(true);
        setError('');
        try {
            await settingsApi.setResumeOnBoot(!enabled);
            await onChanged?.();
        } catch (err) {
            setError(errorMessage(err));
        } finally {
            setBusy(false);
        }
    };

    return (
        <Section
            id="boot"
            title="재기동 시 동작"
            lead="서버나 컨테이너를 다시 띄웠을 때 실행 중이던 전략을 어떻게 할지 정합니다."
        >
            <div className="boot-row">
                <button type="button" className={`toggle ${enabled ? 'on' : ''}`} onClick={toggle} disabled={busy} aria-pressed={enabled}>
                    <span className="toggle-knob" />
                </button>
                <div>
                    <div className="boot-title">{enabled ? '자동 재개' : '정지 상태로 시작 (수동 재개)'}</div>
                    <div className="boot-desc">
                        {enabled
                            ? '실행 중이던 전략은 재기동 직후 그대로 이어서 돌아갑니다. 예기치 않은 재시작에도 매매가 끊기지 않습니다.'
                            : '모든 전략이 정지 상태로 올라옵니다. 매도 체결 동기화는 계속되고, 각 전략에서 시작을 눌러야 매수를 재개합니다. 코드 업데이트 배포 전에 끄세요.'}
                    </div>
                </div>
            </div>
            {settings.held_on_boot_ids?.length > 0 && (
                <div className="form-notice">
                    이번 기동에서 정지 상태로 시작한 전략이 {settings.held_on_boot_ids.length}개 있습니다 (ID {settings.held_on_boot_ids.join(', ')}). 대시보드에서 확인 후 시작하세요.
                </div>
            )}
            {error && <div className="form-error">{error}</div>}
        </Section>
    );
}

// ─────────────────────────────────────────────────────────────── security
function SecuritySection({ passwordRequired }) {
    const [cleared, setCleared] = useState(false);
    const hasStored = !!getStoredPassword();

    return (
        <Section id="security" title="보안" tone="muted">
            {passwordRequired ? (
                <>
                    <p className="settings-text">
                        이 서버는 대시보드 비밀번호로 보호되고 있습니다. 비밀번호를 바꾸려면 서버의 <code>DASHBOARD_PASSWORD</code> 환경변수를 수정하고 재시작하세요.
                    </p>
                    {hasStored && !cleared && (
                        <button type="button" className="btn-ghost" onClick={() => { setStoredPassword(''); setCleared(true); }}>
                            이 브라우저에 저장된 비밀번호 지우기
                        </button>
                    )}
                    {cleared && <div className="form-notice">지웠습니다. 다음 변경 요청 때 다시 묻습니다.</div>}
                </>
            ) : (
                <p className="settings-text">
                    비밀번호가 설정되어 있지 않습니다. 이 주소에 접근할 수 있는 사람은 누구나 설정을 바꾸고 봇을 조작할 수 있습니다.
                    외부에서 접근 가능한 서버라면 <code>DASHBOARD_PASSWORD</code> 환경변수를 설정하세요.
                </p>
            )}
        </Section>
    );
}
