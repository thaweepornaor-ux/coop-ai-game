import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
const component=readFileSync('app/components/simple-wardrobe.tsx','utf8');
const css=readFileSync('app/live-avatar-preview.css','utf8');

test('live preview displays current preset name and active pose without persisting pose',()=>{
 assert.match(component,/activePreset=CHARACTERS\.find\(c=>c\.id===selectedId\)/);
 assert.match(component,/activePoseLabel=previewPoses\.find\(p=>p\.value===previewPose\)/);
 assert.match(component,/activePreset\?'/);
 assert.match(component,/activePoseLabel/);
 assert.match(component,/pose=\{previewPose\}/);
 assert.doesNotMatch(component,/onChange\(\{[^}]*previewPose/);
});
test('full body preview is larger and clipped without covering gallery labels',()=>{
 assert.match(css,/height:190px/);
 assert.match(css,/height:165px/);
 assert.match(css,/\.wardrobe-live-avatar svg\{/);
 assert.match(css,/overflow:hidden!important/);
 assert.match(css,/\.quick-character>strong\{/);
 assert.match(css,/@media\(max-width:390px\)/);
 assert.match(css,/@media\(prefers-reduced-motion:reduce\)/);
});
