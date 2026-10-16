import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {poseForAvatarPreset} from '../shared/avatar-pose.js';
const poses=['wave','confident','think','stand','celebrate'];
test('hero and gallery use exactly the same pose for twenty selectable avatars',()=>{
 for(const gender of ['M','F'])for(let i=1;i<=10;i++){
  const id=gender+String(i).padStart(2,'0');
  assert.equal(poseForAvatarPreset(id),poses[(i-1)%5],id);
 }
 for(const invalid of [undefined,null,'', 'M11','F00','something']){
  assert.equal(poseForAvatarPreset(invalid),'stand');
 }
});
test('actual learner hero synchronizes pose with preset and renders SVG-only',()=>{
 const game=readFileSync('app/game.tsx','utf8');
 const gallery=readFileSync('app/components/simple-wardrobe.tsx','utf8');
 assert.match(game,/className="avatar-preview" motion=\{false\} svgOnly pose=\{poseForAvatarPreset\(avatar\.presetId\)\}/);
 assert.match(gallery,/pose=\{poseForAvatarPreset\(c\.id\)\}/);
 assert.doesNotMatch(gallery,/\['wave','confident','think','stand','celebrate'\] as const\)\[index%5\]/);
});
