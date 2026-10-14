import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
const css=readFileSync(new URL('../app/live-cast-space.css',import.meta.url),'utf8');
const layout=readFileSync(new URL('../app/layout.tsx',import.meta.url),'utf8');
const game=readFileSync(new URL('../app/game.tsx',import.meta.url),'utf8');
const stage=readFileSync(new URL('../app/arena-cast-stage.css',import.meta.url),'utf8');
const browser=readFileSync(new URL('../scripts/test-browser-smoke.mjs',import.meta.url),'utf8');
test('The active right-side player board is sized for a class at all player counts',()=>{
 for(const token of ['.host-question.question-layout:not(.reveal-mode)','clamp(415px,37vw,620px)!important','max-width:1120px']){
   assert.ok(css.includes(token),'Missing stage rule '+token);
 }
 assert.ok(layout.includes("import './live-cast-space.css';"));
});
test('One avatar has a bounded score card, never an enormous full-height portrait',()=>{
 for(const token of ['.score-spotlight{','max-height:142px','.spotlight-avatar{','max-height:136px',
 'เวทีพร้อมต้อนรับผู้เล่นเพิ่มเติม']){
   assert.ok(css.includes(token),'Missing compact spotlight style '+token);
 }
});
test('The real class remains 25 named avatars in a 5-by-5 grid',()=>{
 assert.ok(game.includes("packedRoster=(snapshot?.players.length||0)>=12"));
 assert.ok(stage.includes('grid-template-columns:repeat(5,minmax(0,1fr))'));
 assert.ok(game.includes('role="listitem" title={p.name'));
 assert.ok(browser.includes('25-real-players-question-stage'));
 assert.ok(browser.includes('singlePlayerStageWidth'));
});
test('All visual updates keep mobile, reveal and reduced-motion behaviour isolated',()=>{
 assert.ok(css.includes('@media(prefers-reduced-motion:reduce)'));
 assert.ok(css.includes('@media(min-width:901px)'));
 assert.ok(!css.includes('data-role="player"'));
 let balance=0;for(const ch of css){if(ch==='{')balance++;else if(ch==='}')balance--;assert.ok(balance>=0)}
 assert.equal(balance,0);
});
