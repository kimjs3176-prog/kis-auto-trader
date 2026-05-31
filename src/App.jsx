import { useState, useEffect, useCallback, useRef } from "react";

// ── Electron 환경 감지 & IPC 브리지 ──────────────────────────────────────
const isElectron = typeof window !== "undefined" && !!window.electronAPI;
const eAPI = isElectron ? window.electronAPI : null;

// ── 상수 ──────────────────────────────────────────────────────────────────
const STRATEGIES = [
  { id: "ma",         label: "MA",  color: "#22d3ee" },
  { id: "rsi",        label: "RSI", color: "#a78bfa" },
  { id: "volatility", label: "VOL", color: "#fb923c" },
];

const SOURCE_COLORS = {
  UNIVERSE_SCAN:   { label: "유니버스", color: "#22d3ee" },
  VOLUME_SCREENER: { label: "거래량",   color: "#fb923c" },
  CHANGE_SCREENER: { label: "등락률",   color: "#a78bfa" },
  MULTI_FILTER:    { label: "멀티필터", color: "#4ade80" },
  MANUAL:          { label: "수동",     color: "#71717a" },
};

// ── 모의 데이터 ───────────────────────────────────────────────────────────
const MOCK_CANDIDATES = [
  { code:"005930", name:"삼성전자",  price:78400,  changeRate:1.24,  volume:12840000, signal:"BUY",  signalStrength:0.72, buySignalCount:3, source:"UNIVERSE_SCAN",   filterScore:4, scannedAt: new Date().toISOString(), signals:[{signal:"BUY"},{signal:"BUY"},{signal:"BUY"}] },
  { code:"000660", name:"SK하이닉스",price:198500, changeRate:2.15,  volume:5310000,  signal:"BUY",  signalStrength:0.55, buySignalCount:2, source:"VOLUME_SCREENER", filterScore:3, scannedAt: new Date().toISOString(), signals:[{signal:"BUY"},{signal:"BUY"},{signal:"HOLD"}] },
  { code:"035420", name:"NAVER",     price:212000, changeRate:-0.43, volume:890000,   signal:"HOLD", signalStrength:0.10, buySignalCount:1, source:"MULTI_FILTER",   filterScore:3, scannedAt: new Date().toISOString(), signals:[{signal:"HOLD"},{signal:"BUY"},{signal:"HOLD"}] },
  { code:"051910", name:"LG화학",    price:341000, changeRate:3.12,  volume:2140000,  signal:"BUY",  signalStrength:0.61, buySignalCount:2, source:"CHANGE_SCREENER", filterScore:4, scannedAt: new Date().toISOString(), signals:[{signal:"BUY"},{signal:"HOLD"},{signal:"BUY"}] },
  { code:"068270", name:"셀트리온",  price:158000, changeRate:-1.23, volume:3200000,  signal:"SELL", signalStrength:-0.4, buySignalCount:0, source:"UNIVERSE_SCAN",   filterScore:2, scannedAt: new Date().toISOString(), signals:[{signal:"SELL"},{signal:"SELL"},{signal:"HOLD"}] },
];

const MOCK_POSITIONS = [
  { code:"005930", name:"삼성전자",  qty:10, avgPrice:76200,  evalPrice:78400,  profitRate: 2.89 },
  { code:"035420", name:"NAVER",     qty:3,  avgPrice:218000, evalPrice:212000, profitRate:-2.75 },
];

const MOCK_ORDERS = [
  { id:"ORD-001", time:"09:31:22", side:"BUY",  code:"005930", name:"삼성전자", qty:10, status:"체결", source:"UNIVERSE_SCAN" },
  { id:"ORD-002", time:"10:14:05", side:"BUY",  code:"035420", name:"NAVER",    qty:3,  status:"체결", source:"MULTI_FILTER" },
  { id:"ORD-003", time:"11:02:44", side:"SELL", code:"000270", name:"기아",     qty:5,  status:"체결", source:"CHANGE_SCREENER" },
];

let _lid = 0;
const mkLog = (level, msg) => ({ id: ++_lid, time: new Date().toLocaleTimeString("ko-KR"), level, msg });

// ── 공통 컴포넌트 ──────────────────────────────────────────────────────────
function SignalBadge({ signal, size = "sm" }) {
  const map = {
    BUY:  { label:"매수", bg:"#052e16", color:"#4ade80", border:"#166534" },
    SELL: { label:"매도", bg:"#450a0a", color:"#f87171", border:"#991b1b" },
    HOLD: { label:"관망", bg:"#1c1917", color:"#a8a29e", border:"#44403c" },
  };
  const s = map[signal] ?? map.HOLD;
  return (
    <span style={{ fontSize: size==="lg"?12:10, fontWeight:700, letterSpacing:"0.08em",
      padding: size==="lg"?"3px 10px":"2px 7px", borderRadius:4,
      background:s.bg, color:s.color, border:`1px solid ${s.border}`, fontFamily:"monospace" }}>
      {s.label}
    </span>
  );
}

function SourceBadge({ source }) {
  const s = SOURCE_COLORS[source] ?? SOURCE_COLORS.MANUAL;
  return (
    <span style={{ fontSize:9, fontWeight:700, letterSpacing:"0.07em",
      padding:"1px 6px", borderRadius:3,
      background: s.color + "18", color: s.color,
      border:`1px solid ${s.color}44`, fontFamily:"monospace" }}>
      {s.label}
    </span>
  );
}

function StrengthBar({ value }) {
  const pct = Math.max(0, Math.min(1, Math.abs(value))) * 100;
  const color = value >= 0 ? "#4ade80" : "#f87171";
  return (
    <div style={{ display:"flex", alignItems:"center", gap:6 }}>
      <div style={{ flex:1, height:4, background:"#27272a", borderRadius:2, overflow:"hidden" }}>
        <div style={{ width:`${pct}%`, height:"100%", background:color, borderRadius:2, transition:"width 0.4s" }} />
      </div>
      <span style={{ fontSize:10, color, minWidth:32, textAlign:"right" }}>{(value*100).toFixed(0)}%</span>
    </div>
  );
}

function SectionHeader({ title }) {
  return (
    <div style={{ padding:"10px 20px", borderBottom:"1px solid #27272a",
      fontSize:10, color:"#52525b", letterSpacing:"0.12em", fontWeight:700 }}>
      {title}
    </div>
  );
}

function Card({ children, style = {} }) {
  return (
    <div style={{ background:"#111113", border:"1px solid #27272a", borderRadius:8, overflow:"hidden", ...style }}>
      {children}
    </div>
  );
}

// ── 스크리너 상태 뱃지 ────────────────────────────────────────────────────
function ScannerStatusBar({ running, candidates, nextScan, scanProgress }) {
  return (
    <div style={{ display:"flex", alignItems:"center", gap:16,
      background:"#0c0c0e", border:"1px solid #27272a", borderRadius:8,
      padding:"10px 20px", fontSize:12 }}>
      <div style={{ display:"flex", alignItems:"center", gap:8 }}>
        <div style={{ width:7, height:7, borderRadius:"50%",
          background: running ? "#4ade80" : "#52525b",
          boxShadow: running ? "0 0 6px #4ade80" : "none",
          animation: running ? "pulse 2s infinite" : "none" }} />
        <span style={{ color:"#a1a1aa" }}>{running ? "스캐닝 중" : "중지"}</span>
      </div>
      <div style={{ color:"#52525b" }}>|</div>
      <span style={{ color:"#71717a" }}>후보종목 <span style={{ color:"#22d3ee", fontWeight:700 }}>{candidates}</span>개</span>
      <div style={{ color:"#52525b" }}>|</div>
      <div style={{ display:"flex", gap:10 }}>
        {Object.values(SOURCE_COLORS).slice(0,4).map(s => (
          <span key={s.label} style={{ color: s.color, fontSize:11 }}>● {s.label}</span>
        ))}
      </div>
      {nextScan && (
        <>
          <div style={{ color:"#52525b" }}>|</div>
          <span style={{ color:"#71717a", fontSize:11 }}>다음 스캔 <span style={{ color:"#f4f4f5" }}>{nextScan}</span></span>
        </>
      )}
      {scanProgress !== null && scanProgress !== undefined && (
        <div style={{ marginLeft:"auto", display:"flex", alignItems:"center", gap:8 }}>
          <div style={{ width:80, height:3, background:"#27272a", borderRadius:2 }}>
            <div style={{ width:`${scanProgress}%`, height:"100%", background:"#22d3ee", borderRadius:2, transition:"width 0.3s" }} />
          </div>
          <span style={{ color:"#22d3ee", fontSize:11 }}>{scanProgress}%</span>
        </div>
      )}
    </div>
  );
}

// ── 필터 점수 표시 ────────────────────────────────────────────────────────
function FilterScoreDots({ score, max = 5 }) {
  return (
    <div style={{ display:"flex", gap:3 }}>
      {Array.from({ length: max }).map((_, i) => (
        <div key={i} style={{ width:6, height:6, borderRadius:"50%",
          background: i < score ? "#22d3ee" : "#27272a" }} />
      ))}
    </div>
  );
}

// ── 메인 앱 ───────────────────────────────────────────────────────────────
export default function App() {
  const [tab, setTab] = useState("screener");
  const [running, setRunning] = useState(false);
  const [scanProgress, setScanProgress] = useState(null);
  const [nextScanIn, setNextScanIn] = useState(null);

  // Electron: 앱 시작 시 저장된 설정 불러오기
  useEffect(() => {
    if (!eAPI) return;
    eAPI.loadConfig().then(saved => {
      if (saved && Object.keys(saved).length > 0) {
        setConfig(prev => ({ ...prev, ...saved }));
        addLog("INFO", "저장된 설정을 불러왔습니다.");
      }
    });
  }, []);

  const [candidates, setCandidates] = useState(MOCK_CANDIDATES);
  const [positions, setPositions] = useState(MOCK_POSITIONS);
  const [orders, setOrders] = useState(MOCK_ORDERS);
  const [balance] = useState({ cash: 5_430_000, totalEval: 8_920_000 });
  const [logs, setLogs] = useState([
    mkLog("INFO", "시스템 초기화 완료. 시작 버튼을 눌러 스캐닝을 시작하세요."),
  ]);

  const [config, setConfig] = useState({
    appKey:"", appSecret:"", accountNo:"", accountSuffix:"01",
    // 스크리너
    universeTopN: 10, conditionTopN: 20, maxCandidates: 15,
    minVolume: 500000, volumeSurgeRatio: 2.0,
    rsiMin: 30, rsiMax: 55, momentum52wRatio: 0.9,
    // 전략
    maShort:5, maLong:20,
    rsiPeriod:14, rsiOversold:30, rsiOverbought:70, volatilityK:0.5,
    // 리스크
    stopLoss:-5, takeProfit:10, orderQtyRatio:10,
  });

  const [sortBy, setSortBy] = useState("signalStrength");
  const [filterSignal, setFilterSignal] = useState("ALL");
  const [configError, setConfigError] = useState("");

  const addLog = useCallback((level, msg) => {
    setLogs(prev => [mkLog(level, msg), ...prev].slice(0, 500));
  }, []);

  // 시뮬레이션: 가격 ticker
  useEffect(() => {
    if (!running) return;
    const t = setInterval(() => {
      setCandidates(prev => prev.map(c => ({
        ...c,
        price: Math.round(c.price * (1 + (Math.random()-0.49)*0.003)),
        changeRate: +(c.changeRate + (Math.random()-0.5)*0.1).toFixed(2),
        volume: c.volume + Math.floor(Math.random()*10000),
      })));
    }, 3000);
    return () => clearInterval(t);
  }, [running]);

  // 시뮬레이션: 스캔 로그
  useEffect(() => {
    if (!running) return;
    let countdown = 60;
    const t = setInterval(() => {
      countdown--;
      setNextScanIn(`${countdown}s`);
      if (countdown <= 0) {
        countdown = 60;
        addLog("INFO", `[거래량 스크리너] 상위 20종목 스캔 완료 — 신규 후보 ${Math.floor(Math.random()*3)+1}개`);
        addLog("INFO", `[등락률 스크리너] 상승 상위 스캔 — 조건 통과 ${Math.floor(Math.random()*2)+1}개`);
      }
    }, 1000);
    return () => clearInterval(t);
  }, [running, addLog]);

  // 시뮬레이션: 모닝 스캔
  const runMorningScan = useCallback(() => {
    addLog("INFO", "═══ 모닝 스캔 시작 — 코스피200 유니버스 50종목 ═══");
    let progress = 0;
    setScanProgress(0);
    const t = setInterval(() => {
      progress += 4;
      setScanProgress(progress);
      if (progress >= 100) {
        clearInterval(t);
        setScanProgress(null);
        addLog("INFO", "유니버스 스캔 완료 — 10개 후보 선정");
        addLog("INFO", "멀티 필터 스크리닝 완료 — 거래량급증 3종목, RSI조건 4종목, MA정배열 5종목");
        addLog("INFO", "═══ 모닝 스캔 종료 — 당일 후보 15개 확정 ═══");
      }
    }, 150);
  }, [addLog]);

  const handleStart = () => {
    if (!config.appKey || !config.appSecret || !config.accountNo) {
      setConfigError("앱 키, 앱 시크릿, 계좌번호를 모두 입력해주세요.");
      setTab("settings"); return;
    }
    setConfigError("");
    setRunning(true);
    // Electron: 설정 저장 + 트레이 상태 업데이트
    eAPI?.saveConfig(config);
    eAPI?.updateTraderStatus({ running: true, candidates: candidates.length });
    addLog("INFO", `자동매매 + 스크리너 시작 | 최대후보 ${config.maxCandidates}종목 | 손절 ${config.stopLoss}% | 익절 ${config.takeProfit}%`);
    runMorningScan();
  };

  const handleStop = () => {
    setRunning(false);
    setNextScanIn(null);
    eAPI?.updateTraderStatus({ running: false, candidates: 0 });
    addLog("WARN", "자동매매 중지됨");
  };

  // 후보 목록 정렬/필터
  const displayedCandidates = candidates
    .filter(c => filterSignal === "ALL" || c.signal === filterSignal)
    .sort((a, b) => {
      if (sortBy === "signalStrength") return b.signalStrength - a.signalStrength;
      if (sortBy === "filterScore")   return (b.filterScore??0) - (a.filterScore??0);
      if (sortBy === "volume")        return b.volume - a.volume;
      if (sortBy === "changeRate")    return b.changeRate - a.changeRate;
      return 0;
    });

  const totalProfit = positions.reduce((s, p) => s + (p.evalPrice - p.avgPrice) * p.qty, 0);
  const buyCandidates = candidates.filter(c => c.signal === "BUY").length;

  return (
    <div style={{ minHeight:"100vh", background:"#09090b", color:"#f4f4f5",
      fontFamily:"'IBM Plex Mono','Fira Code',monospace" }}>
      <link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;700&display=swap" rel="stylesheet" />
      <style>{`
        @keyframes pulse { 0%,100%{opacity:1} 50%{opacity:0.4} }
        input:focus { border-color:#22d3ee !important; outline:none; }
        ::-webkit-scrollbar{width:5px} ::-webkit-scrollbar-track{background:#18181b}
        ::-webkit-scrollbar-thumb{background:#3f3f46;border-radius:3px}
        * { box-sizing:border-box; }
      `}</style>

      {/* ── 커스텀 타이틀바 (Electron 전용) ──────────────────────────────── */}
      {isElectron && (
        <div style={{ height:32, background:"#0a0a0c", display:"flex", alignItems:"center",
          justifyContent:"space-between", padding:"0 16px",
          WebkitAppRegion:"drag", userSelect:"none", flexShrink:0 }}>
          <span style={{ fontSize:11, color:"#52525b", letterSpacing:"0.1em" }}>KIS AUTO TRADER</span>
          <div style={{ display:"flex", gap:6, WebkitAppRegion:"no-drag" }}>
            {[
              { action: eAPI?.minimize, color:"#fbbf24", symbol:"−" },
              { action: eAPI?.maximize, color:"#22d3ee", symbol:"□" },
              { action: eAPI?.close,    color:"#f87171", symbol:"×" },
            ].map((b, i) => (
              <button key={i} onClick={b.action}
                style={{ width:22, height:22, borderRadius:"50%", border:"none",
                  background: b.color+"33", color:b.color, fontSize:12, fontWeight:700,
                  cursor:"pointer", display:"flex", alignItems:"center", justifyContent:"center",
                  transition:"background 0.15s" }}
                onMouseEnter={e => e.target.style.background = b.color+"66"}
                onMouseLeave={e => e.target.style.background = b.color+"33"}>
                {b.symbol}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* ── 헤더 ─────────────────────────────────────────────────────────── */}
      <div style={{ borderBottom:"1px solid #27272a", padding:"0 24px",
        display:"flex", alignItems:"center", justifyContent:"space-between",
        height:52, background:"#111113" }}>
        <div style={{ display:"flex", alignItems:"center", gap:12 }}>
          <div style={{ width:8, height:8, borderRadius:"50%",
            background: running ? "#4ade80" : "#52525b",
            boxShadow: running ? "0 0 8px #4ade80" : "none",
            animation: running ? "pulse 2s infinite" : "none" }} />
          <span style={{ fontWeight:700, fontSize:14, letterSpacing:"0.12em", color:"#e4e4e7" }}>
            KIS AUTO TRADER
          </span>
          <span style={{ fontSize:9, padding:"2px 6px", borderRadius:3,
            background:"#18181b", border:"1px solid #3f3f46", color:"#71717a" }}>
            LIVE
          </span>
          {running && (
            <span style={{ fontSize:11, color:"#4ade80" }}>
              매수 후보 <strong>{buyCandidates}</strong>종목
            </span>
          )}
        </div>
        <div style={{ display:"flex", gap:8, alignItems:"center" }}>
          {!running && (
            <button onClick={runMorningScan}
              style={{ padding:"5px 12px", borderRadius:5, border:"1px solid #3f3f46",
                background:"#18181b", color:"#22d3ee", fontFamily:"inherit",
                fontSize:11, cursor:"pointer", letterSpacing:"0.06em" }}>
              모닝 스캔
            </button>
          )}
          <button onClick={running ? handleStop : handleStart}
            style={{ padding:"6px 18px", borderRadius:6, border:"none",
              fontFamily:"inherit", fontSize:12, fontWeight:700,
              letterSpacing:"0.08em", cursor:"pointer",
              background: running ? "#7f1d1d" : "#14532d",
              color: running ? "#fca5a5" : "#86efac" }}>
            {running ? "■ 중지" : "▶ 시작"}
          </button>
        </div>
      </div>

      {/* ── 탭 ───────────────────────────────────────────────────────────── */}
      <div style={{ display:"flex", borderBottom:"1px solid #27272a",
        padding:"0 24px", background:"#111113" }}>
        {[
          { id:"screener",  label:"스크리너" },
          { id:"dashboard", label:"대시보드" },
          { id:"log",       label:`로그 (${logs.length})` },
          { id:"settings",  label:"설정" },
        ].map(t => (
          <button key={t.id} onClick={() => setTab(t.id)}
            style={{ background:"none", border:"none",
              borderBottom: tab===t.id ? "2px solid #22d3ee" : "2px solid transparent",
              padding:"10px 16px", fontFamily:"inherit", fontSize:12,
              color: tab===t.id ? "#22d3ee" : "#71717a",
              cursor:"pointer", letterSpacing:"0.06em" }}>
            {t.label}
          </button>
        ))}
      </div>

      <div style={{ padding:24, maxWidth:1280, margin:"0 auto" }}>

        {/* ══════════════ 스크리너 탭 ══════════════ */}
        {tab === "screener" && (
          <div style={{ display:"flex", flexDirection:"column", gap:16 }}>

            {/* 스캐너 상태바 */}
            <ScannerStatusBar
              running={running}
              candidates={candidates.length}
              nextScan={nextScanIn}
              scanProgress={scanProgress}
            />

            {/* 스크리닝 방식 카드 3개 */}
            <div style={{ display:"grid", gridTemplateColumns:"repeat(3,1fr)", gap:12 }}>
              {[
                { title:"유니버스 스캔", icon:"◈",
                  desc:"코스피200 전체 종목 MA/RSI/변동성 신호 분석",
                  detail:`상위 ${config.universeTopN}종목 선정 · 장 시작 전 08:50 실행`,
                  color:"#22d3ee", count: candidates.filter(c=>c.source==="UNIVERSE_SCAN").length },
                { title:"조건 스크리너", icon:"◉",
                  desc:"거래량 상위 + 등락률 상위 실시간 스캔",
                  detail:`최소 거래량 ${(config.minVolume/10000).toFixed(0)}만주 · 60초 주기`,
                  color:"#fb923c", count: candidates.filter(c=>c.source==="VOLUME_SCREENER"||c.source==="CHANGE_SCREENER").length },
                { title:"멀티 필터", icon:"◆",
                  desc:"거래량 급증 + RSI + MA정배열 + 52주 신고가 복합 조건",
                  detail:`5개 필터 중 3개↑ 통과 · 장 시작 전 + 장중 재스캔`,
                  color:"#4ade80", count: candidates.filter(c=>c.source==="MULTI_FILTER").length },
              ].map(m => (
                <Card key={m.title}>
                  <div style={{ padding:"16px 18px" }}>
                    <div style={{ display:"flex", justifyContent:"space-between", alignItems:"flex-start", marginBottom:10 }}>
                      <div style={{ display:"flex", alignItems:"center", gap:8 }}>
                        <span style={{ color:m.color, fontSize:16 }}>{m.icon}</span>
                        <span style={{ fontWeight:700, fontSize:13, color:"#e4e4e7" }}>{m.title}</span>
                      </div>
                      <span style={{ fontSize:20, fontWeight:700, color:m.color }}>{m.count}</span>
                    </div>
                    <p style={{ fontSize:11, color:"#a1a1aa", lineHeight:1.6, margin:0 }}>{m.desc}</p>
                    <p style={{ fontSize:10, color:"#52525b", marginTop:6 }}>{m.detail}</p>
                  </div>
                </Card>
              ))}
            </div>

            {/* 후보 종목 테이블 */}
            <Card>
              {/* 테이블 툴바 */}
              <div style={{ display:"flex", alignItems:"center", justifyContent:"space-between",
                padding:"10px 20px", borderBottom:"1px solid #27272a" }}>
                <span style={{ fontSize:10, color:"#52525b", letterSpacing:"0.12em", fontWeight:700 }}>
                  CANDIDATES — 발굴 종목 ({displayedCandidates.length})
                </span>
                <div style={{ display:"flex", gap:8 }}>
                  {/* 신호 필터 */}
                  {["ALL","BUY","HOLD","SELL"].map(f => (
                    <button key={f} onClick={() => setFilterSignal(f)}
                      style={{ padding:"3px 10px", borderRadius:4, border:"none", fontFamily:"inherit",
                        fontSize:10, cursor:"pointer", fontWeight:700, letterSpacing:"0.06em",
                        background: filterSignal===f ? "#27272a" : "none",
                        color: filterSignal===f ? "#f4f4f5" : "#52525b" }}>
                      {f}
                    </button>
                  ))}
                  <div style={{ width:1, background:"#27272a", margin:"0 4px" }} />
                  {/* 정렬 */}
                  {[
                    { id:"signalStrength", label:"신호강도" },
                    { id:"filterScore",    label:"필터점수" },
                    { id:"volume",         label:"거래량" },
                    { id:"changeRate",     label:"등락률" },
                  ].map(s => (
                    <button key={s.id} onClick={() => setSortBy(s.id)}
                      style={{ padding:"3px 10px", borderRadius:4, border:"none", fontFamily:"inherit",
                        fontSize:10, cursor:"pointer", letterSpacing:"0.06em",
                        background: sortBy===s.id ? "#1e3a5f" : "none",
                        color: sortBy===s.id ? "#22d3ee" : "#52525b" }}>
                      {s.label}
                    </button>
                  ))}
                </div>
              </div>

              {/* 컬럼 헤더 */}
              <div style={{ display:"grid",
                gridTemplateColumns:"90px 140px 110px 80px 100px 80px 120px 90px 100px 80px",
                gap:8, padding:"7px 20px", borderBottom:"1px solid #27272a",
                fontSize:10, color:"#3f3f46", letterSpacing:"0.08em" }}>
                <span>코드</span><span>종목명</span><span style={{textAlign:"right"}}>현재가</span>
                <span style={{textAlign:"right"}}>등락률</span><span style={{textAlign:"right"}}>거래량</span>
                <span style={{textAlign:"center"}}>신호</span><span>신호강도</span>
                <span style={{textAlign:"center"}}>필터점수</span><span style={{textAlign:"center"}}>전략신호</span>
                <span style={{textAlign:"center"}}>출처</span>
              </div>

              {/* 종목 행 */}
              {displayedCandidates.map(c => (
                <div key={c.code}
                  style={{ display:"grid",
                    gridTemplateColumns:"90px 140px 110px 80px 100px 80px 120px 90px 100px 80px",
                    gap:8, padding:"11px 20px", borderBottom:"1px solid #18181b",
                    alignItems:"center", fontSize:12,
                    background: c.signal==="BUY" ? "#052e1608" : c.signal==="SELL" ? "#450a0a08" : "transparent",
                    transition:"background 0.2s" }}>
                  <span style={{ color:"#71717a", fontSize:11 }}>{c.code}</span>
                  <span style={{ color:"#e4e4e7", fontWeight:500 }}>{c.name}</span>
                  <span style={{ textAlign:"right", color:"#f4f4f5" }}>
                    ₩{c.price.toLocaleString()}
                  </span>
                  <span style={{ textAlign:"right",
                    color: c.changeRate>=0 ? "#4ade80" : "#f87171" }}>
                    {c.changeRate>=0?"▲":"▼"}{Math.abs(c.changeRate).toFixed(2)}%
                  </span>
                  <span style={{ textAlign:"right", color:"#a1a1aa", fontSize:11 }}>
                    {(c.volume/10000).toFixed(0)}만
                  </span>
                  <div style={{ textAlign:"center" }}>
                    <SignalBadge signal={c.signal} />
                  </div>
                  <StrengthBar value={c.signalStrength} />
                  <div style={{ display:"flex", justifyContent:"center" }}>
                    <FilterScoreDots score={c.filterScore ?? 0} />
                  </div>
                  {/* 전략별 신호 아이콘 */}
                  <div style={{ display:"flex", gap:4, justifyContent:"center" }}>
                    {STRATEGIES.map((st, i) => {
                      const sig = c.signals?.[i]?.signal ?? "HOLD";
                      return (
                        <div key={st.id} title={st.label}
                          style={{ width:18, height:18, borderRadius:3, fontSize:9, fontWeight:700,
                            display:"flex", alignItems:"center", justifyContent:"center",
                            background: sig==="BUY" ? "#052e16" : sig==="SELL" ? "#450a0a" : "#18181b",
                            color: sig==="BUY" ? "#4ade80" : sig==="SELL" ? "#f87171" : "#52525b",
                            border: `1px solid ${sig==="BUY" ? "#166534" : sig==="SELL" ? "#991b1b" : "#27272a"}` }}>
                          {st.label[0]}
                        </div>
                      );
                    })}
                  </div>
                  <div style={{ textAlign:"center" }}>
                    <SourceBadge source={c.source} />
                  </div>
                </div>
              ))}

              {displayedCandidates.length === 0 && (
                <div style={{ padding:40, textAlign:"center", color:"#3f3f46", fontSize:12 }}>
                  조건에 맞는 후보 종목이 없습니다
                </div>
              )}
            </Card>

            {/* 필터 조건 요약 */}
            <Card>
              <SectionHeader title="멀티 필터 조건 (5개 중 3개↑ 통과 시 후보 편입)" />
              <div style={{ display:"grid", gridTemplateColumns:"repeat(5,1fr)", gap:0 }}>
                {[
                  { no:1, label:"거래량 급증", desc:`전일比 ${config.volumeSurgeRatio}배↑`, color:"#22d3ee" },
                  { no:2, label:"RSI 구간",    desc:`${config.rsiMin}~${config.rsiMax} (과매도 회복)`, color:"#a78bfa" },
                  { no:3, label:"MA 정배열",   desc:"MA5 > MA20 > MA60", color:"#fb923c" },
                  { no:4, label:"52주 신고가", desc:`현재가 ≥ 신고가 × ${config.momentum52wRatio}`, color:"#4ade80" },
                  { no:5, label:"단기 상승",   desc:"현재가 > 5일 전 종가", color:"#fbbf24" },
                ].map(f => (
                  <div key={f.no} style={{ padding:"14px 16px",
                    borderRight: f.no<5 ? "1px solid #27272a" : "none" }}>
                    <div style={{ display:"flex", alignItems:"center", gap:6, marginBottom:6 }}>
                      <span style={{ width:18, height:18, borderRadius:"50%",
                        background: f.color+"22", color:f.color, fontSize:10, fontWeight:700,
                        display:"flex", alignItems:"center", justifyContent:"center",
                        border:`1px solid ${f.color}44`, flexShrink:0 }}>
                        {f.no}
                      </span>
                      <span style={{ fontSize:11, fontWeight:700, color:"#e4e4e7" }}>{f.label}</span>
                    </div>
                    <p style={{ fontSize:10, color:"#71717a", margin:0 }}>{f.desc}</p>
                  </div>
                ))}
              </div>
            </Card>
          </div>
        )}

        {/* ══════════════ 대시보드 탭 ══════════════ */}
        {tab === "dashboard" && (
          <div style={{ display:"flex", flexDirection:"column", gap:16 }}>
            {/* 스탯 */}
            <div style={{ display:"grid", gridTemplateColumns:"repeat(4,1fr)", gap:12 }}>
              {[
                { label:"보유 현금",  value:`₩${balance.cash.toLocaleString()}`,     sub:"주문가능금액" },
                { label:"평가금액",   value:`₩${balance.totalEval.toLocaleString()}`, sub:"보유종목 평가" },
                { label:"평가손익",   value:`${totalProfit>=0?"+":""}₩${totalProfit.toLocaleString()}`,
                  accent: totalProfit>=0?"green":"red", sub:"미실현손익" },
                { label:"매수 후보",  value:`${buyCandidates}종목`,
                  accent:"green", sub:`전체 ${candidates.length}개 후보 중` },
              ].map((s, i) => (
                <Card key={i} style={{ padding:"16px 20px" }}>
                  <div style={{ display:"flex", flexDirection:"column", gap:2 }}>
                    <span style={{ fontSize:11, color:"#71717a", letterSpacing:"0.05em" }}>{s.label}</span>
                    <span style={{ fontSize:20, fontWeight:700, lineHeight:1.1,
                      color: s.accent==="green" ? "#4ade80" : s.accent==="red" ? "#f87171" : "#f4f4f5" }}>
                      {s.value}
                    </span>
                    {s.sub && <span style={{ fontSize:11, color:"#71717a" }}>{s.sub}</span>}
                  </div>
                </Card>
              ))}
            </div>

            <div style={{ display:"grid", gridTemplateColumns:"1fr 1fr", gap:16 }}>
              {/* 포지션 */}
              <Card>
                <SectionHeader title="POSITIONS" />
                {positions.map(p => (
                  <div key={p.code} style={{ padding:"14px 20px", borderBottom:"1px solid #18181b",
                    display:"flex", justifyContent:"space-between", alignItems:"center" }}>
                    <div>
                      <div style={{ fontWeight:500, fontSize:13 }}>{p.name}</div>
                      <div style={{ fontSize:11, color:"#71717a", marginTop:2 }}>
                        {p.qty}주 · 평균 ₩{p.avgPrice.toLocaleString()}
                      </div>
                    </div>
                    <div style={{ textAlign:"right" }}>
                      <div style={{ fontSize:13 }}>₩{p.evalPrice.toLocaleString()}</div>
                      <div style={{ fontSize:12, marginTop:2,
                        color: p.profitRate>=0 ? "#4ade80" : "#f87171" }}>
                        {p.profitRate>=0?"+":""}{p.profitRate.toFixed(2)}%
                      </div>
                    </div>
                  </div>
                ))}
              </Card>

              {/* 주문 내역 */}
              <Card>
                <SectionHeader title="ORDER HISTORY" />
                {orders.map(o => (
                  <div key={o.id} style={{ padding:"11px 20px", borderBottom:"1px solid #18181b",
                    display:"flex", justifyContent:"space-between", alignItems:"center", fontSize:12 }}>
                    <div style={{ display:"flex", gap:8, alignItems:"center" }}>
                      <SignalBadge signal={o.side} />
                      <span style={{ color:"#e4e4e7" }}>{o.name}</span>
                      <span style={{ color:"#71717a" }}>x{o.qty}</span>
                      <SourceBadge source={o.source} />
                    </div>
                    <div style={{ textAlign:"right", color:"#71717a", fontSize:11 }}>
                      <div>{o.time}</div>
                      <div style={{ color:"#22c55e" }}>{o.status}</div>
                    </div>
                  </div>
                ))}
              </Card>
            </div>
          </div>
        )}

        {/* ══════════════ 로그 탭 ══════════════ */}
        {tab === "log" && (
          <Card>
            <div style={{ position:"sticky", top:0, background:"#111113",
              padding:"10px 16px", borderBottom:"1px solid #27272a",
              display:"flex", justifyContent:"space-between", alignItems:"center" }}>
              <span style={{ fontSize:10, color:"#52525b", letterSpacing:"0.1em" }}>
                CONSOLE — {logs.length}건
              </span>
              <button onClick={() => setLogs([])}
                style={{ background:"none", border:"1px solid #3f3f46", color:"#71717a",
                  fontSize:11, padding:"2px 8px", borderRadius:4, cursor:"pointer", fontFamily:"inherit" }}>
                clear
              </button>
            </div>
            <div style={{ maxHeight:"70vh", overflowY:"auto" }}>
              {logs.map(l => (
                <div key={l.id} style={{ display:"flex", gap:12, padding:"5px 16px",
                  borderBottom:"1px solid #18181b", alignItems:"baseline" }}>
                  <span style={{ color:"#3f3f46", minWidth:68, flexShrink:0, fontSize:11 }}>{l.time}</span>
                  <span style={{ minWidth:40, fontSize:11, flexShrink:0,
                    color: l.level==="ERROR"?"#f87171":l.level==="WARN"?"#fbbf24":"#22d3ee" }}>
                    {l.level}
                  </span>
                  <span style={{ color:"#d4d4d8", fontSize:12 }}>{l.msg}</span>
                </div>
              ))}
            </div>
          </Card>
        )}

        {/* ══════════════ 설정 탭 ══════════════ */}
        {tab === "settings" && (
          <div style={{ display:"flex", flexDirection:"column", gap:14, maxWidth:700 }}>
            {configError && (
              <div style={{ background:"#450a0a", border:"1px solid #991b1b", borderRadius:6,
                padding:"10px 16px", color:"#fca5a5", fontSize:13 }}>
                ⚠ {configError}
              </div>
            )}
            {[
              { title:"API 인증", fields:[
                { key:"appKey",        label:"App Key",          type:"password", placeholder:"KIS 개발자 앱키" },
                { key:"appSecret",     label:"App Secret",       type:"password", placeholder:"KIS 앱 시크릿" },
                { key:"accountNo",     label:"계좌번호 (8자리)",  placeholder:"12345678" },
                { key:"accountSuffix", label:"상품코드",          placeholder:"01" },
              ]},
              { title:"스크리너 설정", fields:[
                { key:"universeTopN",      label:"유니버스 스캔 상위 N종목", type:"number", placeholder:"10" },
                { key:"conditionTopN",     label:"조건 스크리너 상위 N종목", type:"number", placeholder:"20" },
                { key:"maxCandidates",     label:"최대 후보 종목 수",         type:"number", placeholder:"15" },
                { key:"minVolume",         label:"최소 거래량",               type:"number", placeholder:"500000" },
                { key:"volumeSurgeRatio",  label:"거래량 급증 기준 (배수)",   type:"number", placeholder:"2.0" },
              ]},
              { title:"멀티 필터 조건", fields:[
                { key:"rsiMin",            label:"RSI 하한 (과매도 회복)",    type:"number", placeholder:"30" },
                { key:"rsiMax",            label:"RSI 상한 (과매수 진입 전)", type:"number", placeholder:"55" },
                { key:"momentum52wRatio",  label:"52주 신고가 비율",          type:"number", placeholder:"0.9" },
              ]},
              { title:"전략 파라미터", fields:[
                { key:"maShort",       label:"MA 단기",     type:"number", placeholder:"5" },
                { key:"maLong",        label:"MA 장기",     type:"number", placeholder:"20" },
                { key:"rsiPeriod",     label:"RSI 기간",    type:"number", placeholder:"14" },
                { key:"rsiOversold",   label:"RSI 과매도",  type:"number", placeholder:"30" },
                { key:"rsiOverbought", label:"RSI 과매수",  type:"number", placeholder:"70" },
                { key:"volatilityK",   label:"변동성 K값",  type:"number", placeholder:"0.5" },
              ]},
              { title:"리스크 관리", fields:[
                { key:"stopLoss",      label:"손절 기준 (%)",           type:"number", placeholder:"-5" },
                { key:"takeProfit",    label:"익절 기준 (%)",           type:"number", placeholder:"10" },
                { key:"orderQtyRatio", label:"주문 비중 (현금 대비 %)", type:"number", placeholder:"10" },
              ]},
            ].map(sec => (
              <Card key={sec.title}>
                <SectionHeader title={sec.title.toUpperCase()} />
                <div style={{ padding:"14px 20px", display:"flex", flexDirection:"column", gap:10 }}>
                  {sec.fields.map(f => (
                    <div key={f.key} style={{ display:"flex", alignItems:"center", gap:16 }}>
                      <label style={{ fontSize:12, color:"#a1a1aa", minWidth:220, flexShrink:0 }}>
                        {f.label}
                      </label>
                      <input type={f.type??"text"} value={config[f.key]}
                        placeholder={f.placeholder}
                        onChange={e => setConfig(c => ({ ...c, [f.key]: e.target.value }))}
                        style={{ flex:1, background:"#18181b", border:"1px solid #3f3f46",
                          borderRadius:6, padding:"7px 12px", color:"#f4f4f5",
                          fontFamily:"inherit", fontSize:13, transition:"border-color 0.2s" }} />
                    </div>
                  ))}
                </div>
              </Card>
            ))}
            <button onClick={() => { setConfigError(""); setTab("screener"); addLog("INFO", "설정 저장 완료"); }}
              style={{ background:"#22d3ee", color:"#09090b", border:"none", borderRadius:6,
                padding:"10px 24px", fontFamily:"inherit", fontSize:13, fontWeight:700,
                letterSpacing:"0.08em", cursor:"pointer", alignSelf:"flex-start" }}>
              설정 저장
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
