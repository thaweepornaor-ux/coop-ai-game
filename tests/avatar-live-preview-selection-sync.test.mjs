import test from 'node:test';import assert from 'node:assert/strict';import {readFileSync} from 'node:fs';
const file=readFileSync('app/components/simple-wardrobe.tsx','utf8');
test('all three avatar surfaces use same selected pose when selecting presets',()=>{
 assert.match(file,/useState<[^\n]+>\(\(\)=>poseForAvatarPreset\(avatar\.presetId\)\)/);
 assert.match(file,/setPreviewPose\(poseForAvatarPreset\(person\.id\)\)/);
 assert.match(file,/options=\{selectedId===c\.id\?avatar:/);
});
test('manual pose choice stays available for testing every arm configuration',()=>{
 assert.match(file,/onClick=\{\(\)=>setPreviewPose\(item\.value\)\}/);
});
