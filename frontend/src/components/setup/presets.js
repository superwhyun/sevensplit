// Starter presets for the first strategy. Each maps to the classic price-grid strategy;
// the wizard only exposes budget + risk appetite and derives everything else.
export const STRATEGY_PRESETS = [
    {
        key: 'conservative',
        label: '보수형',
        tagline: '넓은 간격, 적은 분할',
        description: '1% 떨어질 때마다 사고 1% 오르면 팝니다. 거래 횟수가 적고 큰 하락에도 예산이 오래 버팁니다.',
        buyRate: 0.01,
        sellRate: 0.01,
        splits: 10,
    },
    {
        key: 'balanced',
        label: '균형형',
        tagline: '기본값, 대부분에게 적합',
        description: '0.5% 간격으로 사고팔며 20분할로 예산을 나눕니다. 변동성이 보통일 때 가장 무난합니다.',
        buyRate: 0.005,
        sellRate: 0.005,
        splits: 20,
        recommended: true,
    },
    {
        key: 'aggressive',
        label: '공격형',
        tagline: '촘촘한 간격, 많은 분할',
        description: '0.3% 간격으로 자주 거래합니다. 횡보장에서 수익 기회가 많지만 급락 시 예산이 빨리 소진됩니다.',
        buyRate: 0.003,
        sellRate: 0.003,
        splits: 30,
    },
];

export const MIN_ORDER_KRW = 5000;
export const DEFAULT_FEE_RATE = 0.0005;

export function findPreset(key) {
    return STRATEGY_PRESETS.find((p) => p.key === key) || STRATEGY_PRESETS[1];
}

export function derivePlan({ budget, presetKey, currentPrice }) {
    const preset = findPreset(presetKey);
    const safeBudget = Math.max(0, Number(budget) || 0);
    const rawPerSplit = preset.splits > 0 ? safeBudget / preset.splits : 0;
    const perSplit = Math.max(0, Math.floor(rawPerSplit / 1000) * 1000);
    const price = Number(currentPrice) || 0;

    const nextBuy = price > 0 ? price * (1 - preset.buyRate) : null;
    const sellTarget = price > 0 ? price * (1 + preset.sellRate) : null;
    const grossPerTrade = perSplit * preset.sellRate;
    const feePerTrade = perSplit * DEFAULT_FEE_RATE * 2;
    const netPerTrade = grossPerTrade - feePerTrade;
    const coverageDrop = preset.buyRate * (preset.splits - 1);

    return {
        preset,
        perSplit,
        maxInvested: perSplit * preset.splits,
        nextBuy,
        sellTarget,
        netPerTrade,
        coverageDrop,
        isValid: perSplit >= MIN_ORDER_KRW && safeBudget > 0,
        problem: safeBudget <= 0
            ? '예산을 입력하세요.'
            : perSplit < MIN_ORDER_KRW
                ? `분할당 금액이 ${MIN_ORDER_KRW.toLocaleString()}원 미만입니다. 예산을 늘리거나 분할이 적은 프리셋을 고르세요.`
                : '',
    };
}

export function buildStrategyPayload({ name, ticker, budget, presetKey }) {
    const plan = derivePlan({ budget, presetKey, currentPrice: 0 });
    const { preset, perSplit } = plan;
    return {
        name,
        ticker,
        budget: Number(budget),
        config: {
            strategy_mode: 'PRICE',
            investment_per_split: perSplit,
            min_price: 0,
            max_price: 0,
            buy_rate: preset.buyRate,
            sell_rate: preset.sellRate,
            fee_rate: DEFAULT_FEE_RATE,
            tick_interval: 1.0,
            rebuy_strategy: 'reset_on_clear',
            max_trades_per_day: 100,
            max_holdings: preset.splits,
            use_trailing_buy: false,
            use_adaptive_buy_control: false,
            price_segments: [
                {
                    min_price: 0,
                    max_price: 1000000000000,
                    investment_per_split: perSplit,
                    max_splits: preset.splits,
                },
            ],
        },
    };
}
