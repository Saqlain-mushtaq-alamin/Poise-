const fs = require('fs');
const path = require('path');
const { spawn } = require('child_process');

// Determine frontend directory relative to current working directory or script location
let frontendDir = path.resolve(__dirname, '../frontend');
if (!fs.existsSync(frontendDir)) {
  frontendDir = path.resolve(process.cwd(), 'frontend');
}
if (!fs.existsSync(frontendDir)) {
  frontendDir = path.resolve(process.cwd(), '../frontend');
}

console.log('[Poise Dev] Starting frontend in:', frontendDir);

const child = spawn('npm', ['run', 'dev'], {
  cwd: frontendDir,
  stdio: 'inherit',
  shell: true,
});

child.on('exit', (code) => {
  process.exit(code || 0);
});
