import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
const css=readFileSync(new URL('../app/host-lobby-fit.css',import.meta.url),'utf8');
const layout=readFileSync(new URL('../app/layout.tsx',import.meta.url),'utf8');
const browser=readFileSync(new URL('../scripts/test-browser-smoke.mjs',import.meta.url),'utf8');

test('Host fit rules load last and do not touch player/question phases',()=>{
  assert.match(layout,/import '\.\/arena-cast-stage\.css';\s*import '\.\/host-lobby-fit\.css';/);
  assert.match(css,/\.game-shell\[data-role="host"\]:has\(> \.host-lobby\)/);
  assert.ok(!css.includes('new Audio(')&&!css.includes('fetch('));
  let balance=0;for(const c of css){if(c==='{')balance++;if(c==='}')balance--;assert.ok(balance>=0);}
  assert.equal(balance,0);
});
test('Every required classroom control has a viewport-fit rule',()=>{
  for(const item of ['height:100svh','flex-direction:column','.topbar','.connection',
    '.host-lobby.lobby','.lobby-main','.roster-panel','.qr',
    '.lobby-main > .button.primary','.session-footer',
    'minmax(390px,.93fr)','overflow-y:auto']){
      assert.ok(css.includes(item),item);
  }
});
test('Short viewport and browser real geometry are covered',()=>{
  for(const item of ['min-width:1000px','min-height:675px','max-height:760px',
    'max-width:999px','max-height:674px',
    'assertHostLobbyFits','host-lobby-fits-viewport',
    'full-lobby-25-participants-fits-projector',
    'width:1280,height:720','width:1366,height:768',
    'width:1600,height:780','width:1920,height:1080']){
    assert.ok((css+'\n'+browser).includes(item),item);
  }
});
