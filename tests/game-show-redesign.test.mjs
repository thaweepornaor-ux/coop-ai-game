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

test('showtime projector keeps its countdown outside the question and protects long Thai text',()=>{
 assert.match(game,/const countdownNode=/);
 assert.match(game,/:countdownNode/);
 assert.match(game,/className="projector-timer-wrap"/);
 assert.match(game,/className=\{'question-layout '/);
 assert.match(game,/denseQuestion=questionLength>115\|\|longestOption>90/);
 assert.match(css,/PROJECTOR FIT \+ COLORWAVE/);
 assert.match(css,/grid-template-rows:repeat\(3,minmax\(0,1fr\)\)/);
 assert.match(css,/\.host-question\.dense-question:not\(\.reveal-mode\)/);
 assert.match(css,/\.answer\.answer-0/);
 assert.match(css,/\.answer\.answer-1/);
 assert.match(css,/\.answer\.answer-2/);
 assert.match(css,/arena-light-sweep/);
 assert.match(css,/motion-off \.host-question/);
});

test('live instructor console has visible avatars, participation meter and three distinctly colored answer panels',()=>{
 assert.match(game,/className="live-score-stage"/);
 assert.match(game,/className="answer-meter" role="progressbar"/);
 assert.match(game,/className="score-spotlight"/);
 assert.match(game,/className="spotlight-avatar"/);
 assert.match(game,/spotlight-state/);
 assert.match(game,/snapshot\.players\.length<=3/);
 assert.match(css,/AI ARENA V2/);
 assert.match(css,/\.answer\.answer-0\{/);
 assert.match(css,/\.answer\.answer-1\{/);
 assert.match(css,/\.answer\.answer-2\{/);
 assert.match(css,/@keyframes arena-stage-rise/);
 assert.match(css,/@keyframes arena-live-breathe/);
 assert.match(css,/\.motion-off \.live-indicator i/);
});

test('25-player presenter switches to compact no-scroll grid without changing the 25-player reveal',()=>{
 assert.match(game,/packedRoster=\(snapshot\?\.players\.length\|\|0\)>=12/);
 assert.match(game,/packed-players/);
 assert.match(game,/--packed-rows/);
 assert.match(game,/role="listitem" title=\{p.name/);
 assert.match(css,/25-CONTESTANT LIVE HUD/);
 assert.match(css,/grid-template-columns:repeat\(3,minmax\(0,1fr\)\)/);
 assert.match(css,/grid-template-rows:repeat\(var\(--packed-rows,9\),minmax\(0,1fr\)\)/);
 assert.match(css,/\.host-question\.packed-roster:not\(\.reveal-mode\)/);
 assert.match(css,/\.host-scored-roster\.packed-players/);
});

test('Thai presenter narration reads all question choices and the revealed explanation, on opt-in only',()=>{
 assert.match(game,/SpeechSynthesisUtterance/);
 assert.match(game,/speechSynthesis\.cancel\(\)/);
 assert.match(game,/utterance\.lang='th-TH'/);
 assert.match(game,/utterance\.rate=1\.18/);
 assert.match(game,/q\.options\[0\]/);
 assert.match(game,/q\.options\[1\]/);
 assert.match(game,/q\.options\[2\]/);
 assert.match(game,/state\.explanation\|\|''/);
 assert.match(game,/narrationEnabled,setNarrationEnabled/);
 assert.match(game,/narrationKey\.current===key/);
 assert.match(game,/aria-pressed=\{narrationEnabled\}/);
 assert.match(game,/if\(narrationEnabled\)/);
});
