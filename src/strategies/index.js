/**
 * 매매 전략 엔진 모음
 * 각 전략은 { signal: 'BUY'|'SELL'|'HOLD', reason: string, strength: number(0-1) } 반환
 */

// ─── 유틸 ─────────────────────────────────────────────────────────────────

function avg(arr) {
  return arr.reduce((a, b) => a + b, 0) / arr.length;
}

function sma(closes, period) {
  const results = [];
  for (let i = period - 1; i < closes.length; i++) {
    results.push(avg(closes.slice(i - period + 1, i + 1)));
  }
  return results;
}

// ─── 1. 이동평균 골든크로스 / 데드크로스 ─────────────────────────────────

/**
 * @param {number[]} closes  - 종가 배열 (오래된 → 최신 순)
 * @param {object} opts
 * @param {number} opts.shortPeriod  default 5
 * @param {number} opts.longPeriod   default 20
 */
export function maStrategy(closes, { shortPeriod = 5, longPeriod = 20 } = {}) {
  if (closes.length < longPeriod + 1) {
    return { signal: 'HOLD', reason: '데이터 부족', strength: 0 };
  }

  const shortMA = sma(closes, shortPeriod);
  const longMA = sma(closes, longPeriod);

  // 최근 2개 값으로 크로스 감지
  const prevShort = shortMA[shortMA.length - 2];
  const prevLong = longMA[longMA.length - 2];
  const currShort = shortMA[shortMA.length - 1];
  const currLong = longMA[longMA.length - 1];

  const spread = ((currShort - currLong) / currLong) * 100;

  if (prevShort <= prevLong && currShort > currLong) {
    return {
      signal: 'BUY',
      reason: `골든크로스 (MA${shortPeriod}=${currShort.toFixed(0)}, MA${longPeriod}=${currLong.toFixed(0)})`,
      strength: Math.min(Math.abs(spread) / 2, 1),
      meta: { shortMA: currShort, longMA: currLong, spread },
    };
  }

  if (prevShort >= prevLong && currShort < currLong) {
    return {
      signal: 'SELL',
      reason: `데드크로스 (MA${shortPeriod}=${currShort.toFixed(0)}, MA${longPeriod}=${currLong.toFixed(0)})`,
      strength: Math.min(Math.abs(spread) / 2, 1),
      meta: { shortMA: currShort, longMA: currLong, spread },
    };
  }

  return {
    signal: 'HOLD',
    reason: `MA 추세 유지 (spread: ${spread.toFixed(2)}%)`,
    strength: 0,
    meta: { shortMA: currShort, longMA: currLong, spread },
  };
}

// ─── 2. RSI 과매수 / 과매도 ───────────────────────────────────────────────

function calcRSI(closes, period = 14) {
  if (closes.length < period + 1) return null;

  let gains = 0, losses = 0;
  for (let i = closes.length - period; i < closes.length; i++) {
    const diff = closes[i] - closes[i - 1];
    if (diff >= 0) gains += diff;
    else losses -= diff;
  }

  const avgGain = gains / period;
  const avgLoss = losses / period;
  if (avgLoss === 0) return 100;
  const rs = avgGain / avgLoss;
  return 100 - 100 / (1 + rs);
}

/**
 * @param {number[]} closes
 * @param {object} opts
 * @param {number} opts.period     default 14
 * @param {number} opts.oversold   default 30
 * @param {number} opts.overbought default 70
 */
export function rsiStrategy(closes, { period = 14, oversold = 30, overbought = 70 } = {}) {
  const rsi = calcRSI(closes, period);
  if (rsi === null) {
    return { signal: 'HOLD', reason: '데이터 부족', strength: 0 };
  }

  if (rsi <= oversold) {
    const strength = (oversold - rsi) / oversold;
    return {
      signal: 'BUY',
      reason: `RSI 과매도 (${rsi.toFixed(1)} ≤ ${oversold})`,
      strength,
      meta: { rsi },
    };
  }

  if (rsi >= overbought) {
    const strength = (rsi - overbought) / (100 - overbought);
    return {
      signal: 'SELL',
      reason: `RSI 과매수 (${rsi.toFixed(1)} ≥ ${overbought})`,
      strength,
      meta: { rsi },
    };
  }

  return {
    signal: 'HOLD',
    reason: `RSI 중립 (${rsi.toFixed(1)})`,
    strength: 0,
    meta: { rsi },
  };
}

// ─── 3. 변동성 돌파 (래리 윌리엄스) ──────────────────────────────────────

/**
 * 전일 레인지의 k배 이상 상승 시 매수
 * @param {object} today   - { open, high, low, close }
 * @param {object} yesterday - { high, low }
 * @param {object} opts
 * @param {number} opts.k  default 0.5
 */
export function volatilityStrategy(today, yesterday, { k = 0.5 } = {}) {
  if (!today || !yesterday) {
    return { signal: 'HOLD', reason: '데이터 부족', strength: 0 };
  }

  const range = yesterday.high - yesterday.low;
  const targetBuy = today.open + range * k;
  const currentPrice = today.close ?? today.high; // 장중이면 현재가 사용

  if (currentPrice >= targetBuy) {
    const overshoot = (currentPrice - targetBuy) / range;
    return {
      signal: 'BUY',
      reason: `변동성 돌파 (목표가 ${targetBuy.toFixed(0)}, 현재 ${currentPrice.toFixed(0)})`,
      strength: Math.min(0.4 + overshoot * 0.6, 1),
      meta: { range, targetBuy, currentPrice, k },
    };
  }

  return {
    signal: 'HOLD',
    reason: `돌파 미달 (현재 ${currentPrice.toFixed(0)} < 목표 ${targetBuy.toFixed(0)})`,
    strength: 0,
    meta: { range, targetBuy, currentPrice, k },
  };
}

// ─── 복합 신호 집계 ───────────────────────────────────────────────────────

/**
 * 여러 전략 결과를 가중 합산하여 최종 신호 결정
 * @param {Array<{signal, strength}>} signals
 * @param {number} buyThreshold   default 0.4
 * @param {number} sellThreshold  default 0.4
 */
export function aggregateSignals(signals, buyThreshold = 0.4, sellThreshold = 0.4) {
  let buyScore = 0, sellScore = 0;
  for (const s of signals) {
    if (s.signal === 'BUY') buyScore += s.strength;
    if (s.signal === 'SELL') sellScore += s.strength;
  }
  buyScore /= signals.length;
  sellScore /= signals.length;

  if (buyScore >= buyThreshold && buyScore > sellScore) {
    return { signal: 'BUY', buyScore, sellScore };
  }
  if (sellScore >= sellThreshold && sellScore > buyScore) {
    return { signal: 'SELL', buyScore, sellScore };
  }
  return { signal: 'HOLD', buyScore, sellScore };
}
