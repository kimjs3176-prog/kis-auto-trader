/**
 * KIS (Korea Investment & Securities) Open API Client
 * Docs: https://apiportal.koreainvestment.com
 */

const BASE_URL = 'https://openapi.koreainvestment.com:9443';

export class KISClient {
  constructor(config) {
    this.appKey = config.appKey;
    this.appSecret = config.appSecret;
    this.accountNo = config.accountNo;   // 계좌번호 앞 8자리
    this.accountSuffix = config.accountSuffix ?? '01'; // 계좌 상품코드
    this.accessToken = null;
    this.tokenExpiry = null;
    this.ws = null;
    this.wsApprovalKey = null;
    this.subscribers = {};
  }

  // ─── 인증 ────────────────────────────────────────────────────────────────

  async getAccessToken() {
    if (this.accessToken && Date.now() < this.tokenExpiry) {
      return this.accessToken;
    }
    const res = await fetch(`${BASE_URL}/oauth2/tokenP`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        grant_type: 'client_credentials',
        appkey: this.appKey,
        appsecret: this.appSecret,
      }),
    });
    if (!res.ok) throw new Error(`Token fetch failed: ${res.status}`);
    const data = await res.json();
    this.accessToken = data.access_token;
    // 만료 1분 전에 갱신하도록
    this.tokenExpiry = Date.now() + (data.expires_in - 60) * 1000;
    console.log('[KIS] Access token issued, expires in', data.expires_in, 's');
    return this.accessToken;
  }

  async revokeToken() {
    if (!this.accessToken) return;
    await fetch(`${BASE_URL}/oauth2/revokeP`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        appkey: this.appKey,
        appsecret: this.appSecret,
        token: this.accessToken,
      }),
    });
    this.accessToken = null;
    console.log('[KIS] Token revoked');
  }

  async getWSApprovalKey() {
    const res = await fetch(`${BASE_URL}/oauth2/Approval`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        grant_type: 'client_credentials',
        appkey: this.appKey,
        secretkey: this.appSecret,
      }),
    });
    const data = await res.json();
    this.wsApprovalKey = data.approval_key;
    return this.wsApprovalKey;
  }

  // ─── 공통 REST 헬퍼 ──────────────────────────────────────────────────────

  async request(method, path, { tr_id, params = {}, body = null } = {}) {
    const token = await this.getAccessToken();
    const url = new URL(`${BASE_URL}${path}`);
    if (method === 'GET') {
      Object.entries(params).forEach(([k, v]) => url.searchParams.set(k, v));
    }
    const headers = {
      'Content-Type': 'application/json; charset=utf-8',
      Authorization: `Bearer ${token}`,
      appkey: this.appKey,
      appsecret: this.appSecret,
      tr_id,
    };
    const res = await fetch(url.toString(), {
      method,
      headers,
      body: body ? JSON.stringify(body) : null,
    });
    const data = await res.json();
    if (data.rt_cd !== '0') {
      throw new Error(`[KIS API] ${data.msg_cd}: ${data.msg1}`);
    }
    return data;
  }

  // ─── 시세 조회 ───────────────────────────────────────────────────────────

  /** 주식 현재가 조회 */
  async getPrice(stockCode) {
    const data = await this.request('GET', '/uapi/domestic-stock/v1/quotations/inquire-price', {
      tr_id: 'FHKST01010100',
      params: {
        FID_COND_MRKT_DIV_CODE: 'J',
        FID_INPUT_ISCD: stockCode,
      },
    });
    const o = data.output;
    return {
      code: stockCode,
      price: Number(o.stck_prpr),
      open: Number(o.stck_oprc),
      high: Number(o.stck_hgpr),
      low: Number(o.stck_lwpr),
      volume: Number(o.acml_vol),
      changeRate: Number(o.prdy_ctrt),
    };
  }

  /** 일봉 데이터 조회 (최대 100일) */
  async getDailyCandles(stockCode, startDate, endDate) {
    const data = await this.request('GET', '/uapi/domestic-stock/v1/quotations/inquire-daily-price', {
      tr_id: 'FHKST01010400',
      params: {
        FID_COND_MRKT_DIV_CODE: 'J',
        FID_INPUT_ISCD: stockCode,
        FID_INPUT_DATE_1: startDate, // YYYYMMDD
        FID_INPUT_DATE_2: endDate,
        FID_PERIOD_DIV_CODE: 'D',
        FID_ORG_ADJ_PRC: '0',
      },
    });
    return data.output2.map((c) => ({
      date: c.stck_bsop_date,
      open: Number(c.stck_oprc),
      high: Number(c.stck_hgpr),
      low: Number(c.stck_lwpr),
      close: Number(c.stck_clpr),
      volume: Number(c.acml_vol),
    }));
  }

  // ─── 순위 / 스크리닝 ─────────────────────────────────────────────────────

  /** 거래량 상위 종목 조회 */
  async getVolumeRanking(topN = 30) {
    const data = await this.request('GET', '/uapi/domestic-stock/v1/quotations/volume-rank', {
      tr_id: 'FHPST01710000',
      params: {
        FID_COND_MRKT_DIV_CODE: 'J',
        FID_COND_SCR_DIV_CODE: '20171',
        FID_INPUT_ISCD: '0001',       // 코스피 전체
        FID_DIV_CLS_CODE: '0',
        FID_BLNG_CLS_CODE: '0',
        FID_TRGT_CLS_CODE: '111111111',
        FID_TRGT_EXLS_CLS_CODE: '000000',
        FID_INPUT_PRICE_1: '',
        FID_INPUT_PRICE_2: '',
        FID_VOL_CNT: '',
        FID_INPUT_DATE_1: '',
      },
    });
    return (data.output ?? []).slice(0, topN).map(s => ({
      code: s.mksc_shrn_iscd,
      name: s.hts_kor_isnm,
      price: Number(s.stck_prpr),
      volume: Number(s.acml_vol),
      changeRate: Number(s.prdy_ctrt),
    }));
  }

  /** 등락률 상위 종목 조회 */
  async getChangeRateRanking(topN = 30, direction = 'UP') {
    const data = await this.request('GET', '/uapi/domestic-stock/v1/quotations/inquire-daily-itemchartprice', {
      tr_id: 'FHPST01700000',
      params: {
        FID_COND_MRKT_DIV_CODE: 'J',
        FID_COND_SCR_DIV_CODE: direction === 'UP' ? '20170' : '20171',
        FID_INPUT_ISCD: '0001',
        FID_RANK_SORT_CLS_CODE: '0',
        FID_INPUT_CNT_1: String(topN),
        FID_PRC_CLS_CODE: '0',
        FID_INPUT_PRICE_1: '',
        FID_INPUT_PRICE_2: '',
        FID_VOL_CNT: '100000',
        FID_TRGT_CLS_CODE: '0',
        FID_TRGT_EXLS_CLS_CODE: '0',
        FID_DIV_CLS_CODE: '0',
        FID_RSFL_RATE1: '',
        FID_RSFL_RATE2: '',
      },
    });
    return (data.output ?? []).slice(0, topN).map(s => ({
      code: s.mksc_shrn_iscd,
      name: s.hts_kor_isnm,
      price: Number(s.stck_prpr),
      volume: Number(s.acml_vol),
      changeRate: Number(s.prdy_ctrt),
    }));
  }

  // ─── 잔고 / 계좌 ─────────────────────────────────────────────────────────

  /** 주식 잔고 조회 */
  async getBalance() {
    const data = await this.request('GET', '/uapi/domestic-stock/v1/trading/inquire-balance', {
      tr_id: 'TTTC8434R',
      params: {
        CANO: this.accountNo,
        ACNT_PRDT_CD: this.accountSuffix,
        AFHR_FLPR_YN: 'N',
        OFL_YN: '',
        INQR_DVSN: '02',
        UNPR_DVSN: '01',
        FUND_STTL_ICLD_YN: 'N',
        FNCG_AMT_AUTO_RDPT_YN: 'N',
        PRCS_DVSN: '01',
        CTX_AREA_FK100: '',
        CTX_AREA_NK100: '',
      },
    });
    return {
      cash: Number(data.output2[0]?.dnca_tot_amt ?? 0),
      totalEval: Number(data.output2[0]?.tot_evlu_amt ?? 0),
      positions: data.output1.map((p) => ({
        code: p.pdno,
        name: p.prdt_name,
        qty: Number(p.hldg_qty),
        avgPrice: Number(p.pchs_avg_pric),
        evalPrice: Number(p.prpr),
        evalProfit: Number(p.evlu_pfls_amt),
        profitRate: Number(p.evlu_pfls_rt),
      })),
    };
  }

  // ─── 주문 ────────────────────────────────────────────────────────────────

  /**
   * 주식 주문
   * @param {object} params
   * @param {'BUY'|'SELL'} params.side
   * @param {string} params.stockCode
   * @param {number} params.qty
   * @param {number|null} params.price  null이면 시장가
   */
  async placeOrder({ side, stockCode, qty, price = null }) {
    const isMarket = price === null;
    const tr_id = side === 'BUY' ? 'TTTC0802U' : 'TTTC0801U';
    const data = await this.request('POST', '/uapi/domestic-stock/v1/trading/order-cash', {
      tr_id,
      body: {
        CANO: this.accountNo,
        ACNT_PRDT_CD: this.accountSuffix,
        PDNO: stockCode,
        ORD_DVSN: isMarket ? '01' : '00', // 01: 시장가, 00: 지정가
        ORD_QTY: String(qty),
        ORD_UNPR: isMarket ? '0' : String(price),
      },
    });
    const result = {
      ordNo: data.output.ODNO,
      side,
      stockCode,
      qty,
      price: price ?? 'market',
      timestamp: new Date().toISOString(),
    };
    console.log(`[KIS ORDER] ${side} ${stockCode} x${qty} @ ${result.price}`, result.ordNo);
    return result;
  }

  // ─── WebSocket 실시간 시세 ────────────────────────────────────────────────

  async connectWS(onMessage) {
    const approvalKey = await this.getWSApprovalKey();
    this.ws = new WebSocket('ws://ops.koreainvestment.com:21000');

    this.ws.onopen = () => {
      console.log('[KIS WS] Connected');
    };

    this.ws.onmessage = (event) => {
      if (typeof event.data === 'string') {
        // PINGPONG 처리
        if (event.data.includes('PINGPONG')) {
          this.ws.send(event.data);
          return;
        }
        const parts = event.data.split('|');
        if (parts.length >= 4) {
          const trId = parts[1];
          const payload = parts[3];
          onMessage?.({ trId, raw: payload });
        }
      }
    };

    this.ws.onerror = (e) => console.error('[KIS WS] Error', e);
    this.ws.onclose = () => {
      console.warn('[KIS WS] Disconnected — reconnecting in 5s');
      setTimeout(() => this.connectWS(onMessage), 5000);
    };

    this._wsApprovalKey = approvalKey;
  }

  /** 실시간 체결가 구독 */
  subscribePrice(stockCode) {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) return;
    this.ws.send(JSON.stringify({
      header: {
        approval_key: this._wsApprovalKey,
        custtype: 'P',
        tr_type: '1',
        'content-type': 'utf-8',
      },
      body: {
        input: { tr_id: 'H0STCNT0', tr_key: stockCode },
      },
    }));
    console.log(`[KIS WS] Subscribed to ${stockCode}`);
  }

  unsubscribePrice(stockCode) {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) return;
    this.ws.send(JSON.stringify({
      header: {
        approval_key: this._wsApprovalKey,
        custtype: 'P',
        tr_type: '2',
        'content-type': 'utf-8',
      },
      body: {
        input: { tr_id: 'H0STCNT0', tr_key: stockCode },
      },
    }));
  }

  disconnectWS() {
    this.ws?.close();
    this.ws = null;
  }
}
