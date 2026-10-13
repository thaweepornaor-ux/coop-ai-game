import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';

const layout=readFileSync(new URL('../app/layout.tsx',import.meta.url),'utf8');
const css=readFileSync(new URL('../app/arena-refresh.css',import.meta.url),'utf8');
const game=readFileSync(new URL('../app/game.tsx',import.meta.url),'utf8');

test('vibrant overlay is loaded AFTER the existing game theme',()=>{
  assert.match(layout,/import '\.\/globals\.css';\s*import '\.\/showtime\.css';\s*import '\.\/arena-refresh\.css';/);
  assert.match(css,/AI ARENA \/ VIBRANT LIVE/);
  let depth=0;
  for(const token of css){if(token==='{')depth++;else if(token==='}')depth--;assert.ok(depth>=0,'Invalid CSS brace depth');}
  assert.equal(depth,0,'Stylesheet should close all declaration blocks');
});

test('presenter toolbar and lobby adapt to narrow and short screens, never hide controls',()=>{
  for(const rule of [
    '.game-shell .topbar','.game-shell .topbar .preferences',
    'grid-template-columns:minmax(0,auto) minmax(0,1fr)',
    'grid-template-columns:repeat(2,minmax(0,1fr))',
    'grid-column:1/-1',
    'overflow-wrap:anywhere',
    '.game-shell .host-lobby .simple-join-ticket',
    '.game-shell .host-lobby .roster-panel'
  ]) assert.ok(css.includes(rule),'Missing responsive safeguard: '+rule);
  for(const size of ['max-width:1380px','max-width:1100px','max-width:900px','max-width:650px','max-width:360px','max-height:790px']){
    assert.ok(css.includes(size),'Missing layout breakpoint: '+size);
  }
  assert.match(game,/className="preferences"/);
  assert.match(game,/className="icon-button new-game-top"/);
  assert.doesNotMatch(css,/\.preferences\s*\{[^}]*display\s*:\s*none/i,'Instructor action bar must not disappear');
});

test('consistent vibrant styling covers teacher, learner, narration, questions, reveal and results',()=>{
  for(const rule of [
    '.game-shell .host-lobby .lobby-main','.game-shell .voice-setup-panel',
    '.game-shell .host-lobby .simple-join-ticket .qr',
    '.game-shell .question-card','.game-shell .answer.answer-0',
    '.game-shell .answer.answer-1','.game-shell .answer.answer-2',
    '.game-shell .quick-player .wardrobe',
    '.game-shell .reveal-person.correct',
    '.game-shell .results-page .finish-heading',
    '.game-shell .results-page .scoreboard'
  ]) assert.ok(css.includes(rule),'Missing refreshed surface: '+rule);
  for(const color of ['--arena-electric','--arena-cyan','--arena-violet','--arena-gold']){
    assert.ok(css.includes(color),'Missing palette token '+color);
  }
});

test('ambient and phase motion can be disabled by UI toggle or reduced-motion preference',()=>{
  assert.match(game,/motion\?'motion-on':'motion-off'/);
  assert.match(css,/@keyframes arena-vibrant-aurora/);
  assert.match(css,/@keyframes arena-vibrant-stars/);
  assert.match(css,/@keyframes arena-vibrant-arrive/);
  assert.match(css,/@keyframes arena-vibrant-live/);
  assert.match(css,/@keyframes arena-vibrant-winner/);
  assert.match(css,/\.game-shell\.motion-on::before/);
  assert.match(css,/\.game-shell\.motion-off::before/);
  assert.match(css,/@media\(prefers-reduced-motion:reduce\)/);
  assert.match(css,/animation:none!important/);
});

test('refresh is presentation-only: question duration, voice and new-room behavior remain in game code',()=>{
  assert.match(game,/const countdownNode=/);
  assert.match(game,/voiceReady/);
  assert.match(game,/setResetDialog\(true\)/);
  assert.match(game,/className="reveal-tiles"/);
  assert.ok(!/fetch\(|new Audio\(|localStorage\./.test(css),'CSS cannot change networking or state');
});
