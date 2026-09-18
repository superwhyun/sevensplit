import React, { useEffect, useMemo, useState } from 'react';
import { errorMessage, marketApi, settingsApi, strategyApi } from '../../lib/api';
import { formatKRW, formatWithCommas, parseCommaNumber } from '../../lib/format';
import { STRATEGY_PRESETS, buildStrategyPayload, derivePlan } from './presets';
import './setup.css';

const STEPS = [
    { key: 'connect', title: '업비트 연결', blurb: 'API 키를 넣거나 건너뛰기' },
    { key: 'mode', title: '실행 방식', blurb: '모의 투자 또는 실거래' },
    { key: 'strategy', title: '첫 전략', blurb: '코인, 예산, 프리셋' },
];

export default function SetupWizard({ settings, onFinished, onSkip, onSettingsChanged }) {
    const [step, setStep] = useState(0);
    const [connection, setConnection] = useState({
        hasKeys: !!settings?.has_keys,
        keyValid: settings?.key_valid ?? null,
        krwBalance: null,
        expireAt: settings?.key_expire_at || null,
    });
    const [mode, setMode] = useState(settings?.mode || 'DEV');

    const goNext = () => setStep((s) => Math.min(s + 1, STEPS.length - 1));
    const goBack = () => setStep((s) => Math.max(s - 1, 0));

    return (
        <div className="wizard">
            <aside className="wizard-side">
                <div className="wizard-brand">
                    <span className="wizard-mark" aria-hidden="true">7</span>
                    <div>
                        <div className="wizard-brand-name">SevenSplit</div>
                        <div className="wizard-brand-sub">분할 매수 · 자동 익절 봇</div>
                    </div>
                </div>
                <ol className="wizard-steps">
                    {STEPS.map((s, i) => (
                        <li key={s.key} className={`wizard-step ${i === step ? 'current' : ''} ${i < step ? 'done' : ''}`}>
                            <span className="wizard-step-index">{i < step ? '✓' : i + 1}</span>
                            <span>
                                <span className="wizard-step-title">{s.title}</span>
                                <span className="wizard-step-blurb">{s.blurb}</span>
                            </span>
                        </li>
                    ))}
                </ol>
                <p className="wizard-side-note">
                    3단계면 끝납니다. 나중에 설정 화면에서 언제든 바꿀 수 있습니다.
                </p>
                <button type="button" className="wizard-skip" onClick={onSkip}>
                    설정 없이 대시보드 보기 →
                </button>
            </aside>

            <main className="wizard-main">
                {step === 0 && (
                    <ConnectStep
                        settings={settings}
                        onConnected={(next) => {
                            setConnection(next);
                            onSettingsChanged?.();
                            goNext();
                        }}
                        onSkipKeys={() => {
                            setConnection((c) => ({ ...c, hasKeys: false, keyValid: null }));
                            setMode('DEV');
                            goNext();
                        }}
                    />
                )}
                {step === 1 && (
                    <ModeStep
                        connection={connection}
                        mode={mode}
                        currentMode={settings?.mode || 'DEV'}
                        onBack={goBack}
                        onChosen={(next) => {
                            setMode(next);
                            onSettingsChanged?.();
                            goNext();
                        }}
                    />
                )}
                {step === 2 && (
                    <StrategyStep
                        mode={mode}
                        onBack={goBack}
                        onFinished={onFinished}
                    />
                )}
            </main>
        </div>
    );
}

// ─────────────────────────────────────────────────────────────── step 1: keys
function ConnectStep({ settings, onConnected, onSkipKeys }) {
    const [accessKey, setAccessKey] = useState('');
    const [secretKey, setSecretKey] = useState('');
    const [showSecret, setShowSecret] = useState(false);
    const [checking, setChecking] = useState(false);
    const [saving, setSaving] = useState(false);
    const [result, setResult] = useState(null);
    const [error, setError] = useState('');
    const [useStored, setUseStored] = useState(!!settings?.has_keys);

    const canCheck = accessKey.trim().length > 10 && secretKey.trim().length > 10;

    const handleCheck = async () => {
        setChecking(true);
        setError('');
        setResult(null);
        try {
            const data = await settingsApi.validateKeys(accessKey.trim(), secretKey.trim());
            if (data.valid) {
                setResult(data);
            } else {
                setError(data.error || '키 검증에 실패했습니다.');
            }
        } catch (err) {
            setError(errorMessage(err));
        } finally {
            setChecking(false);
        }
    };

    const handleSave = async () => {
        setSaving(true);
        setError('');
        try {
            const saved = await settingsApi.saveKeys(accessKey.trim(), secretKey.trim());
            onConnected({
                hasKeys: true,
                keyValid: saved.key_valid !== false,
                krwBalance: result?.krw_balance ?? null,
                expireAt: saved.key_expire_at || result?.expire_at || null,
            });
        } catch (err) {
            setError(errorMessage(err));
        } finally {
            setSaving(false);
        }
    };

    const handleUseStored = async () => {
        setChecking(true);
        setError('');
        try {
            const data = await settingsApi.validateKeys();
            if (data.valid) {
                onConnected({ hasKeys: true, keyValid: true, krwBalance: data.krw_balance, expireAt: data.expire_at });
            } else {
                setError(data.error || '저장된 키가 더 이상 유효하지 않습니다. 새 키를 입력하세요.');
                setUseStored(false);
            }
        } catch (err) {
            setError(errorMessage(err));
            setUseStored(false);
        } finally {
            setChecking(false);
        }
    };

    return (
        <section className="wizard-panel">
            <header className="wizard-panel-head">
                <span className="wizard-kicker">1 / 3</span>
                <h1>업비트와 연결할까요?</h1>
                <p>
                    실거래를 하려면 업비트 Open API 키가 필요합니다. 키는 이 서버에만 저장되고, 화면에는 마지막 네 자리만 표시됩니다.
                    지금은 건너뛰고 모의 투자로 먼저 써 볼 수도 있습니다.
                </p>
            </header>

            {useStored && settings?.has_keys ? (
                <div className="wizard-card stored-keys">
                    <div className="stored-keys-row">
                        <span className="stored-keys-label">저장된 키</span>
                        <code className="mono">{settings.access_key_masked}</code>
                        <span className={`badge ${settings.key_valid === false ? 'badge-danger' : 'badge-muted'}`}>
                            {settings.key_valid === false ? '검증 실패' : settings.key_source === 'env' ? '환경변수' : '저장됨'}
                        </span>
                    </div>
                    <div className="wizard-actions">
                        <button type="button" className="btn-primary-lg" onClick={handleUseStored} disabled={checking}>
                            {checking ? '확인 중…' : '이 키 그대로 사용'}
                        </button>
                        <button type="button" className="btn-ghost" onClick={() => setUseStored(false)}>
                            다른 키 입력
                        </button>
                    </div>
                    {error && <div className="form-error">{error}</div>}
                </div>
            ) : (
                <div className="wizard-card">
                    <div className="field">
                        <label htmlFor="wiz-access">Access Key</label>
                        <input
                            id="wiz-access"
                            className="mono"
                            value={accessKey}
                            onChange={(e) => { setAccessKey(e.target.value); setResult(null); }}
                            placeholder="업비트에서 발급한 Access Key"
                            autoComplete="off"
                            spellCheck={false}
                        />
                    </div>
                    <div className="field">
                        <label htmlFor="wiz-secret">Secret Key</label>
                        <div className="field-inline">
                            <input
                                id="wiz-secret"
                                className="mono"
                                type={showSecret ? 'text' : 'password'}
                                value={secretKey}
                                onChange={(e) => { setSecretKey(e.target.value); setResult(null); }}
                                placeholder="Secret Key"
                                autoComplete="off"
                                spellCheck={false}
                            />
                            <button type="button" className="btn-ghost small" onClick={() => setShowSecret((v) => !v)}>
                                {showSecret ? '숨기기' : '보기'}
                            </button>
                        </div>
                    </div>
                    <p className="field-help">
                        업비트 → 마이페이지 → Open API 관리에서 <strong>자산조회</strong>와 <strong>주문</strong> 권한을 켜고,
                        이 서버의 IP를 허용 목록에 넣어야 합니다.
                    </p>

                    {result && (
                        <div className="check-result">
                            <div className="check-result-title">✓ 연결 확인</div>
                            <dl>
                                <div><dt>KRW 잔고</dt><dd>{formatKRW(result.krw_balance)}</dd></div>
                                <div><dt>보유 코인</dt><dd>{result.held_currencies?.length ? result.held_currencies.join(', ') : '없음'}</dd></div>
                                <div><dt>키 만료</dt><dd>{result.expire_at ? result.expire_at.slice(0, 10) : '정보 없음'}</dd></div>
                            </dl>
                        </div>
                    )}
                    {error && <div className="form-error">{error}</div>}

                    <div className="wizard-actions">
                        {!result ? (
                            <button type="button" className="btn-primary-lg" onClick={handleCheck} disabled={!canCheck || checking}>
                                {checking ? '업비트에 확인 중…' : '연결 확인'}
                            </button>
                        ) : (
                            <button type="button" className="btn-primary-lg" onClick={handleSave} disabled={saving}>
                                {saving ? '저장 중…' : '저장하고 다음 →'}
                            </button>
                        )}
                        <button type="button" className="btn-ghost" onClick={onSkipKeys}>
                            키 없이 모의 투자로 시작
                        </button>
                    </div>
                </div>
            )}
        </section>
    );
}

// ─────────────────────────────────────────────────────────────── step 2: mode
function ModeStep({ connection, mode, currentMode, onBack, onChosen }) {
    const [busy, setBusy] = useState(false);
    const [error, setError] = useState('');
    const realAllowed = connection.hasKeys && connection.keyValid !== false;

    const choose = async (target) => {
        setBusy(true);
        setError('');
        try {
            if (target !== currentMode) {
                await settingsApi.switchMode(target);
            }
            onChosen(target);
        } catch (err) {
            setError(errorMessage(err));
        } finally {
            setBusy(false);
        }
    };

    return (
        <section className="wizard-panel">
            <header className="wizard-panel-head">
                <span className="wizard-kicker">2 / 3</span>
                <h1>어떻게 돌릴까요?</h1>
                <p>언제든 설정에서 바꿀 수 있습니다. 실거래로 바꿀 때는 실행 중인 전략을 먼저 멈춰야 합니다.</p>
            </header>

            <div className="mode-grid">
                <button
                    type="button"
                    className={`mode-card paper ${mode === 'DEV' ? 'selected' : ''}`}
                    onClick={() => choose('DEV')}
                    disabled={busy}
                >
                    <span className="mode-card-icon">🧪</span>
                    <span className="mode-card-title">모의 투자</span>
                    <span className="mode-card-desc">
                        실제 시세로 가상 잔고를 굴립니다. 돈이 나가지 않으니 전략을 마음껏 실험하세요.
                    </span>
                    <span className="mode-card-foot">가상 잔고 {formatKRW(10000000)}부터 시작 (설정에서 변경)</span>
                </button>
                <button
                    type="button"
                    className={`mode-card live ${mode === 'REAL' ? 'selected' : ''} ${!realAllowed ? 'locked' : ''}`}
                    onClick={() => realAllowed && choose('REAL')}
                    disabled={busy || !realAllowed}
                >
                    <span className="mode-card-icon">⚡</span>
                    <span className="mode-card-title">실거래</span>
                    <span className="mode-card-desc">
                        업비트 계좌로 실제 주문을 냅니다. 봇이 사고파는 만큼 실제 돈이 움직입니다.
                    </span>
                    <span className="mode-card-foot">
                        {realAllowed
                            ? connection.krwBalance != null
                                ? `사용 가능 KRW ${formatKRW(connection.krwBalance)}`
                                : '검증된 API 키 사용'
                            : '검증된 API 키가 있어야 선택할 수 있습니다'}
                    </span>
                </button>
            </div>
            {error && <div className="form-error">{error}</div>}
            <div className="wizard-actions">
                <button type="button" className="btn-ghost" onClick={onBack} disabled={busy}>← 이전</button>
            </div>
        </section>
    );
}

// ─────────────────────────────────────────────────────────────── step 3: first strategy
function StrategyStep({ mode, onBack, onFinished }) {
    const [markets, setMarkets] = useState([]);
    const [popular, setPopular] = useState([]);
    const [ticker, setTicker] = useState('KRW-BTC');
    const [budgetText, setBudgetText] = useState('1,000,000');
    const [presetKey, setPresetKey] = useState('balanced');
    const [price, setPrice] = useState(null);
    const [priceError, setPriceError] = useState('');
    const [busy, setBusy] = useState('');
    const [error, setError] = useState('');

    useEffect(() => {
        let mounted = true;
        marketApi.tickers().then((data) => {
            if (!mounted) return;
            setMarkets(data.markets || []);
            setPopular(data.popular || []);
        }).catch(() => {});
        return () => { mounted = false; };
    }, []);

    useEffect(() => {
        let mounted = true;
        setPrice(null);
        setPriceError('');
        marketApi.price(ticker).then((data) => {
            if (mounted) setPrice(data.price);
        }).catch((err) => {
            if (mounted) setPriceError(errorMessage(err, '시세를 불러오지 못했습니다.'));
        });
        const timer = setInterval(() => {
            marketApi.price(ticker).then((data) => { if (mounted) setPrice(data.price); }).catch(() => {});
        }, 5000);
        return () => { mounted = false; clearInterval(timer); };
    }, [ticker]);

    const budget = parseCommaNumber(budgetText);
    const plan = useMemo(() => derivePlan({ budget, presetKey, currentPrice: price }), [budget, presetKey, price]);
    const coinName = useMemo(() => {
        const m = markets.find((x) => x.market === ticker);
        return m ? `${m.korean_name} (${ticker.replace('KRW-', '')})` : ticker;
    }, [markets, ticker]);

    const submit = async (startNow) => {
        if (!plan.isValid) return;
        if (startNow && mode === 'REAL') {
            const ok = window.confirm(
                `실거래 모드입니다.\n지금 시작하면 ${coinName}을(를) 현재가에 ${formatKRW(plan.perSplit)}만큼 즉시 시장가 매수합니다.\n계속할까요?`,
            );
            if (!ok) return;
        }
        setBusy(startNow ? 'start' : 'create');
        setError('');
        try {
            const payload = buildStrategyPayload({
                name: `${ticker.replace('KRW-', '')} ${plan.preset.label}`,
                ticker,
                budget,
                presetKey,
            });
            const created = await strategyApi.create(payload);
            if (startNow && created?.strategy_id) {
                if (mode === 'REAL') await strategyApi.start(created.strategy_id);
                else await strategyApi.startSimulation(created.strategy_id);
            }
            onFinished?.({ strategyId: created?.strategy_id, started: startNow });
        } catch (err) {
            setError(errorMessage(err));
        } finally {
            setBusy('');
        }
    };

    return (
        <section className="wizard-panel">
            <header className="wizard-panel-head">
                <span className="wizard-kicker">3 / 3</span>
                <h1>첫 전략을 만들어요</h1>
                <p>코인과 예산, 성향만 고르면 나머지는 프리셋이 채웁니다. 세부값은 나중에 전략 설정에서 조정할 수 있습니다.</p>
            </header>

            <div className="strategy-layout">
                <div className="wizard-card">
                    <div className="field">
                        <label htmlFor="wiz-ticker">코인</label>
                        <select id="wiz-ticker" value={ticker} onChange={(e) => setTicker(e.target.value)}>
                            {popular.length > 0 && (
                                <optgroup label="자주 쓰는 코인">
                                    {markets.filter((m) => popular.includes(m.market)).map((m) => (
                                        <option key={m.market} value={m.market}>{m.korean_name} · {m.market}</option>
                                    ))}
                                </optgroup>
                            )}
                            <optgroup label="전체 KRW 마켓">
                                {markets.filter((m) => !popular.includes(m.market)).map((m) => (
                                    <option key={m.market} value={m.market}>{m.korean_name} · {m.market}</option>
                                ))}
                                {markets.length === 0 && <option value="KRW-BTC">비트코인 · KRW-BTC</option>}
                            </optgroup>
                        </select>
                        <div className="field-help">
                            현재가 {price ? <strong className="mono">{formatKRW(price)}</strong> : priceError ? <span className="text-danger">{priceError}</span> : '불러오는 중…'}
                        </div>
                    </div>

                    <div className="field">
                        <label htmlFor="wiz-budget">이 전략에 쓸 예산 (KRW)</label>
                        <input
                            id="wiz-budget"
                            className="mono"
                            inputMode="numeric"
                            value={budgetText}
                            onChange={(e) => setBudgetText(formatWithCommas(e.target.value))}
                        />
                        <div className="field-help">봇은 이 금액을 넘겨서 사지 않습니다. {mode === 'REAL' ? '업비트 KRW 잔고 안에서 정하세요.' : '모의 잔고 안에서 정하세요.'}</div>
                    </div>

                    <div className="field">
                        <span className="field-label">투자 성향</span>
                        <div className="preset-list" role="radiogroup" aria-label="투자 성향">
                            {STRATEGY_PRESETS.map((p) => (
                                <button
                                    type="button"
                                    role="radio"
                                    aria-checked={presetKey === p.key}
                                    key={p.key}
                                    className={`preset-card ${presetKey === p.key ? 'selected' : ''}`}
                                    onClick={() => setPresetKey(p.key)}
                                >
                                    <span className="preset-head">
                                        <span className="preset-label">{p.label}</span>
                                        {p.recommended && <span className="badge badge-accent">추천</span>}
                                    </span>
                                    <span className="preset-tagline">{p.tagline}</span>
                                    <span className="preset-desc">{p.description}</span>
                                </button>
                            ))}
                        </div>
                    </div>
                </div>

                <aside className="plan-card">
                    <div className="plan-title">이렇게 움직입니다</div>
                    <ul className="plan-list">
                        <li>
                            <span className="plan-k">시작하면</span>
                            <span className="plan-v">{coinName}을(를) 현재가에 <b className="mono">{formatKRW(plan.perSplit)}</b> 매수</span>
                        </li>
                        <li>
                            <span className="plan-k">추가 매수</span>
                            <span className="plan-v">
                                {(plan.preset.buyRate * 100).toFixed(1)}% 떨어질 때마다 {formatKRW(plan.perSplit)}씩
                                {plan.nextBuy ? <> (다음: <b className="mono">{formatKRW(plan.nextBuy)}</b>)</> : null}
                            </span>
                        </li>
                        <li>
                            <span className="plan-k">익절</span>
                            <span className="plan-v">
                                각 매수분이 {(plan.preset.sellRate * 100).toFixed(1)}% 오르면 자동 매도
                                {plan.sellTarget ? <> (첫 목표: <b className="mono">{formatKRW(plan.sellTarget)}</b>)</> : null}
                            </span>
                        </li>
                        <li>
                            <span className="plan-k">한도</span>
                            <span className="plan-v">최대 {plan.preset.splits}분할, 총 <b className="mono">{formatKRW(plan.maxInvested)}</b>까지</span>
                        </li>
                        <li>
                            <span className="plan-k">버티는 폭</span>
                            <span className="plan-v">첫 매수가 대비 약 {(plan.coverageDrop * 100).toFixed(1)}% 하락까지 분할 매수</span>
                        </li>
                        <li>
                            <span className="plan-k">1회 순수익</span>
                            <span className="plan-v">수수료 제하고 약 <b className="mono">{formatKRW(plan.netPerTrade)}</b></span>
                        </li>
                    </ul>
                    {!plan.isValid && <div className="form-error">{plan.problem}</div>}
                    {error && <div className="form-error">{error}</div>}
                    <div className="plan-actions">
                        <button
                            type="button"
                            className={`btn-primary-lg ${mode === 'REAL' ? 'danger' : ''}`}
                            onClick={() => submit(true)}
                            disabled={!plan.isValid || !!busy || !price}
                        >
                            {busy === 'start' ? '시작하는 중…' : mode === 'REAL' ? '전략 만들고 실거래 시작' : '전략 만들고 모의 투자 시작'}
                        </button>
                        <button type="button" className="btn-ghost" onClick={() => submit(false)} disabled={!plan.isValid || !!busy}>
                            {busy === 'create' ? '만드는 중…' : '만들기만 하고 나중에 시작'}
                        </button>
                    </div>
                </aside>
            </div>

            <div className="wizard-actions">
                <button type="button" className="btn-ghost" onClick={onBack} disabled={!!busy}>← 이전</button>
            </div>
        </section>
    );
}
