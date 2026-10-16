import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';

test('wardrobe live avatar exposes five pose buttons without changing saved avatar',()=>{
 const src=readFileSync('app/components/simple-wardrobe.tsx','utf8');
 for(const pose of ['stand','wave','think','confident','celebrate']){
  assert.match(src,new RegExp("value:'"+pose+"'"));
 }
 assert.match(src,/pose=\{previewPose\}/);
 assert.match(src,/setPreviewPose\(item.value\)/);
 assert.match(src,/aria-pressed=\{previewPose===item.value\}/);
 assert.match(src,/role="group" aria-label="ทดลองท่าทางตัวละคร"/);
 assert.doesNotMatch(src,/onChange\(\{\.\.\.avatar,pose:/,'preview-only pose must not change persisted wardrobe');
});
