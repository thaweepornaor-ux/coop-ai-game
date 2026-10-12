import test from 'node:test';
import assert from 'node:assert/strict';
import {PNG_PARTS} from '../shared/avatar-png-catalog.js';
import {AVATAR_OPTIONS} from '../shared/avatar.js';

test('all PNG paths are unique and scoped to avatar-parts',()=>{
 const paths=Object.values(PNG_PARTS).flat().map(p=>p.src);
 assert.equal(new Set(paths).size,paths.length);
 for(const path of paths)assert.match(path,/^\/avatar-parts\/[a-zA-Z0-9_-]+\.png$/);
});
test('only the committed male face can be flagged uploaded; alignment is still pending',()=>{
 for(const part of Object.values(PNG_PARTS).flat()){
  assert.equal(part.ready,part.src==='/avatar-parts/male.png','unexpected upload status: '+part.src);
  assert.equal(part.aligned,false,'cropped thumbnail must not be marked aligned: '+part.src);
 }
});
test('face hair and glasses selectable keys match the live wardrobe values',()=>{
 for(const [group,key] of [['face','bodyStyle'],['hair','hairStyle'],['glasses','glassesStyle']]){
  const allowed=new Set(AVATAR_OPTIONS[key].map(v=>v.value));
  for(const part of PNG_PARTS[group])assert.ok(allowed.has(part.value),group+': '+part.value);
 }
});
test('mislabelled garments are never passed off as verified wardrobe combinations',()=>{
 assert.equal(PNG_PARTS.top.every(part=>!part.ready),true);
 assert.equal(PNG_PARTS.bottom.every(part=>!part.aligned),true);
 assert.equal(PNG_PARTS.shoes.every(part=>!part.ready),true);
});
