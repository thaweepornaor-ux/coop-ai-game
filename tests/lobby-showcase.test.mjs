import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
const game=readFileSync(new URL('../app/game.tsx',import.meta.url),'utf8');
const layout=readFileSync(new URL('../app/layout.tsx',import.meta.url),'utf8');
const css=readFileSync(new URL('../app/lobby-showcase.css',import.meta.url),'utf8');
const fit=readFileSync(new URL('../app/host-lobby-fit.css',import.meta.url),'utf8');

test('Only the instructor lobby gets the presentation overhaul',()=>{
 assert.ok(layout.includes("import './host-lobby-fit.css';\nimport './lobby-showcase.css';"));
 assert.ok(css.includes('.game-shell[data-role="host"] > .host-lobby'));
 assert.ok(!css.includes('new Audio(')&&!css.includes('fetch('));
 assert.ok(fit.includes('height:100svh'));
 let depth=0;for(const ch of css){if(ch==='{')depth++;if(ch==='}')depth--;assert.ok(depth>=0)}
 assert.equal(depth,0,'balanced CSS declarations');
});
test('Prominent QR and real join steps remain interactive',()=>{
 for(const v of ['arena-ticket-content','arena-ticket-eyebrow','arena-join-steps',
  'สแกน QR','เลือกตัวละคร','ตั้งชื่อ','คัดลอกลิงก์สำหรับผู้เรียน']){
  assert.ok(game.includes(v),'missing UI '+v);
 }
 assert.ok(css.includes('.simple-join-ticket .qr'));
});
test('Empty-player visual must disappear once real learners join',()=>{
 assert.ok(game.includes('snapshot.players.length===0&&(isHost?'));
 for(const v of ['arena-empty-stage','arena-holo-person','arena-empty-copy','arena-live-kicker',
   'ผู้เข้าร่วม <span>{snapshot.players.length} คน</span>']){
  assert.ok(game.includes(v),'missing state UI '+v);
 }
 assert.ok(css.includes('.roster-panel:has(.arena-empty-stage)::after'));
 assert.ok(css.includes('.roster:empty'));
 assert.ok(css.includes('.roster-panel .mini-player'));
});
test('Motion respects accessibility settings and fitted viewports',()=>{
 for(const v of ['@media(min-width:1000px) and (min-height:675px) and (max-height:760px)',
  '@media(max-width:999px)','prefers-reduced-motion:reduce','.game-shell.motion-off',
  '@keyframes arena-holo-float','@keyframes arena-qr-sheen']){
  assert.ok(css.includes(v),'missing safeguard '+v);
 }
});

test('Only actual attendees are displayed; no confusing /25 capacity display',()=>{
 assert.ok(game.includes('ผู้เข้าร่วม <span>{snapshot.players.length} คน</span>'));
 for(const quota of ['arena-attendance','aria-valuemax={25}',' / 25 ผู้เล่น','ผู้เล่นสูงสุด 25 คน']){
  assert.ok(!game.includes(quota),'fixed quota element still visible: '+quota);
 }
 assert.ok(!css.includes('arena-attendance'),'unused quota meter styles remain');
});
