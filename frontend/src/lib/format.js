export function formatKRW(value, { sign = false } = {}) {
    const num = Number(value);
    if (!Number.isFinite(num)) return '-';
    const rounded = Math.round(num);
    const text = `₩${Math.abs(rounded).toLocaleString('ko-KR')}`;
    if (rounded < 0) return `-${text}`;
    return sign && rounded > 0 ? `+${text}` : text;
}

export function formatPercent(rate, digits = 2) {
    const num = Number(rate);
    if (!Number.isFinite(num)) return '-';
    return `${(num * 100).toFixed(digits)}%`;
}

export function formatWithCommas(digitsOnly) {
    if (digitsOnly === null || digitsOnly === undefined) return '';
    const text = String(digitsOnly).replace(/\D/g, '');
    return text.replace(/\B(?=(\d{3})+(?!\d))/g, ',');
}

export function parseCommaNumber(text) {
    const num = parseFloat(String(text ?? '').replace(/,/g, ''));
    return Number.isFinite(num) ? num : 0;
}

export function modeLabel(mode) {
    return mode === 'REAL' ? '실거래' : '모의 투자';
}
