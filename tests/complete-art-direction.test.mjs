import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';

const html=readFileSync(new URL('../app/game.tsx',import.meta.url),'utf8');
const art=readFileSync(new URL('../app/components/game-art.tsx',import.meta.url),'utf8');
const css=readFileSync(new URL('../app/complete-art-direction.css',import.meta.url),'utf8');
const layout=readFileSync(new URL('../app/layout.tsx',import.meta.url),'utf8');
const source=readFileSync(new URL('../public/art/nhk-staff-original.svg',import.meta.url),'utf8');

test('The supplied original employee illustration is actually bundled and not regenerated',()=>{
 assert.ok(source.startsWith('<svg'));
 assert.ok(source.includes('href="data:image/webp;base64,'));
 assert.ok(source.includes('width="405" height="261"'));
 assert.ok(art.includes('src="/art/nhk-staff-original.svg"'));
 assert.ok(!art.includes('NHK</text>'),'Do not synthesize or repaint company logo');
 assert.ok(!art.includes('shirtColor:'),'Do not change staff uniform styling');
});
test('Each game screen has intentional context-dependent artwork',()=>{
 for(const expected of [
 'pose="welcome" className="entry-friendly-robot"',
 'pose="welcome" className="selection-helper-robot"',
 'className="arena-qr-zone"',
 'pose="scan" className="qr-guide-mascot"',
 'className="lobby-staff-illustration"',
 'pose="think" className="question-corner-mascot"',
 'pose="explain" className="answer-guide-mascot"',
 'className="finish-celebration-art"',
 'pose="celebrate" className="finish-robot-illustration"',
 ])assert.ok(html.includes(expected),'Missing screen artwork: '+expected);
 for(const v of ['type Pose','welcome','scan','think','explain','celebrate']){
  assert.ok(art.includes(v));
 }
});
test('Live QR remains a real scan target, independent from decoration',()=>{
 assert.ok(html.includes('QRCode.toDataURL(url,{width:320'));
 assert.ok(html.includes('className="arena-qr-zone"'));
 assert.ok(css.includes('.arena-qr-zone .qr img'));
 assert.ok(css.includes('filter:none!important'));
 assert.ok(css.includes('animation:none!important'));
 assert.ok(css.includes('position:relative;z-index:2'));
});
test('25 users never share the empty-state decoration and page fit is preserved',()=>{
 assert.ok(html.includes('snapshot.players.length===0&&(isHost?'));
 assert.ok(css.includes('max-height:800px'));
 assert.ok(css.includes('max-width:650px'));
 assert.ok(css.includes('prefers-reduced-motion:reduce'));
 assert.ok(!css.includes('grid-template-rows:repeat(5'));
 assert.ok(!css.includes('.host-scored-roster.packed-players'));
 assert.ok(layout.indexOf("import './complete-art-direction.css';")>layout.indexOf("import './eye-comfort-palette.css';"));
 let balance=0;for(const c of css){if(c==='{')balance++;if(c==='}')balance--;assert.ok(balance>=0)}
 assert.equal(balance,0);
});
