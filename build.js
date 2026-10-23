const fs = require('fs');
const path = require('path');
const { spawnSync } = require('child_process');

let frontendDir = path.resolve(__dirname, 'frontend');
if (!fs.existsSync(frontendDir)) {
  frontendDir = path.resolve(__dirname, '../frontend');
}
if (!fs.existsSync(frontendDir)) {
  frontendDir = path.resolve(process.cwd(), 'frontend');
}
if (!fs.existsSync(frontendDir)) {
  frontendDir = path.resolve(process.cwd(), '../frontend');
}

console.log('[Poise Build] Building frontend in:', frontendDir);

const res = spawnSync('npm', ['run', 'build'], {
  cwd: frontendDir,
  stdio: 'inherit',
  shell: true,
});

process.exit(res.status || 0);
