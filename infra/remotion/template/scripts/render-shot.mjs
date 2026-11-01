import {execFileSync} from 'node:child_process';

const args = process.argv.slice(2);
const compIndex = args.indexOf('--comp');
const outIndex = args.indexOf('--out');
if (compIndex < 0 || outIndex < 0) {
  console.error('usage: render-shot.mjs --comp <id> --out <path>');
  process.exit(2);
}
const composition = args[compIndex + 1];
const output = args[outIndex + 1];

execFileSync(
  'npx',
  [
    '--no-install',
    'remotion',
    'render',
    'src/index.ts',
    composition,
    output,
    '--codec=h264',
    '--pixel-format=yuv420p',
    '--crf=18',
    '--concurrency=1',
    '--overwrite',
  ],
  {cwd: '/app', stdio: 'inherit'},
);
