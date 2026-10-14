import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
const sheet=readFileSync(new URL('../app/eye-comfort-palette.css',import.meta.url),'utf8');
const layout=readFileSync(new URL('../app/layout.tsx',import.meta.url),'utf8');
const game=readFileSync(new URL('../app/game.tsx',import.meta.url),'utf8');
function lum(hex){
 const rgb=hex.replace('#','').match(/.{2}/g).map(v=>parseInt(v,16)/255);
 const v=rgb.map(x=>x<=.04045?x/12.92:((x+.055)/1.055)**2.4);
 return v[0]*.2126+v[1]*.7152+v[2]*.0722;
}
const ratio=(a,b)=>{const l1=lum(a),l2=lum(b);return (Math.max(l1,l2)+.05)/(Math.min(l1,l2)+.05)};
test('Eye-comfort palette loads after every previously deployed stylesheet',()=>{
 const a=layout.indexOf("import './live-cast-space.css';");
 const b=layout.indexOf("import './eye-comfort-palette.css';");
 assert.ok(a>=0 && b>a,'Late load required to replace old neon values');
 assert.ok(!sheet.includes('grid-template-columns:'),'Do not alter 25-player layout');
 assert.ok(!sheet.includes('grid-template-rows:'),'Do not alter answer/results grid');
 assert.ok(!sheet.includes('font-size:'),'Typography remains unchanged');
 let depth=0;
 for(const ch of sheet){if(ch==='{')depth++;if(ch==='}')depth--;assert.ok(depth>=0)}
 assert.equal(depth,0);
});
test('Main readable foreground/background combinations meet at least 4.5:1',()=>{
 for(const [foreground,background] of [
   ['#213953','#ffffff'],['#243952','#f4f8fe'],
   ['#31516d','#f4f8fd'],['#253b55','#e5f1fc'],
   ['#253b55','#efeffb'],['#253b55','#fbf4e7'],
   ['#1f5c4a','#e0f2e9'],['#8b444c','#fae9ea'],
   ['#314c67','#e9f0f9'],['#ffffff','#47759d'],
 ]){
   assert.ok(ratio(foreground,background)>=4.5,foreground+'/'+background+' contrast '+ratio(foreground,background).toFixed(2));
 }
});
test('All screens have restful colors without full-screen flash animation',()=>{
 for(const marker of [
   "html{background:#e8f0f7!important;}",
   "linear-gradient(150deg,#fff,#f4f8fe)",
   '.simple-join-ticket .qr',
   '.question-card .answer.answer-0',
   '.question-card .answer.answer-1',
   '.question-card .answer.answer-2',
   '.host-scored-roster.packed-players .mini-player',
   '.host-question.reveal-mode .explanation',
   '.host-question.reveal-mode .reveal-person.correct',
   '.results-page .finish-heading',
   '.quick-player .wardrobe',
   'motion-on::before','animation:none!important',
   '@media(prefers-reduced-motion:reduce)']){
   assert.ok(sheet.includes(marker),'Missing palette part '+marker);
 }
 assert.ok(game.includes('aria-label={\\'คะแนนและสถานะผู้เรียน \\''));
 assert.ok(!sheet.includes('#ff00ff'),'Avoid vivid decorative magenta');
});
