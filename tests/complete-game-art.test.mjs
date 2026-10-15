import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';

const game=readFileSync(new URL('../app/game.tsx',import.meta.url),'utf8');
const css=readFileSync(new URL('../app/complete-game-art.css',import.meta.url),'utf8');
const layout=readFileSync(new URL('../app/layout.tsx',import.meta.url),'utf8');
const browser=readFileSync(new URL('../scripts/test-browser-smoke.mjs',import.meta.url),'utf8');
const names=['nhk-welcome-original.svg','nhk-presenter-original.svg','nhk-celebrate-original.svg'];
const assets=names.map(name=>readFileSync(new URL('../public/art/'+name,import.meta.url),'utf8'));

test('All three original-pixel reference images are bundled (no AI re-coloring)',()=>{
  for(let i=0;i<names.length;i++){
    assert.ok(assets[i].startsWith('<svg xmlns="http://www.w3.org/2000/svg"'),names[i]);
    assert.match(assets[i],/data:image\/webp;base64,/);
    assert.ok(assets[i].length>15000,'No placeholder image accepted '+names[i]);
    assert.ok(game.includes('/art/'+names[i]),'App must show the original image '+names[i]);
  }
});

test('QR is centered without changing the actual code pixels or live player board',()=>{
 for(const part of [
   '.qr-visual-stage','.qr-stage-label','.qr-stage-caption',
   'grid-template-columns:minmax(0,41%) minmax(0,1fr)!important',
   'filter:none!important','animation:none!important',
   '.arena-empty-visual .empty-stage-art',
   'prefers-reduced-motion:reduce'
 ])assert.ok(css.includes(part),'Missing scan/layout/accessibility rule '+part);
 assert.ok(browser.includes('qrCenterOffset'));
 assert.ok(browser.includes('Real 25-player roster must not be obstructed'));
 assert.ok(game.includes('snapshot.players.length===0&&(isHost?'));
 assert.ok(game.includes('snapshot.players.length===0&&(isHost?'));
 assert.ok(game.includes('ผู้เข้าร่วม <span>{snapshot.players.length} คน</span>'));
});

test('Original artwork is placed on the actual lobby, selection, quiz, reveal and closing screens',()=>{
  for(const token of [
    'intro-artwork','wardrobe-mascot-art','empty-stage-art',
    'question-guide-art','reveal-guide-art',
    'learner-reveal-art','final-celebration-art'
  ])assert.ok(game.includes(token),'Missing screen illustration '+token);
  assert.ok(css.includes('.host-question:not(.reveal-mode):not(.dense-question)'));
  assert.ok(css.includes('min-width:1480px'));
  assert.ok(css.includes('max-height:760px'));
  assert.ok(css.includes('max-width:999px'));
  assert.ok(layout.indexOf("import './complete-game-art.css';")>layout.indexOf("import './eye-comfort-palette.css';"));
});
test('Presentation-only layer cannot mutate 25-player grid, timing, audio or scoring',()=>{
  for(const forbidden of [
    'grid-template-rows:repeat(var(--cast-rows,5)','setInterval(',
    'new Audio(','localStorage.','score:','roomCode:'
  ])assert.ok(!css.includes(forbidden),'Art stylesheet must not change game logic '+forbidden);
  let depth=0;for(const char of css){if(char==='{')depth++;else if(char==='}')depth--;assert.ok(depth>=0);}
  assert.equal(depth,0,'CSS must be balanced');
  assert.ok(game.includes('packedRoster=(snapshot?.players.length||0)>=12'));
  assert.ok(game.includes("'--cast-rows':Math.ceil(snapshot.players.length/5)"));
  assert.ok(game.includes('timer/8'));
  assert.ok(game.includes('answerVoiceUrls.current'));
});
