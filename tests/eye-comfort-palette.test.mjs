import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';

const sheet=readFileSync(new URL('../app/eye-comfort-palette.css',import.meta.url),'utf8');
const layout=readFileSync(new URL('../app/layout.tsx',import.meta.url),'utf8');
const styles=readFileSync(new URL('../app/arena-refresh.css',import.meta.url),'utf8');
const lobby=readFileSync(new URL('../app/lobby-showcase.css',import.meta.url),'utf8');
const game=readFileSync(new URL('../app/game.tsx',import.meta.url),'utf8');

test('Rich blue-purple show palette is RESTORED instead of washed-out pastel',()=>{
  assert.ok(sheet.includes('#0b296a 0%,#1a4596 45%,#3c2b83'));
  assert.ok(sheet.includes('color-scheme:dark'));
  assert.ok(styles.includes('linear-gradient(125deg,#092568 0%,#164caa 42%,#44268e 100%)'));
  assert.ok(lobby.includes('linear-gradient(131deg,#176ab9 0%,#234aa7 54%,#5038b4 100%)'));
  assert.ok(!sheet.includes('background:#e8f0f7'));
  assert.ok(!sheet.includes('color-scheme:light'));
  assert.ok(!sheet.includes('linear-gradient(150deg,#fff,#f4f8fe)'));
  assert.ok(layout.indexOf("import './eye-comfort-palette.css';")>layout.indexOf("import './live-cast-space.css';"));
});
test('Retains saturated A/B/C colors while taming blinding halo effects',()=>{
  for(const item of ['.answer.answer-0','.answer.answer-1','.answer.answer-2',
    '.projector-timer-wrap','.countdown.urgent','.simple-join-ticket .qr']){
    assert.ok(sheet.includes(item),'Missing careful selective glow tune '+item);
  }
  assert.ok(sheet.includes('box-shadow:inset 5px 0 0 #65ccf2'));
  assert.ok(sheet.includes('box-shadow:inset 5px 0 0 #ba9bec'));
  assert.ok(sheet.includes('box-shadow:inset 5px 0 0 #efd192'));
  assert.ok(sheet.includes('animation:arena-last-five 1.6s ease-in-out infinite!important'));
  assert.ok(sheet.includes('prefers-reduced-motion:reduce'));
});
test('Theme is pure presentation: 25 real players, QR, sound and rules unchanged',()=>{
  for(const forbidden of ['grid-template-columns:','grid-template-rows:','width:clamp(','font-size:',
      'display:none','Q01.mp3','R01.mp3']){
    assert.ok(!sheet.includes(forbidden),'Visual-only polish should not alter mechanics/geometry: '+forbidden);
  }
  assert.ok(game.includes("snapshot.players.length"));
  assert.ok(game.includes('ผู้เข้าร่วม <span>{snapshot.players.length} คน</span>'));
  let braces=0;
  for(const c of sheet){if(c==='{')braces++;if(c==='}')braces--;assert.ok(braces>=0)}
  assert.equal(braces,0);
});
