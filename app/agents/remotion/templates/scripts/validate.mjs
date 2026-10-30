import {execFileSync} from 'node:child_process';

execFileSync('npx', ['--no-install', 'tsc', '--noEmit'], {
  cwd: '/app',
  stdio: 'inherit',
});
execFileSync('npx', ['--no-install', 'remotion', 'compositions', 'src/index.ts'], {
  cwd: '/app',
  stdio: 'inherit',
});
