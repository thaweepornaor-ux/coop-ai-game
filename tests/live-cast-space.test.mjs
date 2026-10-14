import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
const css=readFileSync(new URL('../app/live-cast-space.css',import.meta.url),'utf8');
const layout=readFileSync(new URL('../app/layout.tsx',import.meta.url),'utf8');
const game=readFileSync(new URL('../app/game.tsx',import.meta.url),'utf8');
const stage=readFileSync(new URL('../app/arena-cast-stage.css',import.meta.url),'utf8');
const browser=readFileSync(new URL('../scripts/test-browser-smoke.mjs',import.meta.url),'utf8');

test('Right-hand live player stage has class-sized width in every teacher question phase',()=>{
 assert.match(css,/\\.host-question\\.question-layout:not\\(\\.reveal-mode\\)/);
 assert.match(css,/clamp\\(415px,37vw,620px\\)!important/);
 assert.match(css,/max-width:1120px/);
 assert.match(layout,/import '\\.\\/live-cast-space\\.css';/);
 assert.ok(!css.includes('display:none!important'));
});
test('The single-player spotlight no longer fills the whole right column',()=>{
 assert.match(css,/\\.score-spotlight\\{/);
 assert.match(css,/max-height:142px/);
 assert.match(css,/\\.spotlight-avatar\\{/);
 assert.match(css,/max-height:136px/);
 assert.match(css,/\\.score-spotlight::after\\{/);
 assert.match(css,/เวทีพร้อมต้อนรับผู้เล่นเพิ่มเติม/);
});
test('25-player stage remains a real five-by-five grid with named avatars',()=>{
 assert.match(game,/packedRoster=\\(snapshot\\?\\.players\\.length\\|\\|0\\)>=12/);
 assert.match(stage,/grid-template-columns:repeat\\(5,minmax\\(0,1fr\\)\\)/);
 assert.match(game,/role="listitem" title=\\{p.name/);
 assert.match(browser,/checkProjectorQuestionFit/);
 assert.match(browser,/projector-25-person-reveal-layout/);
});
test('Reduced-motion and mobile player layouts remain untouched',()=>{
 assert.match(css,/@media\\(prefers-reduced-motion:reduce\\)/);
 assert.match(css,/@media\\(min-width:901px\\)/);
 assert.ok(!css.includes('data-role="player"'));
 let depth=0;for(const c of css){if(c==='{')depth++;if(c==='}')depth--;assert.ok(depth>=0)}assert.equal(depth,0);
});
