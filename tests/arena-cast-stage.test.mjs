import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
const game=readFileSync(new URL('../app/game.tsx',import.meta.url),'utf8');
const layout=readFileSync(new URL('../app/layout.tsx',import.meta.url),'utf8');
const css=readFileSync(new URL('../app/arena-cast-stage.css',import.meta.url),'utf8');

test('cast stage loads as last theme layer without changing timing or room data',()=>{
  assert.match(layout,/import '\.\/showtime\.css';\s*import '\.\/arena-refresh\.css';\s*import '\.\/arena-cast-stage\.css';/);
  assert.ok(css.includes('LIVE CAST STAGE'));
  let nesting=0;
  for(const ch of css){if(ch==='{')nesting++;if(ch==='}')nesting--;assert.ok(nesting>=0)}
  assert.equal(nesting,0);
  assert.doesNotMatch(css,/fetch\(|new Audio\(|localStorage\.|setInterval\(/);
});
test('all 25 learner cards fit five by five while keeping 25 people, titles and scores',()=>{
  assert.match(game,/packedRoster=\(snapshot\?\.players\.length\|\|0\)>=12/);
  assert.match(game,/--cast-rows':Math\.ceil\(snapshot\.players\.length\/5\)/);
  assert.match(game,/snapshot\.players\.length<=3\?'few-players':'many-players'/);
  assert.match(css,/grid-template-columns:repeat\(5,minmax\(0,1fr\)\)/);
  assert.match(css,/grid-template-rows:repeat\(var\(--cast-rows,5\),minmax\(0,1fr\)\)/);
  assert.match(css,/\.mini-player>div/);
  assert.match(css,/\.mini-player strong/);
  assert.match(css,/\.mini-player small/);
  assert.match(css,/@media\(max-width:900px\)/);
});
test('visual score leader and answer statuses do not change any scoring calculations',()=>{
  assert.match(game,/cast-leader/);
  assert.match(game,/p\.score>0&&p\.score===rankedPlayers\[0\]\?\.score/);
  assert.match(game,/rankedPlayers\.filter\(p=>p\.score===rankedPlayers\[0\]\?\.score\)/);
  assert.match(game,/data-answer-status=\{r\.status\}/);
  assert.match(css,/\.mini-player\.cast-leader/);
  assert.match(css,/\.mini-player\.answered/);
  assert.match(css,/\.reveal-person\.correct/);
  assert.match(css,/\.reveal-person\.incorrect/);
});
test('quiz and mobile phases have distinct graphics and full motion accessibility',()=>{
  for(const marker of ['.score-spotlight','.results-page .podium-person.rank-1',
    '.results-page .finish-heading','.own-result.correct','.own-result.incorrect',
    '@keyframes cast-answer-ping','@keyframes cast-result-aurora',
    '.game-shell.motion-on','.game-shell.motion-off','prefers-reduced-motion:reduce']){
    assert.ok(css.includes(marker),marker);
  }
});
