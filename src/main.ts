import * as electron from 'electron';
import * as path from 'node:path';
import { logger } from './core/logging/logger.js';
import * as fs from 'node:fs';
const { app, BrowserWindow, ipcMain } = electron;

let mainWindow = null;

app.whenReady().then(() => {
  logger.info('Electron app starting');

  // Set up IPC handler for application version
  ipcMain.handle('graci:get-app-version', () => {
    return app.getVersion();
  });

  const win = new BrowserWindow({
    width: 1280,
    height: 800,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false
    }
  });

   win.loadFile(path.join(__dirname, 'ui', 'index.html'));
  mainWindow = win;
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});

function createApp() {}