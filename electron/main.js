const { app, BrowserWindow, Tray, Menu, shell, ipcMain, nativeImage, dialog, Notification } = require('electron');
const path = require('path');
const fs = require('fs');

// ── 개발/프로덕션 구분 ────────────────────────────────────────────────────
const isDev = process.env.NODE_ENV === 'development' || !app.isPackaged;
const VITE_DEV_URL = 'http://localhost:5173';

let mainWindow = null;
let tray = null;

// ── 설정 파일 경로 (AppData 저장) ─────────────────────────────────────────
const CONFIG_PATH = path.join(app.getPath('userData'), 'config.json');

function loadConfig() {
  try {
    if (fs.existsSync(CONFIG_PATH)) {
      return JSON.parse(fs.readFileSync(CONFIG_PATH, 'utf-8'));
    }
  } catch (e) { /* ignore */ }
  return {};
}

function saveConfig(data) {
  try {
    fs.writeFileSync(CONFIG_PATH, JSON.stringify(data, null, 2), 'utf-8');
  } catch (e) { console.error('설정 저장 실패:', e); }
}

// ── 메인 윈도우 생성 ─────────────────────────────────────────────────────
function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1440,
    height: 900,
    minWidth: 1100,
    minHeight: 700,
    title: 'KIS Auto Trader',
    backgroundColor: '#09090b',
    titleBarStyle: 'hidden',
    titleBarOverlay: {
      color: '#111113',
      symbolColor: '#71717a',
      height: 32,
    },
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: false,
    },
    icon: path.join(__dirname, '..', 'assets', 'icon.ico'),
    show: false,
  });

  // 로딩 완료 후 표시 (흰 화면 방지)
  mainWindow.once('ready-to-show', () => {
    mainWindow.show();
    if (isDev) mainWindow.webContents.openDevTools();
  });

  // 페이지 로드
  if (isDev) {
    mainWindow.loadURL(VITE_DEV_URL);
  } else {
    mainWindow.loadFile(path.join(__dirname, '..', 'dist', 'index.html'));
  }

  // 닫기 버튼 → 트레이로 최소화 (완전 종료 안 함)
  mainWindow.on('close', (e) => {
    if (!app.isQuitting) {
      e.preventDefault();
      mainWindow.hide();
      showTrayNotification('KIS Auto Trader가 트레이에서 실행 중입니다.');
    }
  });

  // 외부 링크는 브라우저로 열기
  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url);
    return { action: 'deny' };
  });
}

// ── 트레이 아이콘 ────────────────────────────────────────────────────────
function createTray() {
  const iconPath = path.join(__dirname, '..', 'assets', 'tray.ico');
  const icon = fs.existsSync(iconPath)
    ? nativeImage.createFromPath(iconPath)
    : nativeImage.createEmpty();

  tray = new Tray(icon);
  tray.setToolTip('KIS Auto Trader');

  const contextMenu = Menu.buildFromTemplate([
    { label: 'KIS Auto Trader 열기', click: () => mainWindow?.show() },
    { type: 'separator' },
    {
      label: '자동매매 상태',
      enabled: false,
      id: 'status',
    },
    { type: 'separator' },
    {
      label: '시작프로그램 등록',
      type: 'checkbox',
      checked: app.getLoginItemSettings().openAtLogin,
      click: (item) => {
        app.setLoginItemSettings({ openAtLogin: item.checked });
      },
    },
    { type: 'separator' },
    {
      label: '완전 종료',
      click: () => {
        app.isQuitting = true;
        app.quit();
      },
    },
  ]);

  tray.setContextMenu(contextMenu);
  tray.on('double-click', () => mainWindow?.show());
}

function showTrayNotification(body) {
  if (Notification.isSupported()) {
    new Notification({ title: 'KIS Auto Trader', body, silent: true }).show();
  }
}

// ── IPC 핸들러 ───────────────────────────────────────────────────────────

// 설정 저장/불러오기
ipcMain.handle('config:load', () => loadConfig());
ipcMain.handle('config:save', (_, data) => { saveConfig(data); return true; });

// 주문 알림 (트레이 + OS 알림)
ipcMain.on('order:notify', (_, { side, code, name, qty, price }) => {
  const emoji = side === 'BUY' ? '📈' : '📉';
  const msg = `${emoji} ${side === 'BUY' ? '매수' : '매도'} ${name}(${code}) ${qty}주 @ ${price === 'market' ? '시장가' : `₩${Number(price).toLocaleString()}`}`;
  showTrayNotification(msg);
  // 트레이 아이콘 깜빡임 (Windows)
  mainWindow?.flashFrame(true);
  setTimeout(() => mainWindow?.flashFrame(false), 2000);
});

// 자동매매 상태 → 트레이 툴팁 업데이트
ipcMain.on('trader:status', (_, { running, candidates }) => {
  const tooltip = running
    ? `KIS Auto Trader — 실행 중 (후보 ${candidates}종목)`
    : 'KIS Auto Trader — 중지';
  tray?.setToolTip(tooltip);
});

// 앱 버전
ipcMain.handle('app:version', () => app.getVersion());

// 로그 파일 열기
ipcMain.handle('log:open', () => {
  const logDir = app.getPath('userData');
  shell.openPath(logDir);
});

// 외부 브라우저로 열기
ipcMain.on('open:external', (_, url) => shell.openExternal(url));

// 스플래시/로딩 없이 바로 사용
ipcMain.on('window:minimize', () => mainWindow?.minimize());
ipcMain.on('window:maximize', () => {
  if (mainWindow?.isMaximized()) mainWindow.unmaximize();
  else mainWindow?.maximize();
});
ipcMain.on('window:close', () => mainWindow?.hide());

// ── 앱 생명주기 ──────────────────────────────────────────────────────────
app.whenReady().then(() => {
  createWindow();
  createTray();

  // macOS: 독 클릭 시 재표시
  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
    else mainWindow?.show();
  });
});

app.on('window-all-closed', () => {
  // Windows/Linux: 트레이로 계속 실행
  if (process.platform !== 'darwin') {
    // 완전 종료는 tray 메뉴에서만
  }
});

app.on('before-quit', () => {
  app.isQuitting = true;
});

// ── 보안: 외부 URL 네비게이션 차단 ───────────────────────────────────────
app.on('web-contents-created', (_, contents) => {
  contents.on('will-navigate', (e, url) => {
    if (isDev && url.startsWith(VITE_DEV_URL)) return;
    if (!isDev && url.startsWith('file://')) return;
    e.preventDefault();
    shell.openExternal(url);
  });
});
