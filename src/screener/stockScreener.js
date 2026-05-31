/**
 * 종목 발굴 스크리너
 * 세 가지 방식 통합:
 *  1. 유니버스 스캔    — 코스피200 전체 MA/RSI 신호 스캔
 *  2. 조건 스크리너   — KIS API 거래량/등락률 상위 종목
 *  3. 멀티 필터       — 복합 조건(거래량 급증 + RSI + 시총 + 모멘텀)
 */

import { maStrategy, rsiStrategy, volatilityStrategy, aggregateSignals } from '../strategies/index.js';

// ── 코스피200 구성 종목 (주요 50개 샘플 — 실제 운용 시 전체 200개 사용) ──
export const KOSPI200_UNIVERSE = [
  '005930','000660','005380','035420','000270','051910','068270','005490',
  '035720','028260','012330','066570','003670','034730','017670','032640',
  '096770','011200','036570','010130','009150','015760','086790','018260',
  '009830','010950','011170','316140','003550','000100','030200','024110',
  '021240','011790','000810','097950','004020','010140','161390','047050',
  '002380','006400','001570','033780','139480','018880','011070','042660',
  '078930','008770',
];

// ── KIS API 조건 스크리너 ─────────────────────────────────────────────────

export class StockScreener {
  constructor(kisClient, config = {}) {
    this.client = kisClient;
    this.config = {
      // 유니버스 스캔 설정
      universe: config.universe ?? KOSPI200_UNIVERSE,
      universeTopN: config.universeTopN ?? 10,        // 스캔 후 상위 N종목 선정

      // 조건 스크리너 설정
      conditionTopN: config.conditionTopN ?? 20,       // 거래량/등락률 상위 N개 조회
      minVolume: config.minVolume ?? 500000,            // 최소 거래량
      minMarketCap: config.minMarketCap ?? 100_000_000_000, // 최소 시총 1000억

      // 멀티 필터 설정
      volumeSurgeRatio: config.volumeSurgeRatio ?? 2.0, // 거래량 급증 기준 (전일比 2배)
      rsiMin: config.rsiMin ?? 30,                      // RSI 하한 (과매도 회복)
      rsiMax: config.rsiMax ?? 55,                      // RSI 상한 (과매수 진입 전)
      momentum52wRatio: config.momentum52wRatio ?? 0.9, // 52주 신고가 90% 이상

      // 전략 옵션
      maOptions: config.maOptions ?? { shortPeriod: 5, longPeriod: 20 },
      rsiOptions: config.rsiOptions ?? { period: 14 },

      // 최대 동시 보유 후보 수
      maxCandidates: config.maxCandidates ?? 15,
      ...config,
    };

    this.candidates = new Map();   // code → CandidateInfo
    this.onUpdate = config.onUpdate ?? null;
    this.onLog = config.onLog ?? console.log;
    this._scanTimer = null;
    this._morningDone = false;
  }

  log(level, msg, data = null) {
    this.onLog?.({ time: new Date().toISOString(), level, msg, data });
    console[level === 'ERROR' ? 'error' : 'log'](`[SCREENER][${level}] ${msg}`, data ?? '');
  }

  // ── 스케줄러 시작/중지 ──────────────────────────────────────────────────

  start(intraIntervalMs = 60_000) {
    this.log('INFO', '스크리너 시작');
    this._checkAndRunMorning();
    this._scanTimer = setInterval(() => {
      this._checkAndRunMorning();
      this._runConditionScreener();
    }, intraIntervalMs);
  }

  stop() {
    clearInterval(this._scanTimer);
    this._scanTimer = null;
    this._morningDone = false;
    this.log('INFO', '스크리너 중지');
  }

  _checkAndRunMorning() {
    const now = new Date();
    const h = now.getHours(), m = now.getMinutes();
    const isPreMarket = (h === 8 && m >= 50) || (h === 9 && m === 0);
    const isNewDay = !this._morningDone || now.getDate() !== this._lastMorningDate;

    if (isPreMarket && isNewDay) {
      this._morningDone = true;
      this._lastMorningDate = now.getDate();
      this.runMorningScan();
    }
  }

  // ── 1. 장 시작 전 모닝 스캔 ────────────────────────────────────────────

  async runMorningScan() {
    this.log('INFO', `모닝 스캔 시작 — 유니버스 ${this.config.universe.length}종목`);
    const results = [];

    // API 요청 제한(초당 20건) 고려 — 배치로 나눠서 처리
    const batchSize = 10;
    for (let i = 0; i < this.config.universe.length; i += batchSize) {
      const batch = this.config.universe.slice(i, i + batchSize);
      const batchResults = await Promise.allSettled(
        batch.map(code => this._analyzeStock(code))
      );
      for (const r of batchResults) {
        if (r.status === 'fulfilled' && r.value) results.push(r.value);
      }
      await sleep(500); // 배치 간 딜레이
    }

    // 신호 강도 기준 정렬 → 상위 N개 선정
    results.sort((a, b) => b.signalStrength - a.signalStrength);
    const top = results.slice(0, this.config.universeTopN);

    this.log('INFO', `유니버스 스캔 완료 — ${results.length}개 분석, 상위 ${top.length}개 후보 선정`);
    top.forEach(c => this._addCandidate(c, 'UNIVERSE_SCAN'));
    return top;
  }

  // ── 2. 장중 조건 스크리너 ──────────────────────────────────────────────

  async _runConditionScreener() {
    try {
      await Promise.all([
        this._screenByVolume(),
        this._screenByChangeRate(),
      ]);
    } catch (e) {
      this.log('ERROR', '조건 스크리너 실패', e.message);
    }
  }

  /** 거래량 상위 종목 스크리닝 */
  async _screenByVolume() {
    const stocks = await this.client.getVolumeRanking(this.config.conditionTopN);
    const candidates = stocks.filter(s =>
      s.volume >= this.config.minVolume &&
      !this.candidates.has(s.code)
    );
    this.log('INFO', `거래량 상위 스캔 — ${candidates.length}개 신규 분석`);
    for (const s of candidates.slice(0, 5)) {
      const result = await this._analyzeStock(s.code);
      if (result && result.signal !== 'HOLD') {
        this._addCandidate(result, 'VOLUME_SCREENER');
      }
      await sleep(200);
    }
  }

  /** 등락률 상위 종목 스크리닝 */
  async _screenByChangeRate() {
    const stocks = await this.client.getChangeRateRanking(this.config.conditionTopN);
    const rising = stocks.filter(s =>
      s.changeRate > 2 &&      // 2% 이상 상승
      s.changeRate < 15 &&     // 급등주 제외
      !this.candidates.has(s.code)
    );
    for (const s of rising.slice(0, 5)) {
      const result = await this._analyzeStock(s.code);
      if (result && result.signal === 'BUY') {
        this._addCandidate(result, 'CHANGE_SCREENER');
      }
      await sleep(200);
    }
  }

  // ── 3. 멀티 필터 스크리닝 ──────────────────────────────────────────────

  async runMultiFilter(stockList) {
    this.log('INFO', `멀티 필터 스크리닝 — ${stockList.length}종목`);
    const passed = [];

    for (const s of stockList) {
      try {
        const score = await this._multiFilterScore(s);
        if (score >= 3) {  // 5개 필터 중 3개 이상 통과
          const analysis = await this._analyzeStock(s.code ?? s);
          if (analysis) {
            analysis.filterScore = score;
            passed.push(analysis);
          }
        }
        await sleep(150);
      } catch (e) {
        // 개별 종목 실패 무시
      }
    }

    passed.sort((a, b) => (b.filterScore ?? 0) - (a.filterScore ?? 0));
    passed.forEach(c => this._addCandidate(c, 'MULTI_FILTER'));
    this.log('INFO', `멀티 필터 완료 — ${passed.length}개 통과`);
    return passed;
  }

  async _multiFilterScore(code) {
    const today = new Date();
    const start = new Date(today - 100 * 86400000);
    const fmt = d => d.toISOString().slice(0, 10).replace(/-/g, '');

    const [price, candles] = await Promise.all([
      this.client.getPrice(code),
      this.client.getDailyCandles(code, fmt(start), fmt(today)),
    ]);

    let score = 0;
    const closes = candles.map(c => c.close);
    const volumes = candles.map(c => c.volume);

    // 필터 1: 거래량 급증 (최근 5일 평균 대비 현재)
    const recentVolAvg = volumes.slice(-6, -1).reduce((a, b) => a + b, 0) / 5;
    if (price.volume >= recentVolAvg * this.config.volumeSurgeRatio) score++;

    // 필터 2: RSI 구간 (30~55 — 과매도 회복 초입)
    const rsi = calcRSI(closes, 14);
    if (rsi && rsi >= this.config.rsiMin && rsi <= this.config.rsiMax) score++;

    // 필터 3: MA 정배열 (MA5 > MA20 > MA60)
    if (closes.length >= 60) {
      const ma5  = avg(closes.slice(-5));
      const ma20 = avg(closes.slice(-20));
      const ma60 = avg(closes.slice(-60));
      if (ma5 > ma20 && ma20 > ma60) score++;
    }

    // 필터 4: 52주 신고가 근접 (현재가 >= 52주 최고가 × 0.9)
    const high52w = Math.max(...closes.slice(-252));
    if (price.price >= high52w * this.config.momentum52wRatio) score++;

    // 필터 5: 최근 5일 상승 추세 (종가 > 5일 전 종가)
    if (closes.length >= 5 && closes[closes.length - 1] > closes[closes.length - 6]) score++;

    return score;
  }

  // ── 공통 종목 분석 ─────────────────────────────────────────────────────

  async _analyzeStock(code) {
    try {
      const today = new Date();
      const start = new Date(today - 100 * 86400000);
      const fmt = d => d.toISOString().slice(0, 10).replace(/-/g, '');

      const [price, candles] = await Promise.all([
        this.client.getPrice(code),
        this.client.getDailyCandles(code, fmt(start), fmt(today)),
      ]);

      if (candles.length < 21) return null;

      const closes = candles.map(c => c.close);
      const signals = [
        maStrategy(closes, this.config.maOptions),
        rsiStrategy(closes, this.config.rsiOptions),
      ];
      if (candles.length >= 2) {
        const todayCandle = { ...candles[candles.length - 1], close: price.price };
        signals.push(volatilityStrategy(todayCandle, candles[candles.length - 2]));
      }

      const agg = aggregateSignals(signals, 0.3, 0.3);
      const buySignalCount = signals.filter(s => s.signal === 'BUY').length;
      const signalStrength = agg.buyScore - agg.sellScore;

      return {
        code,
        name: price.name ?? code,
        price: price.price,
        changeRate: price.changeRate,
        volume: price.volume,
        signal: agg.signal,
        signalStrength,
        buySignalCount,
        signals,
        aggregate: agg,
        scannedAt: new Date().toISOString(),
      };
    } catch (e) {
      this.log('ERROR', `${code} 분석 실패`, e.message);
      return null;
    }
  }

  // ── 후보 관리 ──────────────────────────────────────────────────────────

  _addCandidate(info, source) {
    if (this.candidates.size >= this.config.maxCandidates) {
      // 신호 강도 가장 낮은 종목 제거
      const weakest = [...this.candidates.entries()]
        .sort((a, b) => a[1].signalStrength - b[1].signalStrength)[0];
      if (weakest && weakest[1].signalStrength < info.signalStrength) {
        this.candidates.delete(weakest[0]);
        this.log('INFO', `후보 교체: ${weakest[0]} → ${info.code}`);
      } else {
        return; // 더 약한 신호면 추가 안 함
      }
    }

    this.candidates.set(info.code, { ...info, source, addedAt: new Date().toISOString() });
    this.log('INFO', `후보 추가 [${source}] ${info.code} ${info.signal} (강도: ${info.signalStrength?.toFixed(2)})`);
    this.onUpdate?.(this.getCandidates());
  }

  removeCandidate(code) {
    this.candidates.delete(code);
    this.onUpdate?.(this.getCandidates());
  }

  getCandidates() {
    return [...this.candidates.values()];
  }

  getWatchList() {
    return [...this.candidates.keys()];
  }
}

// ── 유틸 ──────────────────────────────────────────────────────────────────

function sleep(ms) {
  return new Promise(r => setTimeout(r, ms));
}

function avg(arr) {
  return arr.reduce((a, b) => a + b, 0) / arr.length;
}

function calcRSI(closes, period = 14) {
  if (closes.length < period + 1) return null;
  let gains = 0, losses = 0;
  for (let i = closes.length - period; i < closes.length; i++) {
    const d = closes[i] - closes[i - 1];
    if (d >= 0) gains += d; else losses -= d;
  }
  const avgGain = gains / period;
  const avgLoss = losses / period;
  if (avgLoss === 0) return 100;
  return 100 - 100 / (1 + avgGain / avgLoss);
}
