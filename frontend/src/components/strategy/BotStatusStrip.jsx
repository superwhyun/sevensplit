import React from 'react';
import { formatKRW, modeLabel } from '../../lib/format';

const STATE_META = {
    Stopped: { label: '정지됨', tone: 'muted', hint: '시작을 누르면 현재가에 첫 분할을 삽니다.' },
    'Max Limit': { label: '한도 도달', tone: 'warning', hint: '예산 또는 최대 보유 분할에 걸려 더 사지 않습니다. 매도는 계속 진행됩니다.' },
    Watching: { label: '감시 중', tone: 'amber', hint: 'RSI가 낮아 급락을 의심하고 있습니다. 반등이 확인되면 매수합니다.' },
    Normal: { label: '실행 중', tone: 'success', hint: '' },
    'Simulation (Live)': { label: '시뮬레이션 실행 중', tone: 'paper', hint: '' },
    'Simulation (Paused)': { label: '매수 일시정지', tone: 'amber', hint: '새 매수는 멈췄고, 걸어둔 매도 주문은 계속 체결을 기다립니다.' },
    'Simulation (Stopped)': { label: '정지됨', tone: 'muted', hint: '마지막 시뮬레이션 결과를 표시 중입니다. 다시 시작하면 새 결과로 바뀝니다.' },
};

const fmt = (n) => `₩${Math.round(Number(n)).toLocaleString('ko-KR')}`;

// The backend's status_msg is an English diagnostic string. Translate the known shapes;
// anything unrecognized is shown as-is.
const STATUS_MSG_RULES = [
    [/Price \(([\d.]+)\) is currently ABOVE target \(([\d.]+)\)/, (m) => `현재가 ${fmt(m[1])}가 다음 매수 목표 ${fmt(m[2])}보다 높아 하락을 기다립니다.`],
    [/Buy skipped due to insufficient budget/, () => '예산이 부족해 매수를 건너뜁니다.'],
    [/Buy skipped due to trade limit/, () => '24시간 거래 한도에 걸려 매수를 건너뜁니다.'],
    [/buy conditions satisfied/, () => '매수 조건이 충족되어 주문을 냅니다.'],
    [/Watch Mode: RSI\(5m\) ([\d.]+|None) is below threshold ([\d.]+)/, (m) => `감시 모드: 5분봉 RSI ${m[1]}가 기준 ${m[2]} 아래입니다. 반등을 기다립니다.`],
    [/Watch Mode: RSI Safe \(([\d.]+|None)\)\. Waiting for rebound: ([\d.]+)% \/ ([\d.]+)% Target/, (m) => `감시 모드: RSI 회복(${m[1]}). 최저가 대비 반등 ${m[2]}% / 목표 ${m[3]}%.`],
    [/outside configured segments/, () => '현재가가 설정한 가격 구간 밖이라 매수하지 않습니다.'],
    [/below minimum order size/, () => '매수 금액이 최소 주문 금액보다 작아 건너뜁니다.'],
];

function translateStatusMsg(msg) {
    if (!msg) return '';
    for (const [pattern, render] of STATUS_MSG_RULES) {
        const m = msg.match(pattern);
        if (m) return render(m);
    }
    return msg;
}

/**
 * One-line answer to "what is the bot doing right now?" shown above the chart.
 * @param {{ status: object, config: object, mode: string, nextBuyTarget: number|null }} props
 */
export default function BotStatusStrip({ status, config, mode, nextBuyTarget, runLabel }) {
    if (!status) return null;
    const meta = STATE_META[status.status] || STATE_META.Normal;
    const isRSI = (config?.strategy_mode || 'PRICE') === 'RSI';
    const price = Number(status.current_price) || 0;
    const counts = status.status_counts || {};
    const held = (counts.buy_filled || 0) + (counts.pending_sell || 0);
    const pendingSell = counts.pending_sell || 0;
    const pendingBuy = counts.pending_buy || 0;
    const unrealized = Number(status.total_profit_amount || 0);
    const unrealizedRate = Number(status.total_profit_rate || 0);
    const gap = nextBuyTarget && price ? ((nextBuyTarget - price) / price) * 100 : null;

    let nextBuyText = '-';
    let nextBuyDetail = '';
    if (isRSI) {
        nextBuyText = 'RSI 신호 대기';
        nextBuyDetail = '매일 09:00 확정 일봉 기준';
    } else if (nextBuyTarget) {
        nextBuyText = formatKRW(nextBuyTarget);
        nextBuyDetail = gap === null ? '' : `현재가 대비 ${gap > 0 ? '+' : ''}${gap.toFixed(2)}%`;
    } else if (status.is_running) {
        nextBuyText = '현재가에 즉시';
        nextBuyDetail = '포지션이 없어 바로 진입';
    }

    return (
        <section className={`bot-strip tone-${meta.tone}`} aria-label="봇 상태 요약">
            <div className="bot-strip-state">
                <span className="bot-strip-dot" aria-hidden="true" />
                <div>
                    <div className="bot-strip-label">{meta.label}</div>
                    <div className="bot-strip-sub">{modeLabel(mode)} · {isRSI ? 'RSI 반전' : '가격 그리드'}{runLabel ? ` · ${runLabel}` : ''}</div>
                </div>
            </div>

            <dl className="bot-strip-cells">
                <div>
                    <dt>다음 매수</dt>
                    <dd className="mono">{nextBuyText}</dd>
                    {nextBuyDetail && <span className="bot-strip-detail">{nextBuyDetail}</span>}
                </div>
                <div>
                    <dt>보유 분할</dt>
                    <dd>{held}개</dd>
                    <span className="bot-strip-detail">
                        매도 대기 {pendingSell}{pendingBuy ? ` · 매수 중 ${pendingBuy}` : ''}
                    </span>
                </div>
                <div>
                    <dt>평가 손익</dt>
                    <dd className={`mono ${unrealized > 0 ? 'up' : unrealized < 0 ? 'down' : ''}`}>
                        {formatKRW(unrealized, { sign: true })}
                    </dd>
                    <span className="bot-strip-detail">{held > 0 ? `${unrealizedRate >= 0 ? '+' : ''}${unrealizedRate.toFixed(2)}%` : '보유 없음'}</span>
                </div>
            </dl>

            {(meta.hint || status.status_msg) && (
                <div className="bot-strip-note" title={status.status_msg || ''}>
                    {meta.hint || translateStatusMsg(status.status_msg)}
                </div>
            )}
        </section>
    );
}
