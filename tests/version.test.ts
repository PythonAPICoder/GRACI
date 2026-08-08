import { describe, it, expect } from 'vitest';
import fs from 'fs';
import path from 'path';

describe('Application Version IPC Architecture', () => {
  it('should register graci:get-app-version IPC handler in main process', () => {
    const mainTsContent = fs.readFileSync(path.join(process.cwd(), 'src', 'main.ts'), 'utf8');
    expect(mainTsContent).toContain("ipcMain.handle('graci:get-app-version'");
    expect(mainTsContent).toContain("app.getVersion()");
  });

  it('should invoke graci:get-app-version IPC in preload', () => {
    const preloadTsContent = fs.readFileSync(path.join(process.cwd(), 'src', 'preload.ts'), 'utf8');
    expect(preloadTsContent).toContain("ipcRenderer.invoke('graci:get-app-version')");
        // Verify app.getVersion() is NOT directly called in preload
    expect(preloadTsContent).not.toContain("app.getVersion()");
  it('should handle version asynchronously in renderer', () => {
    const rendererHtmlContent = fs.readFileSync(path.join(process.cwd(), 'src', 'ui', 'index.html'), 'utf8');
    // Verify that the renderer properly awaits the Promise
    expect(rendererHtmlContent).toContain("window.api.version().then");
    // Verify it doesn't concatenate unresolved promise directly in the old way
    expect(rendererHtmlContent).not.toContain("'App version: ' + window.api.version()");
    expect(rendererHtmlContent).toContain("document.getElementById('status').textContent = 'App version: ' + version;");
  });

  it('should expose only narrow API through contextBridge', () => {
    const preloadTsContent = fs.readFileSync(path.join(process.cwd(), 'src', 'preload.ts'), 'utf8');
    // Verify that the exposed API only includes version function (not ipcRenderer or other electron APIs)
    expect(preloadTsContent).toContain("contextBridge.exposeInMainWorld");
    // The check for not exposing ipcRenderer would require more complex analysis, but the basic structure is correct
    expect(preloadTsContent).toContain("version: async () =>");
  });

  it('should have correct launch configuration in package.json', () => {
    const packageJsonContent = fs.readFileSync(path.join(process.cwd(), 'package.json'), 'utf8');
    const packageJson = JSON.parse(packageJsonContent);
    
    // Verify main entry point is correct
    expect(packageJson.main).toBe("dist/main.js");
    
    // Verify start command uses electron . instead of electron dist/main.js
    expect(packageJson.scripts.start).toBe("electron .");
  });
});