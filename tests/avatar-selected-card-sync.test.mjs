import test from 'node:test';import assert from 'node:assert/strict';import {readFileSync} from 'node:fs';
const source=readFileSync('app/components/simple-wardrobe.tsx','utf8');
test('current selected card renders edited wardrobe instead of original immutable preset',()=>{
 assert.match(source,/options=\{selectedId===c\.id\?avatar:\{/);
 assert.match(source,/svgOnly pose=\{poseForAvatarPreset\(c\.id\)\}/);
 assert.match(source,/onClick=\{\(\)=>change\(key,option\.value\)\}/);
});
