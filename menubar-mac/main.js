// JARVIS Menu Bar — macOS
// Usa apenas módulos built-in do Electron (sem require('electron') problemático)
// Este arquivo é carregado pelo Electron binary diretamente via ProgramArguments

process.on('uncaughtException', (err) => {
  console.error('[JARVIS MenuBar] Uncaught:', err.message);
});

let electron;
try {
  electron = require('electron');
} catch {
  // Fallback: quando rodando via Electron binary sem node_modules
  electron = global.require ? global.require('electron') : {};
}

const { app, Tray, Menu, shell, nativeImage, ipcMain } = electron;

if (!app) {
  console.error('[JARVIS MenuBar] Electron app not available — exiting');
  process.exit(1);
}

const path = require('path');
const http = require('http');
const { spawn, execSync } = require('child_process');

const JARVIS_DIR = path.resolve(__dirname, '..');
const NODE_BIN = process.execPath.includes('Electron') ? '/usr/local/bin/node' : process.execPath;

let tray = null;
let jarvisOnline = false;
let pollTimer = null;

app.setName('JARVIS');
app.dock?.hide();

if (!app.requestSingleInstanceLock()) {
  app.quit();
  process.exit(0);
}

function fetchHealth() {
  return new Promise((resolve) => {
    const req = http.get('http://localhost:3000/api/health', { timeout: 3000 }, (res) => {
      let data = '';
      res.on('data', c => data += c);
      res.on('end', () => { try { resolve(JSON.parse(data)); } catch { resolve(null); } });
    });
    req.on('error', () => resolve(null));
    req.on('timeout', () => { req.destroy(); resolve(null); });
  });
}

function buildMenu(online) {
  return Menu.buildFromTemplate([
    { label: online ? '● JARVIS Online' : '○ JARVIS Offline', enabled: false },
    { type: 'separator' },
    {
      label: '  Abrir HUD',
      click: () => shell.openExternal('http://localhost:3000'),
      enabled: online,
    },
    { type: 'separator' },
    { label: '  Reiniciar JARVIS', click: restartServer },
    { type: 'separator' },
    { label: '  Pasta do JARVIS', click: () => shell.openPath(JARVIS_DIR) },
    { type: 'separator' },
    { label: 'Fechar menu bar', click: () => app.quit() },
  ]);
}

function updateTray(online) {
  if (!tray) return;
  jarvisOnline = online;
  tray.setTitle(online ? ' 🟢 JARVIS' : ' 🔴 JARVIS');
  tray.setToolTip(online ? 'JARVIS Online — clique para abrir HUD' : 'JARVIS Offline — reiniciando...');
  tray.setContextMenu(buildMenu(online));
}

async function pollHealth() {
  const r = await fetchHealth();
  updateTray(!!(r && (r.status === 'ok' || r.status === 'operational')));
}

function restartServer() {
  try { execSync("lsof -ti:3000 | xargs kill -9 2>/dev/null; sleep 1 && launchctl start com.jarvis.server", { shell: true }); } catch {}
  updateTray(false);
  setTimeout(pollHealth, 4000);
}

app.whenReady().then(() => {
  tray = new Tray(nativeImage.createEmpty());
  tray.setTitle(' ⚡ JARVIS');
  tray.setToolTip('JARVIS — verificando...');
  tray.setContextMenu(buildMenu(false));
  tray.on('click', () => {
    if (jarvisOnline) shell.openExternal('http://localhost:3000');
    else tray.popUpContextMenu();
  });
  pollHealth();
  pollTimer = setInterval(pollHealth, 30000);
});

app.on('before-quit', () => { if (pollTimer) clearInterval(pollTimer); });
app.on('window-all-closed', () => {}); // manter vivo sem janelas
