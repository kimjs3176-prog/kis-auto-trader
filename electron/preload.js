const { contextBridge, ipcRenderer } = require('electron');

/**
 * Renderer(React)에서 window.electronAPI 로 접근 가능한 API
 * contextBridge로 안전하게 노출
 */
contextBridge.exposeInMainWorld('electronAPI', {
  // ── 설정 ──────────────────────────────────────────────────────────────
  loadConfig: () => ipcRenderer.invoke('config:load'),
  saveConfig: (data) => ipcRenderer.invoke('config:save', data),

  // ── 앱 정보 ───────────────────────────────────────────────────────────
  getVersion: () => ipcRenderer.invoke('app:version'),
  openLogFolder: () => ipcRenderer.invoke('log:open'),
  openExternal: (url) => ipcRenderer.send('open:external', url),

  // ── 주문 알림 ─────────────────────────────────────────────────────────
  notifyOrder: (order) => ipcRenderer.send('order:notify', order),

  // ── 트레이 상태 업데이트 ─────────────────────────────────────────────
  updateTraderStatus: (status) => ipcRenderer.send('trader:status', status),

  // ── 윈도우 컨트롤 (커스텀 타이틀바용) ──────────────────────────────
  minimize: () => ipcRenderer.send('window:minimize'),
  maximize: () => ipcRenderer.send('window:maximize'),
  close:    () => ipcRenderer.send('window:close'),

  // ── Electron 환경 감지 ────────────────────────────────────────────────
  isElectron: true,
});
