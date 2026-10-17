import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';

const read=(p)=>readFileSync(new URL(p,import.meta.url),'utf8');

test('published game contract agrees with implemented 15-question countdown',()=>{
  const readme=read('../README.md');
  const game=read('../app/game.tsx');
  const browser=read('../scripts/test-browser-smoke.mjs');
  const questionFile=read('../server/questions.ts');
  const values=[...questionFile.matchAll(/"timeLimitSeconds":\s*(\d+)/g)].map(m=>Number(m[1]));
  assert.equal(values.length,15);
  assert.ok(values.every(v=>v===8),'all deployed questions are eight seconds');
  assert.match(readme,/\*\*8-second answer window\*\*/);
  assert.match(game,/timer\/8/);
  assert.match(browser,/8-second answer deadline/);
  assert.doesNotMatch(readme,/10-second answer window/i,'no stale contradictory teacher instructions');
});

test('release documentation cannot silently imply staging deployment or physical rehearsal',()=>{
  const readme=read('../README.md');
  assert.match(readme,/Do not trigger Cloudflare Staging deployment/);
  assert.match(readme,/A passing check does \*\*not\*\* certify physical mobile devices/);
  assert.match(readme,/a real 25-person rehearsal/i);
});

test('host receives visible preflight warning before starting without approved R sound',()=>{
 const game=read('../app/game.tsx');
 const css=read('../app/globals.css');
 assert.match(game,/host-audio-preflight/);
 assert.match(game,/เสียงเฉลย R01–R15 ยังไม่พร้อมบนเครื่องนี้/);
 assert.match(game,/กรุณาเลือก ZIP และทดลองฟังก่อนเริ่มกิจกรรม/);
 assert.match(game,/role="status" aria-live="polite"/);
 assert.match(game,/host-timing-preflight/);
 assert.match(game,/เปิดให้ตอบ 8 วินาทีต่อข้อ/);
 assert.match(css,/\.host-audio-preflight\.missing/);
});
