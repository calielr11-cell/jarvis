const { app, BrowserWindow, ipcMain, Menu, Tray, shell, screen, nativeImage } = require('electron');
const path = require('path');
const http = require('http');
const fs = require('fs');
const { spawn, execSync } = require('child_process');

const JARVIS_DIR = path.resolve(__dirname, '..');
const NODE_BIN = '/usr/local/bin/node';
const SERVER_SCRIPT = path.join(JARVIS_DIR, 'server.js');

let mainWindow = null;
let tray = null;
let dragOffset = null;
let jarvisOnline = false;
let pollTimer = null;

// Single instance lock
const gotLock = app.requestSingleInstanceLock();
if (!gotLock) {
  app.quit();
} else {
  app.on('second-instance', () => {
    if (mainWindow) { mainWindow.show(); mainWindow.focus(); }
  });
}

// ── Health check ─────────────────────────────────────────────────────────────
function fetchJSON(url) {
  return new Promise((resolve) => {
    const req = http.get(url, { timeout: 3000 }, (res) => {
      let data = '';
      res.on('data', (chunk) => (data += chunk));
      res.on('end', () => {
        try { resolve(JSON.parse(data)); } catch { resolve({ status: 'online' }); }
      });
    });
    req.on('error', () => resolve(null));
    req.on('timeout', () => { req.destroy(); resolve(null); });
  });
}

// ── Tray (Menu Bar) ───────────────────────────────────────────────────────────
function buildTrayMenu(online) {
  return Menu.buildFromTemplate([
    {
      label: online ? '● JARVIS Online' : '○ JARVIS Offline',
      enabled: false,
    },
    { type: 'separator' },
    {
      label: '  Abrir HUD',
      click: () => shell.openExternal('http://localhost:3000'),
      enabled: online,
    },
    {
      label: '  Abrir Pet',
      click: () => { if (mainWindow) { mainWindow.show(); mainWindow.focus(); } else createPetWindow(); },
    },
    { type: 'separator' },
    {
      label: '  Reiniciar JARVIS',
      click: restartJarvis,
    },
    { type: 'separator' },
    {
      label: '  Abrir pasta JARVIS',
      click: () => shell.openPath(JARVIS_DIR),
    },
    { type: 'separator' },
    { label: 'Fechar JARVIS', click: () => app.quit() },
  ]);
}

function updateTray(online, detail = '') {
  if (!tray) return;
  jarvisOnline = online;
  const dot = online ? '🟢' : '🔴';
  tray.setTitle(` ${dot} JARVIS`);
  tray.setToolTip(online
    ? `JARVIS ONLINE\n${detail}`
    : 'JARVIS OFFLINE — clique com botão direito → Reiniciar'
  );
  tray.setContextMenu(buildTrayMenu(online));
}

function createTray() {
  tray = new Tray(nativeImage.createEmpty());
  tray.setTitle(' ⚡ JARVIS');
  tray.setToolTip('JARVIS — verificando...');
  tray.setContextMenu(buildTrayMenu(false));

  // Click esquerdo → abre HUD
  tray.on('click', () => {
    if (jarvisOnline) shell.openExternal('http://localhost:3000');
    else tray.popUpContextMenu();
  });
}

async function pollHealth() {
  const result = await fetchJSON('http://localhost:3000/api/health');
  const online = !!(result && (result.status === 'ok' || result.status === 'operational'));
  const detail = online && result.components?.pools
    ? `Opus×${result.components.pools.opus} Sonnet×${result.components.pools.sonnet}`
    : '';
  updateTray(online, detail);
}

function startJarvisServer() {
  try { execSync(`launchctl start com.jarvis.server`, { stdio: 'ignore' }); } catch {}
  setTimeout(pollHealth, 3000);
}

function restartJarvis() {
  try { execSync("lsof -ti:3000 | xargs kill -9 2>/dev/null || true", { shell: true }); } catch {}
  updateTray(false);
  setTimeout(startJarvisServer, 1500);
}

// ── Pet Window ────────────────────────────────────────────────────────────────
function createPetWindow() {
  const { width, height } = screen.getPrimaryDisplay().workAreaSize;

  mainWindow = new BrowserWindow({
    width: 200, height: 200,
    x: width - 220, y: height - 220,
    frame: false, transparent: true,
    alwaysOnTop: true, skipTaskbar: true,
    resizable: false, hasShadow: false,
    backgroundColor: '#00000000',
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      preload: path.join(__dirname, 'preload.js'),
    },
  });

  mainWindow.loadFile(path.join(__dirname, 'pet.html'));
  mainWindow.setVisibleOnAllWorkspaces(true, { visibleOnFullScreen: true });
  mainWindow.on('closed', () => { mainWindow = null; });
}

// Preload
const preloadContent = `
const { contextBridge, ipcRenderer } = require('electron');
contextBridge.exposeInMainWorld('jarvis', {
  getStatus: () => ipcRenderer.invoke('get-jarvis-status'),
  openCockpit: () => ipcRenderer.invoke('open-cockpit'),
  moveToCenter: () => ipcRenderer.invoke('move-to-center'),
  closePet: () => ipcRenderer.invoke('close-pet'),
  startDrag: (screenX, screenY) => ipcRenderer.send('drag-start', screenX, screenY),
  onDrag: (screenX, screenY) => ipcRenderer.send('drag-move', screenX, screenY),
  stopDrag: () => ipcRenderer.send('drag-stop'),
  showMenu: () => ipcRenderer.send('show-context-menu'),
});
`;
fs.writeFileSync(path.join(__dirname, 'preload.js'), preloadContent, 'utf-8');

// ── IPC ───────────────────────────────────────────────────────────────────────
ipcMain.handle('get-jarvis-status', async () => {
  const result = await fetchJSON('http://localhost:3000/api/health');
  return result ? { online: true, ...result } : { online: false };
});

ipcMain.handle('open-cockpit', () => {
  shell.openExternal('http://localhost:3000');
  return true;
});

ipcMain.handle('move-to-center', () => {
  if (!mainWindow) return;
  const { width, height } = screen.getPrimaryDisplay().workAreaSize;
  mainWindow.setPosition(Math.round(width / 2 - 100), Math.round(height / 2 - 100));
});

ipcMain.handle('close-pet', () => { app.quit(); });

ipcMain.on('drag-start', (e, screenX, screenY) => {
  if (!mainWindow) return;
  const [winX, winY] = mainWindow.getPosition();
  dragOffset = { x: screenX - winX, y: screenY - winY };
});

ipcMain.on('drag-move', (e, screenX, screenY) => {
  if (!mainWindow || !dragOffset) return;
  mainWindow.setPosition(screenX - dragOffset.x, screenY - dragOffset.y);
});

ipcMain.on('drag-stop', () => { dragOffset = null; });

ipcMain.on('show-context-menu', () => {
  if (!mainWindow) return;
  const menu = Menu.buildFromTemplate([
    { label: 'Abrir Cockpit', click: () => shell.openExternal('http://localhost:3000') },
    {
      label: 'Mover pro Centro',
      click: () => {
        const { width, height } = screen.getPrimaryDisplay().workAreaSize;
        if (mainWindow) mainWindow.setPosition(Math.round(width / 2 - 100), Math.round(height / 2 - 100));
      }
    },
    { type: 'separator' },
    { label: 'Fechar', click: () => app.quit() }
  ]);
  menu.popup({ window: mainWindow });
});

// ── App Init ──────────────────────────────────────────────────────────────────
app.whenReady().then(() => {
  // Sem ícone no Dock — só menu bar
  app.dock?.hide();

  createTray();
  createPetWindow();

  // Poll imediato + a cada 30s
  pollHealth();
  pollTimer = setInterval(pollHealth, 30000);

  // Se JARVIS não responder em 5s, inicia via LaunchAgent
  setTimeout(async () => {
    const r = await fetchJSON('http://localhost:3000/api/health');
    if (!r) startJarvisServer();
  }, 5000);
});

app.on('before-quit', () => {
  if (pollTimer) clearInterval(pollTimer);
});

// Não sair quando janelas fecham — o tray mantém vivo
app.on('window-all-closed', () => {
  // intencionalmente vazio — tray mantém o app vivo
});
