import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';

const avatar=readFileSync('app/components/avatar.tsx','utf8');
const wardrobe=readFileSync('app/components/simple-wardrobe.tsx','utf8');
const svg=readFileSync('shared/avatar.js','utf8');

test('gallery and interactive live preview use identical SVG art for all poses',()=>{
 assert.match(avatar,/svgOnly\?:boolean/);
 assert.match(avatar,/!svgOnly&&pose==='stand'&&complete/);
 assert.match(avatar,/!svgOnly&&pose==='stand'&&complete&&<div/);
 assert.match(wardrobe,/\}\} svgOnly pose=\{/);
 assert.match(wardrobe,/<Avatar options=\{avatar\} svgOnly pose=\{previewPose\}/);
});
test('hand and fingertip SVG markup has no duplicate fill attributes',()=>{
 assert.doesNotMatch(svg,/fill="none" fill="none"/);
});
