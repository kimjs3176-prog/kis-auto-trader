/**
 * 자동매매 엔진
 * 전략 실행 → 리스크 체크 → 주문 실행 → 로그
 */

import { maStrategy, rsiStrategy, volatilityStrategy, aggregateSignals } from '../strategies/index.js';

export class TradingEngine {
  constructor(kisClient, config = {}) {
    this.client = kisClient;
    this.config = {
      watchList: config.watchList ?? [],       // 감시 종목 코드 배열
      maxPositionRatio: config.maxPositionRatio ?? 0.2,  // 1종목 최대 20%
      stopLossRate: config.stopLossRate ?? -0.05,        // -5% 손절
      takeProfitRate: config.takeProfitRate ?? 0.1,      // +10% 익절
      orderQtyRatio: config.orderQtyRatio ?? 0.1,        // 주문 시 현금의 10%
      strategies: config.strategies ?? ['ma', 'rsi', 'volatility'],
      maOptions: config.maOptions ?? { shortPeriod: 5, longPeriod: 20 },
      rsiOptions: config.rsiOptions ?? { period: 14, oversold: 30, overbought: 70 },
      volatilityK: config.volatilityK ?? 0.5,
      ...config,
    };
    this.isRunning = false;
    this.logs = [];
    this.onLog = config.onLog ?? console.log;
    this.onSignal = config.onSignal ?? null;
    this.onOrderFilled = config.onOrderFilled ?? null;
    this._timer = null;
    this._priceCache = {};
    this._candleCache = {};
  }

  log(level, msg, data = null) {
    const entry = { time: new Date().toISOString(), level, msg, data };
    this.logs.unshift(entry);
    if (this.logs.length > 500) this.logs.pop();
    this.onLog?.(entry);
    console[level === 'ERROR' ? 'error' : level === 'WARN' ? 'warn' : 'log'](
      `[${entry.time.slice(11, 19)}][${level}] ${msg}`,
      data ?? ''
    );
  }

  // ─── 시작 / 정지 ─────────────────────────────────────────────────────────

  async start(intervalMs = 60_000) {
    if (this.isRunning) return;
    this.isRunning = true;
    this.log('INFO', '자동매매 엔진 시작', { watchList: this.config.watchList });
    await this._cycle(); // 즉시 1회 실행
    this._timer = setInterval(() => this._cycle(), intervalMs);
  }

  stop() {
    this.isRunning = false;
    clearInterval(this._timer);
    this._timer = null;
    this.log('INFO', '자동매매 엔진 중지');
  }

  // ─── 메인 사이클 ─────────────────────────────────────────────────────────

  async _cycle() {
    if (!this.isRunning) return;
    this.log('INFO', `사이클 시작 — ${this.config.watchList.length}개 종목 점검`);

    let balance;
    try {
      balance = await this.client.getBalance();
    } catch (e) {
      this.log('ERROR', '잔고 조회 실패', e.message);
      return;
    }

    for (const code of this.config.watchList) {
      try {
        await this._processStock(code, balance);
      } catch (e) {
        this.log('ERROR', `${code} 처리 실패`, e.message);
      }
    }

    // 보유 종목 손절/익절 점검
    for (const pos of balance.positions) {
      await this._checkExitConditions(pos);
    }
  }

  async _processStock(code, balance) {
    // 1. 데이터 조회
    const price = await this.client.getPrice(code);
    this._priceCache[code] = price;

    const today = new Date();
    const start = new Date(today - 100 * 86400000);
    const fmt = (d) => d.toISOString().slice(0, 10).replace(/-/g, '');
    const candles = await this.client.getDailyCandles(code, fmt(start), fmt(today));
    this._candleCache[code] = candles;

    const closes = candles.map((c) => c.close);
    const signals = [];

    // 2. 전략 실행
    if (this.config.strategies.includes('ma')) {
      const s = maStrategy(closes, this.config.maOptions);
      signals.push(s);
      this.log('INFO', `[MA] ${code}`, s);
    }
    if (this.config.strategies.includes('rsi')) {
      const s = rsiStrategy(closes, this.config.rsiOptions);
      signals.push(s);
      this.log('INFO', `[RSI] ${code}`, s);
    }
    if (this.config.strategies.includes('volatility') && candles.length >= 2) {
      const today = candles[candles.length - 1];
      const yesterday = candles[candles.length - 2];
      const todayWithCurrent = { ...today, close: price.price };
      const s = volatilityStrategy(todayWithCurrent, yesterday, { k: this.config.volatilityK });
      signals.push(s);
      this.log('INFO', `[VOL] ${code}`, s);
    }

    if (signals.length === 0) return;

    // 3. 신호 집계
    const agg = aggregateSignals(signals);
    this.onSignal?.({ code, price: price.price, ...agg, signals });
    this.log('INFO', `[SIGNAL] ${code} → ${agg.signal}`, agg);

    // 4. 이미 보유 중인지 확인
    const existingPos = balance.positions.find((p) => p.code === code);

    // 5. 리스크 / 포지션 한도 체크
    if (agg.signal === 'BUY' && !existingPos) {
      const maxBuyAmt = balance.cash * this.config.maxPositionRatio;
      const buyAmt = balance.cash * this.config.orderQtyRatio;
      if (buyAmt > maxBuyAmt) {
        this.log('WARN', `${code} 포지션 한도 초과, 스킵`);
        return;
      }
      if (balance.cash < price.price) {
        this.log('WARN', `${code} 현금 부족, 스킵 (보유현금: ${balance.cash.toLocaleString()})`);
        return;
      }
      const qty = Math.floor(buyAmt / price.price);
      if (qty < 1) return;
      await this._placeOrder({ side: 'BUY', stockCode: code, qty, reason: agg });
    }

    if (agg.signal === 'SELL' && existingPos) {
      await this._placeOrder({
        side: 'SELL',
        stockCode: code,
        qty: existingPos.qty,
        reason: agg,
      });
    }
  }

  async _checkExitConditions(pos) {
    if (pos.profitRate <= this.config.stopLossRate * 100) {
      this.log('WARN', `[STOP-LOSS] ${pos.code} ${pos.profitRate.toFixed(2)}% → 손절 주문`);
      await this._placeOrder({ side: 'SELL', stockCode: pos.code, qty: pos.qty, reason: { signal: 'SELL', reason: '손절' } });
    } else if (pos.profitRate >= this.config.takeProfitRate * 100) {
      this.log('INFO', `[TAKE-PROFIT] ${pos.code} ${pos.profitRate.toFixed(2)}% → 익절 주문`);
      await this._placeOrder({ side: 'SELL', stockCode: pos.code, qty: pos.qty, reason: { signal: 'SELL', reason: '익절' } });
    }
  }

  async _placeOrder({ side, stockCode, qty, reason }) {
    try {
      const order = await this.client.placeOrder({ side, stockCode, qty, price: null });
      const entry = { ...order, reason };
      this.onOrderFilled?.(entry);
      this.log('INFO', `[ORDER] ${side} ${stockCode} x${qty}`, entry);
      return entry;
    } catch (e) {
      this.log('ERROR', `주문 실패 ${side} ${stockCode}`, e.message);
      return null;
    }
  }

  getSnapshot() {
    return {
      isRunning: this.isRunning,
      watchList: this.config.watchList,
      priceCache: this._priceCache,
      logs: this.logs.slice(0, 100),
    };
  }
}
