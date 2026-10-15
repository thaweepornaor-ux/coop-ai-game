import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
const css=readFileSync(new URL('../app/mobile-all-screens.css',import.meta.url),'utf8');
const layout=readFileSync(new URL('../app/layout.tsx',import.meta.url),'utf8');
test('mobile layout loads after existing art and covers learner journey',()=>{
  assert.ok(layout.indexOf("import './mobile-all-screens.css';")>layout.indexOf("import './complete-game-art.css';"));
  for(const section of ['quick-player','player-lobby','question-card','answer-grid','results-page','score-row','reset-modal','modal-backdrop']){
    assert.ok(css.includes(section),'Missing mobile coverage: '+section);
  }
});
test('no horizontal overflow and minimum phone breakpoints without changing game logic',()=>{
  assert.match(css,/@media\s*\(max-width:\s*767px\)/);
  assert.match(css,/@media\(max-width:360px\)/);
  assert.match(css,/overflow-x:clip/);
  assert.match(css,/grid-template-columns:minmax\(0,1fr\)/);
  assert.match(css,/prefers-reduced-motion:reduce/);
  assert.ok(!/fetch\(|setInterval\(|localStorage\./.test(css));
  let depth=0;for(const c of css){if(c==='{')depth++;if(c==='}')depth--;assert.ok(depth>=0)}
  assert.equal(depth,0);
});