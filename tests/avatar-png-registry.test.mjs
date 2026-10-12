import test from 'node:test';
import assert from 'node:assert/strict';
import {PNG_PARTS} from '../shared/avatar-png-catalog.js';

test('PNG catalog has unique safe local paths for all declared assets',()=>{
 const paths=new Set();
 for(const [kind,items] of Object.entries(PNG_PARTS)){
  if(kind==='body') assert.equal(items.length,0,'No body base may be advertised before audited PNG upload');
  else assert.ok(items.length>0,kind);
  for(const item of items){
   assert.match(item.src,/^\/avatar-parts\/[a-zA-Z0-9_-]+\.png$/);
   assert.ok(!paths.has(item.src),'duplicate path '+item.src);
   paths.add(item.src);
   assert.equal(typeof item.ready,'boolean');
   assert.equal(typeof item.aligned,'boolean');
  }
 }
});
test('not-yet-uploaded assets are not falsely advertised as ready',()=>{
 for(const items of Object.values(PNG_PARTS))
  for(const item of items)
   if(item.ready===false) assert.equal(item.aligned,false);
});
