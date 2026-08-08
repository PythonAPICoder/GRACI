#!/usr/bin/env node
const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

console.log('Building G.R.A.C.I. Phase 1...');

try {
  console.log('1. Compiling TypeScript...');
  execSync('npx tsc', { stdio: 'inherit' });

  console.log('2. Creating dist/ui directory...');
  const uiDir = path.join(process.cwd(), 'dist', 'ui');
  if (!fs.existsSync(uiDir)) {
    fs.mkdirSync(uiDir, { recursive: true });
  }

  console.log('3. Copying UI file...');
  const sourceHtml = path.join(process.cwd(), 'src', 'ui', 'index.html');
  const targetHtml = path.join(uiDir, 'index.html');
  fs.copyFileSync(sourceHtml, targetHtml);

  console.log('4. Verifying build output...');
  console.log('  - dist/main.js:', fs.existsSync(path.join(process.cwd(), 'dist', 'main.js')) ? '✓' : '✗');
  console.log('  - dist/preload.js:', fs.existsSync(path.join(process.cwd(), 'dist', 'preload.js')) ? '✓' : '✗');
  console.log('  - dist/ui/index.html:', fs.existsSync(targetHtml) ? '✓' : '✗');

  console.log('\nBuild complete!');
} catch (error) {
  console.error('Build failed:', error.message);
  process.exit(1);
}