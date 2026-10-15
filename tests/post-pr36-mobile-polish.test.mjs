import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
const css=readFileSync(new URL('../app/complete-game-art.css',import.meta.url),'utf8');
test('Compact mobile QR retains a scan-safe square and readable labels',()=>{
  assert.match(css,/@media\(max-width:480px\)/);
  assert.match(css,/width:min\(100%,215px\)!important/);
  assert.match(css,/@media\(max-width:360px\)/);
  assert.match(css,/width:min\(100%,190px\)!important/);
  assert.match(css,/white-space:normal/);
  assert.match(css,/overflow-wrap:anywhere/);
  assert.match(css,/filter:none!important/);
});
test('Mobile mascot is decorative and feedback reserves space for text',()=>{
  assert.match(css,/\.own-result:has\(> \.learner-reveal-art\)/);
  assert.match(css,/padding-right:max\(58px,18%\)!important/);
  assert.match(css,/\.learner-reveal-art\{[\s\S]*?pointer-events:none/);
  assert.match(css,/\.game-shell\.motion-off :is/);
  assert.match(css,/@media\(prefers-reduced-motion:reduce\)/);
});