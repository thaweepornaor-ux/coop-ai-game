import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
const game=readFileSync(new URL('../app/game.tsx',import.meta.url),'utf8');
const css=readFileSync(new URL('../app/showtime.css',import.meta.url),'utf8');
const layout=readFileSync(new URL('../app/layout.tsx',import.meta.url),'utf8');

test('premium game-show theme loads after original CSS and covers every view',()=>{
 assert.match(layout,/import '\.\/globals\.css';\s*import '\.\/showtime\.css';/);
 for(const expression of ['radial-gradient','box-shadow','arena-qr-entrance','arena-player-entrance','arena-answer-in','arena-reveal','.host-lobby','.host-question','.quick-player','.results-page']){
   assert.ok(css.includes(expression),expression+' missing from theme');
 }
});
test('projector time has huge digits, urgent five-second flash and accessible motion cutoff',()=>{
 assert.match(game,/className=\{'countdown '/);
 assert.match(game,/timer-kicker/);
 assert.match(game,/timer-value/);
 assert.match(css,/\.countdown\{[\s\S]*?width:clamp\(138px/);
 assert.match(css,/@keyframes arena-last-five/);
 assert.match(css,/\.countdown\.urgent\{animation:arena-last-five/);
 assert.match(css,/@media\(prefers-reduced-motion:reduce\)/);
 assert.match(css,/\.motion-off \.countdown\.urgent\{animation:none!important\}/);
});
test('all 25 learner result pictures are compact and available in the projector viewport',()=>{
 assert.match(game,/reveal-mode/);
 assert.match(game,/className="reveal-tiles"/);
 assert.match(game,/className="reveal-avatar"/);
 assert.match(game,/className=\{'reveal-person '/);
 assert.match(game,/snapshot\.results/);
 assert.match(css,/grid-template-columns:repeat\(var\(--reveal-columns\),minmax\(0,1fr\)\)/);
 assert.match(css,/grid-template-rows:repeat\(5,minmax\(0,1fr\)\)/);
 assert.match(css,/\.session-footer\{display:none\}/);
});
