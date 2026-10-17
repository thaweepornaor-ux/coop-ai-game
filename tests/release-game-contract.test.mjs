import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {questions} from '../server/questions.ts';

const read=(p)=>readFileSync(new URL(p,import.meta.url),'utf8');

test('published game contract agrees with implemented 15-question countdown',()=>{
  const readme=read('../README.md');
  const game=read('../app/game.tsx');
  const browser=read('../scripts/test-browser-smoke.mjs');
  assert.equal(questions.length,15);
  assert.ok(questions.every(q=>q.timeLimitSeconds===8),'all deployed questions are eight seconds');
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
